# 04 · The API Client (Python port)

Python port of [`ruby/04_api_client`](../../ruby/04_api_client). One HTTP
POST, one parsed JSON response, no tool-calling loop yet — that's step 05.
Stdlib only, same as Ruby's `net/http` — see that README for the raw
response shape from Anthropic vs. Ollama.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/client.py` | `Client` — POSTs the payload, retries transient failures, parses JSON |
| `boukensha/errors.py` | adds `ApiError` |

## Notable differences from the Ruby version

- **`net/http` → `urllib.request`** — both are stdlib, no extra dependency,
  matching the Ruby step's explicit "no gems" intent: the HTTP call should
  stay visible, not hidden behind a library.
- **Control flow had to change shape, not just syntax.** Ruby's `Net::HTTP`
  returns a response object *regardless of status code* — the code checks
  `response.is_a?(Net::HTTPSuccess)` after the fact. Python's
  `urllib.request.urlopen` raises `HTTPError` for any non-2xx status instead
  of returning it. So the retry loop is `try/except HTTPError` (inspect
  `.code` against the retryable set) plus a separate `except` for
  connection-level failures (`URLError` and friends — DNS failures, refused
  connections, timeouts, SSL errors), rather than one linear
  request-then-check like Ruby's.
- **SSL needed no workaround.** The Ruby README calls out a real portability
  problem: `net/http`'s default `ca_file` path is macOS-specific and doesn't
  exist on Linux/WSL2, so the step ships with `ca_file` commented out to let
  OpenSSL find system certs itself. Python's `urllib.request` builds its
  default SSL context via `ssl.create_default_context()` for every
  `https://` request automatically, which already loads the OS's CA store —
  there was nothing to work around.
- Retry policy (retryable status codes, `MAX_RETRIES = 3`, exponential
  backoff `0.5 * 2**(attempt-1)`) is ported 1:1.

## Verification

No live API key is available in this environment, so the real
Anthropic/OpenAI/etc. round trip is untested here. What *is* verified,
against local throwaway HTTP servers:

- A connection-refused target retries 3 times then raises `ApiError` (not a
  raw `URLError`).
- A `503` response retries and succeeds once the server recovers.
- A `400` response fails on the first attempt — no retry — with the status
  code and body in the `ApiError` message.

## Run

```bash
uv sync
../bin/04_api_client
```

Requires `.boukensha/settings.yaml` with `tasks.player.provider`/`model` and
the matching API key env var.
