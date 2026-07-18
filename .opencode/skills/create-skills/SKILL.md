---
name: create-skills
description: Create or improve reusable Agent Skills defined by a named directory and SKILL.md. Use when asked to make, scaffold, generate, review, validate, install, or refine a skill for OpenCode or another Agent Skills-compatible coding agent.
---

# Create Skills

Turn a reusable capability into a concise, discoverable, and validated skill.

## Workflow

1. Determine the concrete requests that should trigger the skill and the result each request should produce. Infer these when the request is clear; ask only when different answers would materially change the skill.
2. Choose a lowercase hyphenated name under 64 characters. Prefer a short verb-led name and make the directory name match it exactly.
3. Confirm the installation scope. For OpenCode, use `.opencode/skills/<name>/SKILL.md` for the current project or `~/.config/opencode/skills/<name>/SKILL.md` globally. Preserve an existing compatible location when updating a skill.
4. Plan only the resources needed repeatedly:
   - `scripts/` for deterministic operations that would otherwise be rewritten.
   - `references/` for detailed domain material loaded only when needed.
   - `assets/` for templates or files copied into outputs.
5. Create `SKILL.md`, then add only the planned resources. Do not add a README, changelog, installation guide, or other auxiliary documentation.
6. Validate the structure and inspect the final files before reporting completion.

## Write SKILL.md

Start with YAML frontmatter containing only `name` and `description` for broad compatibility:

```markdown
---
name: example-skill
description: State what the skill does and the requests or contexts that should trigger it.
---
```

Make the description specific because agents use it to decide whether to load the skill. Put all trigger guidance in the description rather than in a later "When to use" section.

Write the body as direct, imperative instructions for another capable agent. Include non-obvious procedures, decision rules, safety constraints, expected outputs, and verification steps. Prefer concise examples over general explanation. Keep the main file under 500 lines and link directly to optional resources when details would make it too large.

Match instruction precision to risk: allow judgment where several approaches are safe, but prescribe exact commands and checks for fragile or irreversible work.

## Optional Skill Expert Draft

When the user requests Ollama's `cmdmbox/skill-expert`, treat its output as a draft rather than automatically trusting it.

1. Locate and explicitly load the intended `.env` when it defines `OLLAMA_HOST`; do not assume the shell loads `.env` automatically.
2. Run `ollama list` and confirm `cmdmbox/skill-expert` exists on that server.
3. Generate into a temporary file with `--hidethinking --nowordwrap`.
4. Review the frontmatter, commands, permissions, safety constraints, and output requirements.
5. Rewrite vague or excessive content before placing it in the final skill directory.

Use a capability-focused request:

```bash
ollama run cmdmbox/skill-expert \
  --hidethinking \
  --nowordwrap \
  "Create a skill for <capability, workflow, guardrails, and expected output>"
```

Never place secrets, credentials, machine-specific tokens, or private server addresses in a generated skill.

## Validate

Before reporting success, verify:

- The directory and `name` use the same valid lowercase hyphenated name.
- `SKILL.md` exists with valid YAML delimiters and non-empty `name` and `description`.
- The description explains both capability and triggering context.
- The body contains actionable instructions and a completion check.
- Every referenced resource exists and every included resource is necessary.
- No placeholders or generated terminal-control characters remain.
- The target agent can discover the chosen installation path.

When an available platform validator exists, run it and fix every reported error. Otherwise, perform the checklist directly and show the final path.
