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

## 2. Give Pi project instructions and a startup task

Pi automatically discovers `AGENTS.md` (plural) in the working directory. Store the reusable MUD rules, memory behavior, and safety constraints in:

```text
week0_explore/explore_architecture/01_plain_agent/AGENTS.md
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
