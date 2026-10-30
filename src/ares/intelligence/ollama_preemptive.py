"""Opt-in process-isolated Ollama request with a preemptive wall-clock limit.

Only the local loopback transport is supported. The worker cannot call tools.
"""

from multiprocessing import get_context
from multiprocessing.connection import Connection
from time import monotonic

from ares.intelligence.ollama_transport import OllamaLocalTransport
from ares.intelligence.transport import ProviderTransportError, RequestLimits


def _worker(
    connection: Connection,
    payload: bytes,
    limits: RequestLimits,
    host: str,
    port: int,
) -> None:
    try:
        result = OllamaLocalTransport(port=port, host=host).request(payload, limits=limits)
        connection.send_bytes(b"1" + result)
    except Exception:
        connection.send_bytes(b"0")
    finally:
        connection.close()


class PreemptiveOllamaTransport:
    """Kill a subprocess that exceeds the request budget; no hidden retries."""

    def __init__(self, port: int = 11434, host: str = "127.0.0.1") -> None:
        # Validate the address before starting a worker.
        OllamaLocalTransport(port=port, host=host)
        self._host = host
        self._port = port

    def request(self, payload: bytes, *, limits: RequestLimits) -> bytes:
        context = get_context("spawn")
        reader, writer = context.Pipe(duplex=False)
        process = context.Process(
            target=_worker,
            args=(writer, payload, limits, self._host, self._port),
            daemon=True,
        )
        started = monotonic()
        try:
            process.start()
            writer.close()
            remaining = max(0.0, limits.timeout_seconds - (monotonic() - started))
            if not reader.poll(remaining):
                raise ProviderTransportError("ollama_deadline_exceeded")
            try:
                message = reader.recv_bytes(maxlength=limits.max_response_bytes + 1)
            except (EOFError, OSError) as exc:
                raise ProviderTransportError("ollama_worker_failed") from exc
            if message[:1] != b"1":
                raise ProviderTransportError("ollama_worker_failed")
            response = message[1:]
            if len(response) > limits.max_response_bytes:
                raise ProviderTransportError("provider_response_too_large")
            if monotonic() - started > limits.timeout_seconds:
                raise ProviderTransportError("ollama_deadline_exceeded")
            return response
        finally:
            reader.close()
            writer.close()
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
