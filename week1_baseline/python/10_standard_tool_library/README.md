# 10 · A Standard Tool Library (Python port)

Python port of [`ruby/10_standard_tool_library`](../../ruby/10_standard_tool_library)
— see [`docs/plans/10_standard_tool_library.md`](../../../docs/plans/10_standard_tool_library.md)
for the scope decision this step is built on: `ITERATIONS.md` claims steps
10–12 use an MCP-host rewrite, but no such code exists anywhere in this
repo's `ruby/` files (confirmed by grep). What's actually here is the
*original* built-in tool modules, ported as three pieces:

- **`mud_manager/`** — a from-scratch port of `week0_explore/mud_manager/`
  (a Ruby gem this step depends on with no prior Python equivalent): a
  threaded telnet client (`session.py`) plus ~50 stateless CircleMUD
  command builders (`primitives.py`).
- **`boukensha/tools/file_system.py`** — 6 tools sandboxed to a working
  directory (pwd, list_directory, read_file, write_file, delete_file,
  search_files).
- **`boukensha/tools/shell.py`** — 1 tool (`run_command`) with a timeout
  and optional allow-list.
- **`boukensha/tools/mud.py`** — 26 tools wrapping a persistent
  `mud_manager.Session`.

`boukensha.run()`/`boukensha.repl()` gain `working_dir=`,
`allowed_commands=`, `shell_timeout=`, and `mud=` keyword arguments that
wire these in automatically.

## Code Changes

| File | Purpose |
|------|---------|
| `mud_manager/primitives.py` | ~50 CircleMUD command builders — new |
| `mud_manager/session.py` | threaded telnet client — new |
| `boukensha/tools/file_system.py` | 6 sandboxed file tools — new |
| `boukensha/tools/shell.py` | `run_command` — new |
| `boukensha/tools/mud.py` | 26 MUD gameplay tools — new |
| `boukensha/context.py` | adds `working_dir` |
| `boukensha/__init__.py` | `run()`/`repl()` gain 4 kwargs + tool auto-registration |
| `boukensha/repl.py` | banner gains a `mud:` status line |

`client.py`/`config.py` have zero diff from step 09's Ruby reference — the
step 08→09 regression persists unfixed there too, and we're not reverting
our (better) versions to match it, same call as step 09.

## A Ruby-side detour, not a bug in this port

Ruby's `repl.rb` banner went: rich (step 08) → regressed to plain
`(default)` placeholders (step 09, unexplained) → rich again *plus* a new
`mud:` line (step 10). Our Python `repl.py` never regressed — we kept step
08's version through 09 on purpose — so this step's change here is "add
the `mud:` line on top of what we already have," not "apply the 09→10
diff literally" (which would assume a regressed starting point this port
never had).

## Notable differences from the Ruby version

### `mud_manager`

- **Ruby's `Struct.new(..., keyword_init: true)` → a Python `@dataclass`**
  for `Command`, same as `Tool`/`Message` in earlier steps.
- **Ruby's `Mutex` + `ConditionVariable` → Python's `threading.Condition`**,
  which bundles both into one object. The timing logic in
  `read_until_quiet` (clamp the wait to `min(quiet_remaining,
  total_remaining)`) is a direct translation, verified against a fake TCP
  server with a deliberately delayed multi-packet response.
- **Ruby's `:return`/`:enter` symbol sentinel (meaning "send a bare Enter
  keystroke") → Python's `None`.** Symbols have no Python equivalent;
  `None` is the natural "no value" sentinel and reads more clearly than a
  fake `":return"` string would.
- **IAC (telnet protocol) byte stripping operates on raw `bytes`**, not
  the decoded string, matching Ruby's operation on the byte array before
  re-encoding — verified against a fake server that interleaves real IAC
  negotiation sequences (`WILL`/`SB...SE`) with real text.
- **Ruby's `rescue EOFError, IOError, ECONNRESET` (expected, silent) vs.
  `rescue StandardError => e; warn(...)` (unexpected, logged) is a real
  distinction, preserved** — not collapsed into one blanket `except`. A
  graceful disconnect (`OSError` from a closed socket) is silent; anything
  else in the reader thread gets printed.
- **`Process.clock_gettime(CLOCK_MONOTONIC)` → `time.monotonic()`** — both
  monotonic clocks immune to wall-clock adjustments.

### Tool modules

- **`FileSystem`'s path-escape guard returns an error *string*, not an
  exception** — ported as-is; the agent needs to *see* the rejection as
  tool output, not have the turn crash.
- **`Shell`'s allow-list check uses naive whitespace splitting for the
  first token, deliberately not `shlex`** — matching Ruby's own
  `split(/\s+/).first` exactly rather than "upgrading" to shell-aware
  parsing, which would change what gets rejected.
