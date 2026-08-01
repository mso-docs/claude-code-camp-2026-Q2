# 00 · Configuration (Python port)

Python port of [`ruby/00_config`](../../ruby/00_config). Same behavior, same
`.boukensha/` directory (`BOUKENSHA_DIR` env var, else `$HOME/.boukensha`),
same `settings.yaml` schema — see the Ruby README for the full schema and
directory-resolution rules, which are unchanged here.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `Config` class |
| `boukensha/tasks/base.py` | abstract `Base` (provider/model + prompt resolution) |
| `boukensha/tasks/player.py` | concrete `Player` (the main loop) |
| `boukensha/__init__.py` | top-level package exports |
| `prompts/system.md` | default system prompt shipped with the package |
| `examples/example.py` | runnable smoke-test |

## Notable differences from the Ruby version

- **No string/symbol duality.** Ruby's `dig`/`tasks` handle both `"player"`
  and `:player` because YAML gives strings but Ruby code favors symbols.
  Python has one string type, so `dig()` and `tasks()` are simpler — no
  dual lookups needed.
- **`Base` methods are `@classmethod`, not Ruby singleton methods** —
  same effect (stateless, called on the class, never instantiated), just
  Python's spelling of it.
- Ruby's `Pathname` → Python's `pathlib.Path`; `Dotenv.load` → `python-dotenv`'s
  `load_dotenv`; `YAML.safe_load` → `pyyaml`'s `yaml.safe_load`.

## Run

```bash
uv sync
../bin/00_config          # or: uv run python examples/example.py
```

Requires a `.boukensha/settings.yaml` at the repo root (shared with the Ruby
version) — see `ruby/00_config/README.md` for the schema.
