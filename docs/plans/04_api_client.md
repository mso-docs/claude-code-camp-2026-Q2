# Step 04 · The API Client

**Ruby reference:** `week1_baseline/ruby/04_api_client/`
**Python port:** `week1_baseline/python/04_api_client/`
**Status:** Done

## Goal

Take the payload `PromptBuilder` assembled and actually POST it — one HTTP
call, parse the JSON response, no tool-calling loop yet (that's step 05).
Ruby deliberately uses only its stdlib `net/http` here — no gems — because
the HTTP call is meant to be visible, not hidden behind a library.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/client.rb` | `boukensha/client.py` | `net/http` → `urllib.request` (both stdlib) |
| `lib/boukensha/errors.rb` (adds `ApiError`) | `boukensha/errors.py` | add `ApiError` |
| everything from step 03 | carried forward unchanged |

## Design decisions

- **Stdlib only, matching Ruby's intent.** `urllib.request` is Python's
  direct analog of `net/http` — no `requests` dependency, keeping the HTTP
  call itself visible in the port the same way the Ruby step insists on it.
- **Retry policy ported 1:1:** same retryable status codes
  (`408, 409, 429, 500, 502, 503, 504`), `MAX_RETRIES = 3`, exponential
  backoff `0.5 * 2**(attempt - 1)`.
- **Control-flow difference to handle carefully:** Ruby's `Net::HTTP`
  returns a response object regardless of status code — the code inspects
  `response.is_a?(Net::HTTPSuccess)` itself. Python's `urllib.request.urlopen`
  *raises* `HTTPError` (a subclass of `URLError`) for any non-2xx status
  instead of returning it. The retry loop has to be restructured around
  `try/except HTTPError` (retryable/non-retryable by status code) and
  `try/except URLError` (connection-level failures — Ruby's `TRANSIENT_ERRORS`
  list: `ECONNRESET`, `ECONNREFUSED`, timeouts, SSL errors, etc.), rather
  than a single post-request status check.
- **SSL:** Ruby's README flags `net/http` CA-file portability issues
  (macOS vs. Linux/WSL2) as a known rough edge, resolved by *not* setting
  `ca_file` and letting OpenSSL find system certs. Python's `urllib.request`
  uses `ssl.create_default_context()` automatically for `https://` URLs,
  which loads the OS's default CA store the same way — expect this to just
  work without the workaround Ruby needed, but call it out if it doesn't.
- `ApiError` message format carried forward: include attempt count and
  status code/body on final failure, matching Ruby's wording closely enough
  to be recognizable.

## Verification plan

- Unit-level: construct a `Client` against each backend's `PromptBuilder`
  and confirm `call()` builds the right request (can't fully verify network
  behavior without live API keys in this environment).
- If a real `ANTHROPIC_API_KEY` is available, run the example for real and
  compare the raw response shape against the Ruby README's documented
  Anthropic/Ollama response examples.
- Explicitly exercise the error path: a bad URL or unreachable host should
  raise `ApiError` after `MAX_RETRIES` attempts, not hang or raise a raw
  `URLError`.

## Outcome

Matched the plan, including the anticipated control-flow restructuring
around `HTTPError`/`URLError`. No live API key was available in this
environment, so the real network round-trip is unverified here — instead
verified the retry/error/success logic against local throwaway HTTP
servers (connection-refused → retries then `ApiError`; `503` → retries then
succeeds; `400` → fails immediately, no retry). SSL needed no workaround, as
predicted. See [`python/04_api_client/README.md`](../../week1_baseline/python/04_api_client/README.md).

## Ruby build checklist (reference)

The course's checklist for building `ruby/04_api_client` itself (not a
Python-port checklist). Checked retrospectively.

**1. Add the API Client Iteration**
- [x] 1.1 `week1_baseline/ruby/04_api_client` exists with content
- [x] 1.2 No unwanted `Zone.Identifier` files
- [ ] 1.3 Runner under `week1_baseline/bin/ruby` — **doesn't exist**; actual runner is `week1_baseline/ruby/bin/04_api_client`, same deviation as steps 02–03

**2. Configure a Provider**
- [ ] 2.1 API key(s) added — **not present**: no `.env` exists yet at the repo's `.boukensha/`
- [ ] 2.2 Provider/model configured in `settings.yaml` — **not present** either, same gap
- [x] 2.3 `.env` excluded from Git — confirmed in `.gitignore` (`.env`, `.env.local`)

**3. Test the API Client**
- [ ] 3.1 Run the example — **not verified**, Ruby isn't installed in this sandbox
- [~] 3.2 N/A — no config to fail on since it was never run here
- [ ] 3.3 Confirm a successful provider response — **not verified**, no live credentials in this environment

**4. Commit the Iteration**
- [x] 4.1 Reviewed git status (as part of this investigation)
- [x] 4.2 No secrets/`.env` staged — confirmed clean
- [ ] 4.3 Commit the completed iteration separately — **not how the Ruby side happened** (one `Initial commit` for all of `ruby/`); the Python port now does commit one step at a time going forward

**Real gap worth flagging:** neither the Ruby nor the Python API client has
actually been exercised against a live provider in this environment — both
are verified structurally/via mocks only, since `.boukensha/settings.yaml`
and `.env` don't exist yet. Worth doing a real end-to-end run once you set
those up.