- **`Open3.capture2e` + `Timeout.timeout` → `subprocess.run(shell=True,
  capture_output=True, timeout=...)`** with `text=True` and stdout+stderr
  concatenated to match the merged-stream behavior; `subprocess.TimeoutExpired`
  replaces Ruby's manual `Timeout::Error` rescue.
- **`Tools::Mud` is a mechanical, near-identical port of ~26 tool
  registrations** — guard → build a `Primitives` command → send → catch
  the validation error → return an error string. `send_cmd`'s
  drain-before-send (so `read_until_prompt` only sees this command's fresh
  output, not stale async chatter) is the one piece of real logic, ported
  exactly.

### Wiring

- **A real naming collision, resolved with an aliased import.** `run()`/
  `repl()` have a `mud=` keyword parameter, which would shadow a bare
  `from .tools import mud` at call time — Ruby doesn't hit this
  (`Tools::Mud`, capitalized, is a different identifier from a local `mud`
  variable; Python has no such built-in distinction). Imported as
  `from .tools import mud as mud_tools` instead.
- **`working_dir`'s default is resolved inside the function body, not
  baked into the signature.** Ruby's `working_dir: Dir.pwd` evaluates
  fresh on every call; a Python `working_dir: str = os.getcwd()` default
  would freeze the cwd at *function-definition* time — the same class of
  bug as the `Agent(logger=Logger())` trap from step 06. Used
  `working_dir: str | bool | None = None` and resolved `os.getcwd()`
  inside the body instead.
- **`mud:` resolution is a real three-way branch**: `False` → skip
  entirely; `None` (default) → build from `Config.mud_host`/`mud_username`
  (finally read for the first time — they've been carried as unused since
  step 07) if a host is configured, else skip; an explicit dict → use it
  directly. Verified all three states independently.
- **The banner's `mud:` probe is TCP-reachability only, not a login
  check** — the tool session already auto-connects at registration, so a
  second login attempt from the banner would double-login. Python:
  `socket.create_connection((host, port), timeout=3)`, closed immediately,
  catching `OSError`.

### A second stale runner script found

Like step 09's `ruby/bin/09_global_executable` (pointing at a nonexistent
`examples/example.rb`), `ruby/bin/10_standard_tool_library` has the same
problem — it references `examples/example.rb`, but this step's actual file
is `examples/demo.rb`. No Python equivalent bug to replicate; our launcher
correctly points at `examples/demo.py`.

## Verification

No live CircleMUD/tbaMUD server reachable from this sandbox (confirmed:
connection refused on `localhost:4000`), so `mud_manager.Session` and
`tools.mud` are both verified against fake TCP servers built for this step
(the same pattern as `Client`'s HTTP stub-server tests in step 04):

- `mud_manager.primitives`: spot-checked across movement, combat,
  communication, and inventory categories, including invalid-enum and
  invalid-argument error paths.
- `mud_manager.session`: a full login sequence (name → password → Welcome
  → menu keystrokes) with real IAC negotiation bytes mixed into the
  stream, confirming they're stripped and never leak as garbage text; a
  `LoginError` on a wrong-password response; a `ConnectionError` on a
  refused connection; and `read_until_quiet`'s timing against a
  deliberately delayed two-chunk response (confirmed it waits for the
  quiet window — not instant, not the full timeout).
- `Tools::FileSystem`: path traversal rejected (both `../` and absolute
  paths), the full write/read/delete round trip, and `search_files`
  against a real multi-file tree including an invalid-regex error path.
- `Tools::Shell`: allow-list rejection confirmed to happen *before*
  `subprocess.run` is ever called (via a call-counting patch, not just
  the returned string), a real enforced timeout, and merged stdout+stderr
  output.
- `Tools::Mud` against a fake server: auto-connect on registration, the
  "not connected" guard both before connecting and after an explicit
  disconnect, one tool from each category round-tripping through
  `send_cmd`, `send_raw`'s escape hatch, and an invalid-enum argument
  producing an error string instead of crashing.
- `run()`'s tool auto-registration: `working_dir=<path>` registers
  FileSystem+Shell (and not Mud, when unconfigured);
  `working_dir=False` registers neither.
- All three `mud:` resolution states, plus a real request against
  `api.anthropic.com` with a fake key (same posture as every prior step)
  confirming the full pipeline still reaches the live API correctly.
- The REPL banner's `mud:` line against unconfigured, unreachable, and
  reachable-with/without-credentials states.

## Run

```bash
uv sync
../bin/10_standard_tool_library
```

Requires `.boukensha/settings.yaml` with `tasks.player.provider`/`model`
and, for the MUD demo specifically, a `mud:` block (`host`/`port`/
`username`/`password`) pointing at a running CircleMUD/tbaMUD server.
