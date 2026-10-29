# ARES Intelligence — offline baseline

The pipeline invokes the policy-checked sensor gateway, builds a deterministic
assessment, and validates an untrusted structured proposal.

`LocalReferenceModel` is **not a language model**. It is a zero-cost baseline
to test orchestration without API credentials, networking, or model variability.

All decisions are recommendations only. No tool commands, write permissions,
approvals, actuators or recovery actions are created by this module.

Run tests with `uv run pytest tests/intelligence -v`.

Future provider adapters must honor the same `ModelAdapter` contract, bound
response limits, timeouts and validated inputs. An external model integration
requires separate privacy, operational and security reviews.
