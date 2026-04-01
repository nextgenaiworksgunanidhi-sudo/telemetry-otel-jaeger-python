---
name: greet
description: Greet a person by name. Use when user says greet <name> or hello <name>
argument-hint: <name>
user-invocable: true
---

## Instructions

When the user says "greet <name>" or "hello <name>":
1. Extract the name from the message
2. Run: `python3 .claude/skills/greet/index.py --name <name> --triggered-by claude`
3. Return the message field from the JSON output

## Example triggers

- "greet Guna"
- "hello Alice"
- "say hello to Bob"
