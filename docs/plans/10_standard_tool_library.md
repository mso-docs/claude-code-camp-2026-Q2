# Step 10 · A Standard Tool Library

**Ruby reference:** `week1_baseline/ruby/10_standard_tool_library/` (+ `week0_explore/mud_manager/` for `Tools::Mud`)
**Python port:** `week1_baseline/python/10_standard_tool_library/`
**Status:** Planned

## Scope note — see prior discussion

`ITERATIONS.md` claims this step (and 11, 12) use an MCP-host rewrite.
Confirmed by grep across every `.rb` file in `week1_baseline/ruby/`: no
such code exists anywhere in this repo. What's actually in
`10_standard_tool_library` is the *original* built-in tool modules
(`Tools::FileSystem`, `Tools::Shell`, `Tools::Mud`) that `ITERATIONS.md`
says were deleted — they weren't, at least not here. Porting what's
actually on disk. Per your call: including `Tools::Mud`, which means
porting `mud_manager` (`week0_explore/mud_manager/`) first — it's a
Ruby-only gem this step depends on that has no existing Python port.

## Goal

Give the agent a standard library of capabilities out of the box instead
of registering every tool by hand: `Tools::FileSystem` (6 sandboxed
file-oriented tools), `Tools::Shell` (1 command-execution tool with a
timeout and optional allow-list), and `Tools::Mud` (26 CircleMUD gameplay
tools riding on a single persistent session). `run()`/`repl()` gain
`working_dir:`, `allowed_commands:`, `shell_timeout:`, and `mud:` keyword
arguments that wire these in automatically.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `week0_explore/mud_manager/lib/mud_manager/primitives.rb` | `mud_manager/primitives.py` | ~50 stateless CircleMUD command builders — mechanical |
| `week0_explore/mud_manager/lib/mud_manager/session.rb` | `mud_manager/session.py` | threaded telnet client — the hard part |
| `lib/boukensha/tools/file_system.rb` | `boukensha/tools/file_system.py` | 6 sandboxed tools |
| `lib/boukensha/tools/shell.rb` | `boukensha/tools/shell.py` | 1 tool, subprocess + timeout |
| `lib/boukensha/tools/mud.rb` | `boukensha/tools/mud.py` | 26 tool registrations wrapping `mud_manager` |
| `lib/boukensha/context.rb` (+`working_dir`) | `boukensha/context.py` | one new constructor param |
| `lib/boukensha.rb` (`run`/`repl` gain 4 kwargs + tool auto-registration) | `boukensha/__init__.py` | |
| `lib/boukensha/repl.rb` (banner gains a `mud:` status line) | `boukensha/repl.py` | builds on our existing (already-correct) banner — see note below |

`client.rb`/`config.rb` have **zero diff** from step 09 — the step
08→09 regression persists unfixed here too. No change needed: we already
carry step 08's better versions forward and aren't reverting them.

## A Ruby-side detour worth knowing about before touching `repl.py`

Ruby's `repl.rb` banner went: rich (step 08) → regressed to plain
`(default)` placeholders (step 09, unexplained) → rich again *plus* a new
`mud:` status line (step 10). Diffing 10 directly against 09 makes it look
like this step reintroduces the rich formatting — but our Python
`repl.py` never regressed in the first place (we kept step 08's version
through 09 on purpose). So the correct move here is **not** "apply the
09→10 diff" (which assumes a regressed starting point we don't have) —
it's "add the new `mud:` line and `mud=` parameter directly on top of the
banner we already have." Noting this so the diff-application approach
doesn't accidentally re-derive a middle state that never existed in our
port.

## Design decisions — `mud_manager` port

