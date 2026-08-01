# Step 09 · Global Executable

**Ruby reference:** `week1_baseline/ruby/09_global_executable/`
**Python port:** `week1_baseline/python/09_global_executable/`
**Status:** Done

## Goal

Package Boukensha so a `boukensha` command works from anywhere on the
machine, not just from inside a step folder. The gem/package is "a wrapper
and a default" — it doesn't copy or symlink any teaching material, it just
knows where to look. A loader resolves *which* step's code to boot, in
priority order:

1. `$BOUKENSHA_PATH` env var — point at any step folder
2. `$HOME/.boukensharc` — a file containing a single path, for a persistent default
3. The bundled step (this one) — the fallback

This is orthogonal to `$BOUKENSHA_DIR` (Ruby, and our `state.config()`),
which resolves the *config* directory (`settings.yaml`/`.env`), not which
*code* to run.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `boukensha.gemspec` | `pyproject.toml` `[project.scripts]` entry point | gem metadata → Python package metadata |
| `bin/boukensha` | console-script entry point (no separate file needed) | `uv`/hatchling generates the shim from `[project.scripts]` |
| `lib/boukensha_loader.rb` (`BoukenshaLoader`) | `boukensha_loader.py` | the actual porting work in this step |
| `lib/boukensha.rb` + `lib/boukensha/` | `boukensha/` (this step's copy) | see the regression note below — carrying forward step 08's versions, not this step's |

## A real regression in this step's Ruby snapshot — not replicating it

Diffing `08_the_repl_loop` against `09_global_executable` turns up three
unexplained reversions, none mentioned anywhere in this step's README
(whose entire stated scope is gem packaging):

- `client.rb` loses the friendly `401` message added in step 08, reverting
  to the generic "API request failed after N attempts" wording.
- `config.rb` loses the project-local `.boukensha/` CWD tier added in step
  08, reverting to the plain 2-tier (`$BOUKENSHA_DIR` → `$HOME/.boukensha`)
  resolution from step 07 and earlier.
- `repl.rb`'s banner loses the computed API-key-status / "directory not
  found" messaging, reverting to plain `(default)` placeholders for
  `config`/`provider`, and drops the `model:` line's rich formatting.

This is the same *kind* of drift we've flagged before (`mud_*`,
`LoopError` toggling on and off between steps 05–07), but higher-stakes:
those were always dead code either way, so it didn't matter which snapshot
"won." This time it's tested, working, user-facing behavior actually
regressing. Nothing in the README claims this step touches `client`/
`config`/`repl` internals at all — its whole scope is the loader and
packaging — so there's no narrative reason to believe this is intentional.

