"""External service clients. Each service has an interface, a Real impl, and a
Fake impl used by tests and offline demo mode (selected via USE_FAKE_CLIENTS).
Every real network call goes through ``resilient_call`` (retry + backoff)."""
