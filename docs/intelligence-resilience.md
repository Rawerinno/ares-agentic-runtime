# Intelligence resilience — initial offline contracts

The bounded proposal engine records accepted, rejected and provider-failed
outcomes, a stable error code and elapsed duration. It never stores provider
exception text in its outcome and never executes a tool.

The response-size limit uses the size of a Python string representation of
the returned mapping: it is a *defense in depth* check, not a transport byte
limit. Remote providers must enforce response byte/token caps before parsing.

Elapsed time is **not a timeout**. No arbitrary worker thread or remote model
can be safely interrupted by this synchronous wrapper. Implement mandatory
transport-level deadlines, cancellation and output limits in each remote
provider adapter before deploying it. No provider adapter is enabled yet.
