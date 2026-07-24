"""FileSystem registers the standard set of file-oriented tools against a
registry, all sandboxed to a single root directory.

Tools registered:
  pwd              — return the working directory
  read_file        — read the full contents of a file
  write_file       — write (or overwrite) a file
  delete_file      — delete a file

list_directory and search_files are currently disabled (commented out
below) — leftover from when this app was a coding harness; the player
agent has no use for them yet.

Every path argument the agent supplies is resolved relative to that root.
If the resolved path would escape the root (path traversal) the tool
returns an error string rather than raising — so the agent sees it and
can try something sensible instead.

Usage (handled automatically by boukensha.run/boukensha.repl when
working_dir= is set, but you can call it directly too):

    file_system.register(registry, working_dir="/my/project")
"""

from __future__ import annotations

import os
from pathlib import Path


def register(registry, *, working_dir: str) -> None:
    root = str(Path(working_dir).expanduser().resolve())

    def resolve(path: str) -> str:
        """Resolve an agent-supplied path inside root. Returns the absolute
        path on success, or an error string."""
        absolute = str((Path(root) / str(path)).resolve())
        if absolute == root or absolute.startswith(root + os.sep):
            return absolute
        return f"error: path '{path}' escapes the working directory"

    def oops(msg: str) -> str:
        return f"error: {msg}"

    @registry.tool("pwd", description="Return the working directory — the root that all file paths are relative to.", parameters={})
    def pwd():
        return root

    # list_directory: disabled for now — leftover from when this app was a
    # coding harness; the current player agent has no use for it. Kept here
    # so it can be re-registered later if a task needs it.
    #
    # @registry.tool(
    #     "list_directory",
    #     description="List files and subdirectories at a path relative to the working directory. Defaults to the working directory itself.",
    #     parameters={"path": {"type": "string", "description": "Relative path to list (default '.')"}},
    # )
    # def list_directory(path="."):
    #     target = resolve(path)
    #     if target.startswith("error:"):
    #         return target
    #     if not os.path.isdir(target):
    #         return oops(f"'{path}' is not a directory")
    #
    #     entries = sorted(e for e in os.listdir(target) if e not in (".", ".."))
    #     entries = [f"{name}/" if os.path.isdir(os.path.join(target, name)) else name for name in entries]
    #     return "(empty)" if not entries else "\n".join(entries)

    @registry.tool(
        "read_file",
        description="Read and return the full contents of a file. Path is relative to the working directory.",
        parameters={"path": {"type": "string", "description": "Relative path to the file"}},
    )
    def read_file(path):
        target = resolve(path)
        if target.startswith("error:"):
            return target
        if not os.path.isfile(target):
            return oops(f"'{path}' is not a file")
        try:
            return Path(target).read_text()
        except OSError as e:
            return oops(str(e))

    @registry.tool(
        "write_file",
        description="Write content to a file, creating it (and any missing parent directories) if needed, overwriting if it exists. Path is relative to the working directory.",
        parameters={
            "path": {"type": "string", "description": "Relative path to the file"},
            "content": {"type": "string", "description": "Text content to write"},
        },
    )
    def write_file(path, content):
        target = resolve(path)
        if target.startswith("error:"):
            return target
        try:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_text(content)
            rel = target[len(root) + 1 :] if target.startswith(root + os.sep) else target
            return f"ok: wrote {len(content.encode())} bytes to {rel}"
        except OSError as e:
            return oops(str(e))

    @registry.tool(
        "delete_file",
        description="Delete a file. Directories are not deleted. Path is relative to the working directory.",
        parameters={"path": {"type": "string", "description": "Relative path to the file to delete"}},
    )
    def delete_file(path):
        target = resolve(path)
        if target.startswith("error:"):
            return target
        if not os.path.isfile(target):
            return oops(f"'{path}' is not a file")
        try:
            os.remove(target)
            return f"ok: deleted {path}"
        except OSError as e:
            return oops(str(e))

    # search_files: disabled for now — same reason as list_directory above.
    #
    # @registry.tool(
    #     "search_files",
    #     description="Search for a text pattern (literal string or regex) across all files in the working directory tree. Returns matching lines in 'path:line_number:content' format.",
    #     parameters={
    #         "pattern": {"type": "string", "description": "The text or regex pattern to search for"},
    #         "path": {"type": "string", "description": "Subdirectory or file to search within (default '.' = entire working directory)"},
    #         "glob": {"type": "string", "description": "File glob to restrict which files are searched, e.g. '*.py' (default '*')"},
    #     },
    # )
    # def search_files(pattern, path=".", glob="*"):
    #     target = resolve(path)
    #     if target.startswith("error:"):
    #         return target
    #
    #     candidates = [target] if os.path.isfile(target) else sorted(str(p) for p in Path(target).rglob(glob))
    #
    #     try:
    #         regex = re.compile(pattern)
    #     except re.error as e:
    #         return oops(f"invalid pattern: {e}")
    #
    #     matches = []
    #     for file in candidates:
    #         if not os.path.isfile(file):
    #             continue
    #         rel = file[len(root) + 1 :] if file.startswith(root + os.sep) else file
    #         try:
    #             with open(file, errors="replace") as f:
    #                 for lineno, line in enumerate(f, start=1):
    #                     if regex.search(line):
    #                         matches.append(f"{rel}:{lineno}:{line.rstrip(chr(10))}")
    #         except OSError as e:
    #             matches.append(f"{rel}: error reading file: {e}")
    #
    #     return "no matches" if not matches else "\n".join(matches)
