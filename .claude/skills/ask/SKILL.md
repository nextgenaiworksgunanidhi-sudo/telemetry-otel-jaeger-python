---
name: ask
description: Answer a technical question about Python, OTel, Jaeger, or AI. Use when user says ask <question> or what is <topic>
argument-hint: <question>
user-invocable: true
---

## Instructions

When the user asks a technical question:

1. Run the skill and capture the full JSON output:
   `python3 .claude/skills/ask/index.py --question "<question>" --triggered-by claude | tail -1`

2. Send telemetry passing the raw JSON output directly:
   `python3 hooks/send_span.py --skill ask --input "<question>" --skill-output '<json output from step 1>' --triggered-by claude --status ok --file-path .claude/skills/ask/SKILL.md`

3. Return the `message` field from the JSON output to the user.

If step 1 fails, run step 2 with `--status error --error "<error message>"` instead.

## Example triggers

- "ask what is opentelemetry?"
- "what is jaeger?"
- "ask what is python?"
- "/ask what is a span?"
