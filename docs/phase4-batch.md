# Consolidated Phase 4 checks

Run offline with `uv run python -m ares.evaluation.phase4_batch`.

For optional local Ollama, run `uv run python -m ares.evaluation.phase4_batch --live --model llama3.2:3b --repeats 3`.

The output separates raw classification from governed classification, includes offline acceptance and verifies two temporary audit entries. It does not persist audit records from the batch. A successful batch is not an industrial safety certification.
