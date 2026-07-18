# Agent Skills Architecture

## Core Concept: Reusable Capabilities
Agent Skills are defined as **reusable capabilities** that are driven by a primary coding agent. This architecture emphasizes modular, independent units of function (skills) that can be orchestrated by the main agent to handle complex tasks efficiently without requiring monolithic codebases.

## Open Standards & Ecosystem Support
Agent Skills operate as an **open standard**, ensuring broad interoperability across the developer ecosystem. They are supported by a wide array of:
*   **Coding Agents:** Compatible with various LLM-based agents and autonomous coding assistants.
*   **SDKs:** Supported by software development kits designed for agent interaction and tool definition.

This openness allows developers to utilize pre-built skills or create custom ones that work seamlessly across different tools and platforms.

## Generating Skills with Ollama

The `cmdmbox/skill-expert` Ollama model converts a plain-language capability description into a complete `SKILL.md` file. Run it with a prompt describing the workflow the agent should learn:

```bash
ollama run cmdmbox/skill-expert --hidethinking \
  "Create a skill for <capability>"
```

Replace `<capability>` with the actual task or workflow. A simple test command is:

```bash
ollama run cmdmbox/skill-expert --hidethinking \
  "Create a skill for git operations"
```

The `--hidethinking` option hides the model's reasoning so its output contains only the generated skill. The result should include YAML frontmatter followed by concise workflows, decision rules, guardrails, output requirements, and verification steps. Review the generated instructions and any shell commands before saving the output as `<skill-name>/SKILL.md` in the target agent's skills directory.

This generation step fits into the Agent Skills architecture as follows:

1. Describe a reusable capability in the prompt.
2. Generate the initial `SKILL.md` with Skill Expert.
3. Review and refine its instructions and safety constraints.
4. Install the skill in the directory recognized by the target agent.
5. Test the skill on realistic tasks and iterate as needed.