**`Primitives` is the easy half — pure, stateless, mechanical.** ~50
module-level functions, each validating enum/string arguments and
returning a `Command`. Ruby's `Command = Struct.new(:primitive, :raw,
:verb, :args, keyword_init: true)` → a Python `@dataclass`. Ruby's
`check_enum!`/`require_str!` private helpers → two small module-level
functions. No concurrency, no I/O — straightforward line-by-line port.

**`Session` is the hard half — a threaded telnet client.** Ruby uses a
background `Thread` continuously draining the socket into a buffer
guarded by a `Mutex` + `ConditionVariable`, with IAC (telnet protocol)
byte-stripping and a CircleMUD-specific login state machine. Python's
`threading.Thread` + `threading.Condition` (which bundles a lock and a
condition variable into one object, unlike Ruby's separate `Mutex`/`ConditionVariable`)
map directly. Key behaviors to preserve exactly:
- `read_until_quiet(quiet_seconds, timeout)` — waits for a quiet window
  *or* an overall timeout, whichever comes first; the "wait_for" clamping
  logic (`min(quiet_remaining, total_remaining)`) is easy to get subtly
  wrong and needs a direct translation, not a rewrite.
- `read_until(pattern, timeout)` — blocks until a regex/string match
  appears in the buffer, consuming up through the match; raises a
  `Timeout` error type distinct from `ConnectionError`.
- IAC stripping (`strip_iac`) — a byte-level state machine (`WILL`/`WONT`/`DO`/`DONT`
  = 3-byte sequences to discard; `SB...SE` = variable-length subnegotiation
  to discard; literal `IAC IAC` = one literal 0xFF byte to keep). Porting
  byte-for-byte against Python `bytes`/`bytearray`, not the decoded string,
  matching Ruby's operation on `bytes.bytes` (a byte array) before
  re-encoding.
- The CircleMUD `login()` state machine (name prompt → password prompt →
  Welcome/Reconnecting/Wrong-password branch → main-menu keystrokes for a
  fresh login).

**Ruby's `Process.clock_gettime(Process::CLOCK_MONOTONIC)` → Python's
`time.monotonic()`.** Both are monotonic clocks immune to wall-clock
adjustments — the direct equivalent, not `time.time()`.

**Thread safety note carried into the port, not introduced by it.** The
reader thread and the calling thread communicate purely through the
mutex-guarded buffer and condition variable — no other shared mutable
state. Python's GIL doesn't change what needs to be synchronized here;
`threading.Condition` is used the same way it would be needed even without
a GIL, since `wait()`/`notify_all()` semantics (not atomicity of simple
ops) are what's actually being relied on.

## Design decisions — tool modules

**`Tools::FileSystem`'s path-escape guard returns an error *string*, not
an exception.** `resolve(path)` returns either the resolved absolute path
or a string starting with `"error:"` — callers check
`.startswith("error:")` rather than catching an exception. A slightly odd
API (stringly-typed error signaling) but ported as-is since it's load-bearing:
the agent needs to *see* the error as tool output, not have the whole
turn crash on a path-traversal attempt.

**`Tools::Shell`'s allow-list check happens before any subprocess is
spawned.** The first whitespace-split token of the command is checked
against `allowed_commands` (when set) before `subprocess` ever runs —
ported as a guard clause up front, not a post-hoc check.

**Ruby's `Open3.capture2e` + `Timeout.timeout` → Python's
`subprocess.run(..., capture_output=True, timeout=...)`.** `capture2e`
merges stdout+stderr into one stream; `subprocess.run` needs
`stderr=subprocess.STDOUT` to get the same merged-stream behavior. Ruby's
`Timeout.timeout` wraps *any* block; Python's `subprocess.run(timeout=)`
raises `subprocess.TimeoutExpired` directly — cleaner here, no manual
signal-based timeout needed.

**`Tools::Mud` is ~26 near-identical registrations: guard → build a
`Primitives` command → send → catch `ArgumentError` → return an error
string.** Faithful mechanical port, tool by tool. The one piece of real
logic to get right: `send_cmd` drains stale buffered bytes *before*
sending a command, so `read_until_prompt` only sees fresh output from
*this* command, not leftover async chatter from between turns.

**Auto-connect at tool-registration time, with a caught failure.** `Mud.register`
tries to open + log in immediately so the agent doesn't waste a turn
calling `mud_connect` first; a connection failure at registration time is
caught and warned, not raised — the agent can still call `mud_connect`
manually later. Ported as a best-effort startup attempt, not a hard
requirement.

## Design decisions — wiring

**`Context` gains a `working_dir` param**, expanded to an absolute path
when given, stored as a plain attribute (not currently read by `Context`
itself — `Tools::FileSystem`/`Tools::Shell` take their own `working_dir:`
argument directly from `run()`/`repl()`, independent of what's stored on
`Context`). Porting for structural parity even though nothing reads it
back off `Context` yet.

**`run()`/`repl()`'s `mud:` resolution has three states, not two.**
`mud: false` → skip entirely. `mud: None` (Ruby's implicit default) →
look at `Config`'s `mud_host`/`mud_username` (which we've been carrying
as unused dead code since step 07 — this is the step where they finally
get read) and build options from there if a host is configured, else
`None`. An explicit `mud: {...}` dict → use it directly. This is a
real three-way branch, not a simple `or` default.

**The REPL banner's `mud:` line does a live TCP reachability probe, not a
login check.** `probe_mud` opens a raw socket with a 3-second timeout and
immediately closes it — deliberately *not* attempting a real login, since
the tool session already auto-connects at registration time and a second
login attempt from the banner would double-login. Python:
`socket.create_connection((host, port), timeout=3)` then close, catching
`OSError` (covers connection-refused, timeout, and DNS failure in one).

## Verification plan

No live CircleMUD/tbaMUD server reachable from this sandbox (confirmed:
connection refused on `localhost:4000`) — `Session` needs a fake TCP
server, the same pattern used for `Client`'s HTTP tests in step 04.

- `mud_manager.primitives`: spot-check representative functions across
  categories (movement, combat, communication, inventory) for correct
  `Command.raw` output and correct `ArgumentError`/`ValueError` on invalid
  enum values.
- `mud_manager.session` against a local fake TCP server (`socket`/`threading`
  based, not `http.server`) that: sends IAC negotiation bytes mixed with
  real text (verify they're stripped from the buffer), plays out the
  CircleMUD login sequence (name prompt → password prompt → Welcome →
  menu keystrokes), and exercises `read_until_quiet`'s timing logic with a
  deliberately delayed response.
- `Tools::FileSystem`: path traversal rejected (`../` escaping root, and
  an absolute path outside root), `search_files` regex matching, and the
  `write_file`/`read_file`/`delete_file` round trip against a scratch
  directory.
- `Tools::Shell`: allow-list rejection *before* any subprocess spawns
  (verify via a spy/counter, not just the returned string), a real timeout
  via a deliberately slow command, and the merged stdout+stderr behavior.
- `Tools::Mud` against the fake session server: the guard's "not
  connected" message when called before `mud_connect`, at least one tool
  from each category actually round-tripping through `send_cmd`, and
  `send_raw`'s escape hatch.
- `run()`'s three-way `mud:` resolution (`False`, `None` with/without a
  configured host, and an explicit dict).
- The REPL banner's `mud:` line against both a reachable and an
  unreachable fake TCP endpoint.

## Outcome

_(fill in after implementation)_
