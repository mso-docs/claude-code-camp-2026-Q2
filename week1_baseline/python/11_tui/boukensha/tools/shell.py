"""Shell registers command-execution tools against a registry.

Tools registered:
  run_command  — run an arbitrary shell command inside the working directory

Options:
  working_dir:      (required) all commands run with this as their cwd
  timeout:          seconds before a command is killed (default 30)
  allowed_commands: optional list of allowed executable names (e.g.
                    ["python", "git"]). When None (the default) all
                    commands are permitted. When set, any command whose
                    first token is not in the list is rejected before
                    execution.

Usage (handled automatically by boukensha.run/boukensha.repl when
working_dir= is set):

    shell.register(registry, working_dir="/my/project",
                    allowed_commands=["python", "pytest", "git"])
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def register(registry, *, working_dir: str, timeout: int = 30, allowed_commands: list[str] | None = None) -> None:
    root = str(Path(working_dir).expanduser().resolve())

    def oops(msg: str) -> str:
        return f"error: {msg}"

    allowed_note = f" Allowed executables: {', '.join(allowed_commands)}." if allowed_commands else ""

    @registry.tool(
        "run_command",
        description=(
            "Run a shell command inside the working directory and return its combined stdout+stderr output. "
            f"Commands run with a {timeout}-second timeout.{allowed_note}"
        ),
        parameters={"command": {"type": "string", "description": "The shell command to execute (e.g. 'python script.py', 'ls -la', 'git status')"}},
    )
    def run_command(command):
        if allowed_commands:
            # Naive whitespace split, matching the Ruby reference exactly
            # (not shlex — this is a first-word heuristic, not a real
            # shell-aware parse, and changing that would change behavior).
            tokens = command.strip().split()
            executable = tokens[0] if tokens else ""
            if executable not in [str(c) for c in allowed_commands]:
                return oops(f"'{executable}' is not in the allowed-commands list ({', '.join(allowed_commands)})")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=root,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return oops(f"command timed out after {timeout}s: {command}")
        except OSError as e:
            return oops(f"command not found: {e}")

        output = (result.stdout + result.stderr).strip()
        exit_note = "" if result.returncode == 0 else f"\n[exit {result.returncode}]"
        return f"(no output){exit_note}" if not output else f"{output}{exit_note}"
