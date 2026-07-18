---
name: git-workflow
description: Use when initializing a repository, making changes, committing, and pushing code.
---

# Git Workflow

Follow these steps sequentially. Do not proceed until each step is complete.

## Step 1: Initialize Repository (first time only)

If no `.git` directory exists in the current directory:

```bash
git init -b main
git add .
git commit -m "Initial commit"
```

If a remote repository already exists, skip this step and proceed to Step 2.

## Step 2: Stage Changes

Run `git status`. If there are untracked files or modified files not yet staged:

```bash
git add .
git status
```

Verify that only intended changes are staged. Do not stage unnecessary files.

## Step 3: Commit Changes

Create a descriptive commit message:

```bash
git commit -m "Type: Description of changes"
```

If the commit is incomplete, run `git status` again and add missing changes before committing.

## Step 4: Push to Remote

Check if the remote exists:

```bash
git remote -v
```

If no remote exists, create one:

```bash
git remote add origin <remote-url>
```

Push your branch:

```bash
git push -u origin <branch-name>
```

## Decision Rules

### Before committing:
- If the commit is a continuation of previous work, use `-m "Update: description"` instead of a generic message.
- Do not commit WIP (work in progress) or debug messages.
- Do not commit credentials, tokens, or secrets.

### After pushing:
- If push fails due to conflicts, stop and ask the user how to proceed.
- Do not force push (`git push -f`) unless explicitly instructed by the user.

## Guardrails

- Never run `git reset --hard` without explicit confirmation from the user.
- Never delete remote branches or tags without explicit confirmation.
- If a command fails, report the exact error and suggest recovery steps.
- Do not commit sensitive information to git history.

## Output Requirements

After completing the workflow:

```markdown
Git operations complete.
Branch: $(git branch --show-current)
Status: $(git status --short)
Last commit: $(git log -1 --oneline)
```

