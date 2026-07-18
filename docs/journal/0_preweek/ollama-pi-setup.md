# Local Ollama and Pi Agent Setup

For this experiment, the models are running locally via Ollama. Pi provides the coding-agent harness and terminal tools used to interact with the MUD.

## 1. Install Ollama

On Debian or Ubuntu, install the archive prerequisite and then install Ollama using the official installer for your operating system:

```bash
sudo apt-get update
sudo apt-get install -y zstd
hash -r
ollama --version
```

Confirm that Ollama is available and list the locally installed models:

```bash
ollama list
```

If the required model is not present, pull it before launching Pi:

```bash
ollama pull <model-name>
```

## 2. Create an Agent Skill with Skill Expert

Use Ollama's [`cmdmbox/skill-expert`](https://ollama.com/cmdmbox/skill-expert) model to turn a plain-language capability description into the contents of a `SKILL.md` file. The model is designed specifically for prompts in the form `Create a skill for ...`, so describe the reusable task the agent should learn rather than asking for a general tutorial.

### Copy-paste template

Copy this template and replace the two values on the first two lines:

```bash
SKILL_NAME="your-skill-name"
SKILL_REQUEST="the capability, workflow, guardrails, and expected output"

mkdir -p "002_agent_skills/$SKILL_NAME"
ollama run cmdmbox/skill-expert \
  --hidethinking \
  --nowordwrap \
  "Create a skill for $SKILL_REQUEST" \
  > "002_agent_skills/$SKILL_NAME/SKILL.md"
```

For example, this verified test command creates a draft skill for Git operations:

```bash
ollama run cmdmbox/skill-expert \
  --hidethinking \
  --nowordwrap \
  "Create a skill for git operations" \
  > 002_agent_skills/git-skill.md
```

Each part of the command has a purpose:

- `Create a skill for ...` gives the specialist model a direct capability description from which it can generate YAML frontmatter and operational instructions. Adding the workflow, guardrails, and expected output makes the generated skill more specific and useful.
- `--hidethinking` hides the model's reasoning so it is not mixed into the generated skill.
- `--nowordwrap` disables Ollama's interactive terminal word wrapping. Without it, redirected output can contain literal ANSI cursor-control characters such as `ESC[1D` and `ESC[K`, along with duplicated word fragments.
- `>` writes the final response to the requested file. It overwrites that file if it already exists.

Review the generated instructions, safety constraints, and shell commands before using the skill. For an installable Agent Skill, keep it in a named directory with the standard filename `<skill-name>/SKILL.md`; the first template creates that structure.

## 3. Give Pi project instructions and a startup task

Pi automatically discovers `AGENTS.md` (plural) in the working directory. Store the reusable MUD rules, memory behavior, and safety constraints in:

```text
week0_explore/explore_architecture/001_playing_agent/AGENTS.md
```

Do not place passwords in that committed file. Put the task that should begin immediately in `START.md`, for example:

```markdown
Play the MUD and complete every goal in AGENTS.md. Use the available terminal
and file tools, update the player and world memory after meaningful actions,
and continue until every requested output file has been created. Do not stop
after merely explaining how to perform the task.
```

Launch Pi from the agent directory and submit `START.md` automatically:

```bash
ollama launch pi --model <model-name> -- \
  --approve \
  -p \
  @START.md \
  "Execute the attached task now."
```

Replace `<model-name>` with a tool-capable model shown by `ollama list`. The `-p` option runs non-interactively, prints the final response, and exits. Omit `-p` to leave Pi open as an interactive chat after submitting the initial task.

When text pasted into interactive Pi appears as `[paste #1 +12 lines]`, the paste succeeded; Pi has only collapsed the multiline content in the editor. Press Enter to submit it.
