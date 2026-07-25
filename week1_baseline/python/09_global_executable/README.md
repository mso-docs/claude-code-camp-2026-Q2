# 09 · Global Executable (Python port)

Python port of [`ruby/09_global_executable`](../../ruby/09_global_executable).
Packages Boukensha so a `boukensha` command works from anywhere on the
machine — a wrapper and a default, not a copy: it doesn't duplicate any
teaching material, it just knows where to look.

```
$BOUKENSHA_PATH env var  →  ~/.boukensharc file  →  bundled step (this one)
```

This is separate from `$BOUKENSHA_DIR` (which `Config`/`state.config()`
already handles) — that resolves the *config* directory
(`settings.yaml`/`.env`), not which *code* runs.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha_loader.py` | resolves which step to load, then boots the REPL — the actual porting work in this step |
| `pyproject.toml` `[project.scripts]` | `boukensha = "boukensha_loader:main"` — the entry point that becomes the global command |
| `boukensha/` | this step's copy — see the regression note below, it's step 08's code, not step 09's |

There's no `examples/` in this step (Ruby's own `09_global_executable` has
none either) — the "example" is running the installed command itself.

## A real regression in this step's Ruby snapshot, not replicated

Diffing `08_the_repl_loop` against `09_global_executable` on the Ruby side
turns up three reversions with nothing in the README explaining them —
whose entire stated scope is gem packaging, nothing to do with these files:

- `client.rb` loses the friendly `401` message added in step 08.
- `config.rb` loses the project-local `.boukensha/` CWD resolution tier
  added in step 08.
- `repl.rb`'s banner loses the API-key-status / "directory not found"
  messaging, reverting to plain `(default)` placeholders.

Same category of drift as `mud_*`/`LoopError` toggling between steps
05–07, but higher stakes: those were always dead code either way, this is
tested, working, user-facing behavior actually disappearing with no
justification. **This step's `boukensha/client.py`/`config.py`/`repl.py`
are step 08's versions, carried forward unchanged, not step 09's
regressed ones.** Reverting real functionality to match an
apparently-accidental snapshot gap would make the port strictly worse for
no pedagogical reason.

Also: `ruby/bin/09_global_executable` (the runner script) points at
`examples/example.rb`, which doesn't exist in this step — a stale,
broken script, presumably copy-pasted from an earlier step's template and
never updated. No Python equivalent launcher was written for this step for
the same reason — see "Try it" below for the real way to exercise this.

## Notable differences from the Ruby version

- **`require <absolute path>` → `sys.path` manipulation.** Ruby's
  `require main` loads a computed absolute path directly. Python doesn't
  need an equivalent trick here: every step's package is named `boukensha`
  at the top of its own directory, so loading a different step is just
  `sys.path.insert(0, resolved_step_dir)` before `import boukensha` — the
  same pattern every `examples/example.py` in this port already uses,
  just pointed at a runtime-computed directory.
- **Module-caching hazard, defused explicitly.** If `boukensha` had
  already been imported from one path in this process, importing it again
  from a different path would silently return the *first* cached module
  (`sys.modules` caches by name, not path). `load_and_start_repl` calls
  `sys.modules.pop("boukensha", None)` before importing, specifically so
  resolving a different step actually reloads from there — verified
  directly by loading two different step directories in one process and
  confirming the second import's `__file__` reflects the new path.
- **`abort <<~MSG` → stderr write + `sys.exit(1)`.** Ruby's `abort` does
  both in one call; Python needs the two spelled out (`_abort()` helper).
- **`$BOUKENSHA_DEBUG` is a separate flag from `state.is_debug()`.** The
  loader checks it directly to decide whether to print its own
  `[boukensha] loading from: ...` line — unrelated to `Boukensha.debug!`,
  which gates `Logger.raw()` deep inside the agent loop.
- **`resolve()` takes injectable `boukensha_path`/`rc_path` parameters**,
  defaulting to `$BOUKENSHA_PATH`/`~/.boukensharc` — a small addition
  beyond a literal port, needed so tests can exercise every branch without
  mutating real environment variables or writing to the actual user's home
  directory.
- **Packaging: `[project.scripts]` + `uv build`/`uv tool install` in place
  of a gemspec + `gem build`/`gem install`.** Getting `boukensha_loader.py`
  (a standalone top-level module, not part of the `boukensha` package)
  into the wheel needed `[tool.hatch.build.targets.wheel.force-include]`
  — hatchling's `packages` only picks up directories, and a plain
  `include` line silently didn't include it either; confirmed by actually
  inspecting the built wheel's contents rather than assuming the config
  worked.

## Verification

- `resolve()`'s full priority chain, with real env/home-directory
  dependencies replaced by injected parameters: valid `BOUKENSHA_PATH`,
  invalid `BOUKENSHA_PATH` (aborts, doesn't fall through), valid injected
  rc file, invalid rc file (aborts), neither set (bundled default).
- The "step doesn't support the REPL" path, pointed at step 07's package
  (no `repl` attribute) — friendly abort message, not a raw
  `AttributeError`.
- The module-caching hazard test described above.
- Actually built the wheel (`uv build`), inspected its contents to confirm
  both `boukensha/` and `boukensha_loader.py` are present alongside a
  correct `console_scripts` entry, then `uv tool install .`'d it for real
  and ran the resulting global `boukensha` command against a scratch
  config: confirmed the bundled-default path, `BOUKENSHA_PATH` overriding
  to a different step, the no-REPL friendly error, the invalid-path
  friendly error, and `BOUKENSHA_DEBUG=1`'s diagnostic line — all via the
  actual installed executable, not just library calls. Uninstalled it and
  removed `dist/` afterward to avoid leaving global state on this machine
  from a verification pass.

## Try it

```bash
cd week1_baseline/python/09_global_executable
uv build
uv tool install .
boukensha                                    # bundled default (this step)
BOUKENSHA_PATH=../08_the_repl_loop boukensha  # run a different step
BOUKENSHA_DEBUG=1 boukensha                   # print which step loaded
uv tool uninstall boukensha                   # clean up
```
