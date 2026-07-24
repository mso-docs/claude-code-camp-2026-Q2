# Step 00 · Configuration

**Ruby reference:** `week1_baseline/ruby/00_config/`
**Python port:** `week1_baseline/python/00_config/`
**Status:** Done

## Goal

One class (`Config`) that resolves `.boukensha/` (`$BOUKENSHA_DIR` or
`~/.boukensha`), loads `.env`, and loads `settings.yaml` into a plain dict.
Task settings (`tasks.player.*`) are looked up through a stateless
`Tasks::Base` → `Tasks::Player` pair — class methods only, never instantiated.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/config.rb` | `boukensha/config.py` | `Pathname` → `pathlib.Path`, `Dotenv` → `python-dotenv`, `YAML.safe_load` → `pyyaml` |
| `lib/boukensha/tasks/base.rb` | `boukensha/tasks/base.py` | Ruby singleton methods → Python `@classmethod` |
| `lib/boukensha/tasks/player.rb` | `boukensha/tasks/player.py` | direct 1:1 |
| `prompts/system.md` | `prompts/system.md` | copied verbatim |
| `examples/example.rb` | `examples/example.py` | 1:1 output format |

## Design decisions

- Package manager: `uv`, one self-contained project per step (mirrors Ruby's
  per-step `Gemfile`).
- Ruby's `dig`/`tasks` juggle string vs. symbol hash keys (YAML gives
  strings, Ruby code favors symbols). Python has one string type, so that
  duality just doesn't exist in the port — a real simplification, not a
  1:1 translation.

## Verification

Ran `examples/example.py` against a scratch `.boukensha/settings.yaml`
(with and without `prompt_override.system: true`) and confirmed output
matches the Ruby README's "Expected output" block field-for-field.

## Outcome

Matches plan. See [`python/00_config/README.md`](../../week1_baseline/python/00_config/README.md) for the full differences list.

## Course checklist

This is the actual course task list for step 00 (supersedes an earlier,
wrongly-generic checklist draft). Checked against what was actually done.

**1. Prepare the Python Port**
- [x] 1.1 Create `week1_baseline/python/00_config`
- [ ] 1.2 Create a porting plan — **not satisfied as ordered**: this plan was written retroactively, after steps 00–04 were all already implemented, not before 00's changes were made
- [x] 1.3 Use the Ruby `00_config` implementation as the reference

**2. Configure the Python Project**
- [x] 2.1 Set up a Python virtual environment — via `uv sync`, which creates `.venv` automatically rather than a manual `python -m venv`
- [x] 2.2 Add the required dependencies (`python-dotenv`, `pyyaml` in `pyproject.toml`)
- [x] 2.3 Update the Python README with setup instructions (`README.md`'s "Run" section)

**3. Port the Configuration**
- [x] 3.1 Ported the Ruby configuration implementation to Python
- [x] 3.2 Kept the same configuration schema (`tasks.player.*`, `mud.*` — unchanged from Ruby's `settings.yaml`)
- [x] 3.3 Loads the external `.boukensha` configuration (dir resolution, `.env`, `settings.yaml`)
- [x] 3.4 Supports overriding the config directory for the example (`BOUKENSHA_DIR` env var, same as Ruby's `ENV["BOUKENSHA_DIR"] ||= ...`)

**4. Add the Python Runner**
- [x] 4.1 Created a Python launcher — at `week1_baseline/python/bin/00_config`, mirroring where Ruby's own launcher actually lives (`week1_baseline/ruby/bin/00_config`); there is no top-level `week1_baseline/bin/` in this repo for either language, so `bin/python/...` doesn't apply literally here
- [ ] 4.2 Verify both the Ruby and Python launchers work independently — **not fully satisfied**: only the Python launcher was run. Ruby is not installed in this sandbox (`which ruby` fails), so the Ruby launcher could not be executed or verified here — only read and reasoned about

**5. Verify the Port**
- [x] 5.1 Ran the Python config example
- [x] 5.2 Confirmed the configuration loads successfully
- [x] 5.3 Verified player settings and system prompt are loaded (checked against a scratch `settings.yaml`, including the `prompt_override.system: true` path)
- [~] 5.4 Compared output with the Ruby implementation — compared against the Ruby README's documented "Expected output" block, not a live side-by-side run, since Ruby can't run in this environment

**6. Finish**
- [x] 6.1 Reviewed git status
- [x] 6.2 Commit the completed Python port — committed as `8525e5d`, but by you directly outside this conversation, not as a step performed here
