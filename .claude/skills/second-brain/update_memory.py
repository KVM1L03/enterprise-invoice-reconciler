#!/usr/bin/env python3
"""Append a structured memory entry to docs/project_memory.md."""

import sys
from datetime import datetime, timezone
from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "project_memory.md"


def derive_title(summary: str) -> str:
    """Extract a short title from the first sentence of the summary."""
    import re

    # Split on sentence boundaries: period followed by space+uppercase or end of string
    sentences = re.split(r"\.(?:\s+(?=[A-Z])|\s*$)", summary)
    first_sentence = sentences[0].strip()
    if len(first_sentence) > 80:
        first_sentence = first_sentence[:77] + "..."
    return first_sentence


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, respecting dotted identifiers like dspy.configure."""
    import re

    # Split on period followed by whitespace and an uppercase letter (sentence boundary)
    parts = re.split(r"\.\s+(?=[A-Z])", text)
    return [p.strip().rstrip(".") for p in parts if p.strip()]


def build_entry(summary: str) -> str:
    """Build a Markdown entry from the summary text."""
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = derive_title(summary)

    lines = split_sentences(summary)

    decisions = []
    bugs = []
    state = []

    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in ("fix", "bug", "race", "error", "anti-pattern", "resolved", "eradicat")):
            bugs.append(f"- {line}.")
        elif any(kw in lower for kw in ("implement", "architect", "decision", "design", "chose", "replacing", "pattern")):
            decisions.append(f"- {line}.")
        else:
            state.append(f"- {line}.")

    # Ensure each section has at least one bullet
    if not decisions:
        decisions.append("- No new architectural decisions in this entry.")
    if not bugs:
        bugs.append("- No bugs resolved in this entry.")
    if not state:
        state.append("- See summary above for current state.")

    return (
        f"\n## {now} - {title}\n"
        f"\n**Summary:** {summary}\n"
        f"\n### Architectural Decisions Made\n"
        f"\n" + "\n".join(decisions) + "\n"
        f"\n### Critical Bugs Resolved (Anti-Patterns avoided)\n"
        f"\n" + "\n".join(bugs) + "\n"
        f"\n### Current State & Next Steps\n"
        f"\n" + "\n".join(state) + "\n"
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: update_memory.py <summary>", file=sys.stderr)
        sys.exit(1)

    summary = sys.argv[1]

    if not MEMORY_FILE.exists():
        print(f"ERROR: Memory file not found at {MEMORY_FILE}", file=sys.stderr)
        sys.exit(1)

    entry = build_entry(summary)

    with MEMORY_FILE.open("a") as f:
        f.write(entry)

    print(f"OK: Appended entry to {MEMORY_FILE.relative_to(MEMORY_FILE.parent.parent)}")


if __name__ == "__main__":
    main()
