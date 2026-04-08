---
name: Update Project Memory
description: >
  Appends a structured entry to docs/project_memory.md recording architectural decisions,
  conquered bugs, and current project state. Use after completing a major milestone or
  resolving a critical issue so future sessions can bootstrap context quickly.
command: python3 .claude/skills/second-brain/update_memory.py "$1"
---

# Update Project Memory

## When to use

Run this skill after completing a significant piece of work — a new feature, a bug fix,
an architectural decision, or a phase milestone.

## Input

Pass a single summary string describing what was accomplished. The script will parse it
and append a dated, structured Markdown section to `docs/project_memory.md`.

## Example

```
python .claude/skills/second-brain/update_memory.py "Implemented MCP bridge with verify_purchase_order tool. Decided on stdio transport over HTTP for subprocess isolation."
```
