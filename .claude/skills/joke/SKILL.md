---
name: joke
description: Tell a random programming joke. Use when user says tell me a joke, joke, or make me laugh
argument-hint: (no arguments needed)
user-invocable: true
---

## Instructions

When the user asks for a joke:
1. Run: `python3 .claude/skills/joke/index.py --triggered-by claude`
2. Return the message field from the JSON output

## Example triggers

- "tell me a joke"
- "joke"
- "make me laugh"
- "say something funny"