**Decision: this step's Python port carries forward step 08's
`client.py`/`config.py`/`repl.py` unchanged, not step 09's regressed
versions.** Reverting working, verified functionality to match an
apparently-accidental snapshot gap would make the Python port strictly
worse for no pedagogical reason. Flagging this prominently (here, in the
step's README, and in the architecture doc) rather than silently
diverging — if this turns out to be deliberate and I'm missing context,
it's easy to spot and reverse.

## Design decisions

**Ruby's `require <absolute path>` → Python's `sys.path` manipulation.**
`BoukenshaLoader.load_and_start_repl` does `require main` where `main` is
a computed absolute path to a *different* step folder's `lib/boukensha.rb`
— Ruby's `require` accepts absolute paths directly. Python's import system
doesn't have a direct equivalent for "import this exact file as a named
module," but doesn't need one here: every step's Python package is simply
named `boukensha` at the top of its own step directory, so resolving to a
different step is just `sys.path.insert(0, resolved_step_dir)` before
`import boukensha` — the same trick every `examples/example.py` in this
port already uses, just pointed at a runtime-computed directory instead of
a hardcoded relative one. No `importlib.util.spec_from_file_location`
machinery needed.

**Module-caching hazard, avoided by construction.** If this process had
already done `import boukensha` from one path, a later `import boukensha`
from a different path would silently return the *first* cached module
(Python caches by module name in `sys.modules`, not by path) — a real
footgun for a loader whose whole job is "load boukensha from a
runtime-chosen location." Not an issue here because `boukensha_loader.py`
never imports `boukensha` itself before resolving and inserting the target
path; it only computes strings. Worth stating explicitly since it's the
kind of bug that only appears when someone later refactors this to import
eagerly.

**Ruby's `abort <<~MSG` → print to stderr + exit 1.** Ruby's `abort`
prints to `$stderr` and exits with status 1 in one call. Python has no
single-call equivalent; using `sys.stderr.write(msg)` + `sys.exit(1)` (or
`raise SystemExit(msg)`, which does exactly that).

**`$BOUKENSHA_DEBUG` is a separate flag from `state.is_debug()`.** The
loader checks `os.environ.get("BOUKENSHA_DEBUG")` directly to decide
whether to print its own `[boukensha] loading from: ...` diagnostic line —
this is unrelated to `Boukensha.debug!`/`state.set_debug()`, which gates
`Logger.raw()` deep inside the agent loop. Two different debug flags for
two different concerns; not consolidating them, since Ruby doesn't either.

**Packaging: `uv`/hatchling entry point in place of a gemspec + `gem
build`/`gem install`.** `[project.scripts] boukensha = "boukensha_loader:main"`
in `pyproject.toml` is the direct equivalent of `spec.executables =
["boukensha"]` — installing this project (`uv tool install .` from this
directory, or `pip install -e .`) puts a `boukensha` command on `$PATH`
that Python itself generates as a thin shim calling `boukensha_loader.main()`,
the same role Ruby's `bin/boukensha` shebang script plays by hand.

## Verification plan

- Unit-test `resolve()`'s three-tier priority directly (no real install
  needed): `$BOUKENSHA_PATH` set and valid; `$BOUKENSHA_PATH` set but
  invalid (should abort with a specific message, not silently fall
  through); unset with a valid `$HOME/.boukensharc`-equivalent (parameterize
  the rc path for testability rather than hardcoding `~`); neither set,
  falls back to the bundled step.
- Confirm the "step doesn't support the REPL" path: point resolution at a
  step directory whose `boukensha` package has no `repl` attribute (e.g. a
  scratch copy of an early step) and confirm the friendly abort message,
  not a raw `AttributeError`.
- Confirm no `sys.modules` collision: resolve and "load" two different
  step directories in sequence within one process and verify the second
  one's `boukensha.VERSION` (or another distinguishing attribute) actually
  reflects the second path, not a cached first import — this is the
  concrete test for the module-caching hazard noted above.
- If feasible in this sandbox, actually `uv tool install --editable .` (or
  `uv build`) and confirm a real `boukensha` shim gets produced and runs.

## Outcome

Matched the plan, plus one thing discovered only by actually building the
wheel: hatchling's `[tool.hatch.build.targets.wheel] include = [...]`
silently did *not* put `boukensha_loader.py` (a standalone top-level
module, not part of the `boukensha` package) into the built wheel —
`packages` only picks up directories. Caught by inspecting the wheel's
actual contents (`python3 -m zipfile -l ...`) rather than trusting that
the config "looked right," which it did. Fixed with `force-include`,
re-verified by inspecting the wheel again.

Every verification-plan item passed, and pushed further than planned: got
a real console-script `boukensha` installed via `uv tool install .` and
exercised it as an actual global command — bundled default, a
`BOUKENSHA_PATH` override to a different step, the no-REPL friendly
abort, the invalid-path friendly abort, and `BOUKENSHA_DEBUG=1`'s
diagnostic line — not just calling the loader's functions directly.
Uninstalled the tool and removed `dist/` afterward (and added `**/dist/`
to `.gitignore`) so the verification pass didn't leave global state
behind on this machine. See
[`python/09_global_executable/README.md`](../../week1_baseline/python/09_global_executable/README.md).
