# telemetry-otel-jaeger-python

Local Claude skill telemetry using OpenTelemetry + Jaeger.  
Each skill traces itself directly — no hooks required.  
Works with **Claude Code CLI** and **VS Code Copilot Chat** from the same `.claude/skills/` folder.

---

## Setup

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Jaeger
docker compose up -d

# 4. Run test spans
python test_spans.py
```

Open **http://localhost:16686** → service **`claude-skills`** → Search.

---

## Skills

| Skill | Trigger | Slash command (Copilot) |
|---|---|---|
| `greet` | "greet Guna", "hello Alice" | `/greet Guna` |
| `joke`  | "tell me a joke", "make me laugh" | `/joke` |

Both skills live in `.claude/skills/` — this single folder is read by both Claude Code and VS Code Copilot (open standard defined at agentskills.io).

---

## Invoking skills

### Claude Code CLI
```bash
cd telemetry-otel-jaeger-python
claude
# type: greet Guna
```
Claude reads `SKILL.md`, follows the run instruction, executes `index.py`, and a span is exported.

### VS Code Copilot Chat

**Prerequisites**
- VS Code 1.99 or later
- GitHub Copilot extension installed and signed in
- Agent skills enabled (VS Code 1.99+ enables them by default; if not, add to `settings.json`):

```json
{
  "github.copilot.chat.agentSkills.enabled": true
}
```

**Steps**

1. Open this project folder in VS Code:
   ```bash
   code .
   ```

2. Start Jaeger (if not already running):
   ```bash
   docker compose up -d
   ```

3. Open Copilot Chat — press `Ctrl+Alt+I` (Mac: `Cmd+Alt+I`) or click the Copilot icon in the sidebar.

4. Make sure the chat mode is set to **Agent** (not Ask or Edit) using the dropdown at the top of the chat panel.

5. Use a slash command or natural language:
   ```
   /greet Guna
   /joke
   greet Guna
   tell me a joke
   ```

6. Copilot reads `.claude/skills/greet/SKILL.md`, follows the run instruction, and executes:
   ```bash
   python3 .claude/skills/greet/index.py --name Guna --triggered-by claude
   ```

7. The skill prints its output and a span is exported to Jaeger automatically.

**Verify traces**

Open http://localhost:16686 → service `claude-skills` → Search.  
If Jaeger is not running, check `telemetry_spans.json` and run:
```bash
python view_spans.py --skill greet
```

### Direct CLI (debugging / CI)
```bash
python .claude/skills/greet/index.py --name Guna --triggered-by cli
python .claude/skills/joke/index.py --triggered-by cli
```
Output is JSON: `{"skill": "greet", "message": "Hello, Guna! ..."}`.

---

## Span attributes

### `trace_skill` — fired on every skill execution

| Attribute | Example value | Notes |
|---|---|---|
| `skill.name` | `"greet"` | always |
| `skill.file_path` | `".claude/skills/greet/SKILL.md"` | always |
| `skill.triggered_by` | `"claude"` | always |
| `skill.session_id` | `"8e38203a-8567-..."` | UUID per process — groups all spans from one session |
| `skill.input` | `{"name": "Guna"}` | JSON string of arguments |
| `skill.status` | `"ok"` / `"error"` | always |
| `skill.duration_ms` | `3.14` | always |
| `skill.response` | `"{'skill': 'greet', ...}"` | first 1024 chars of return value |
| `skill.llm_response` | `"Hello, Guna! ..."` | `message` field from result dict |
| `skill.error` | `"SKILL.md not found"` | only on exception |

### `trace_skill_read` — fired when a SKILL.md is considered

| Attribute | Example value | Notes |
|---|---|---|
| `skill.name` | `"greet"` | always |
| `skill.file_path` | `".claude/skills/greet/SKILL.md"` | always |
| `skill.session_id` | `"8e38203a-8567-..."` | same UUID as execution span |
| `skill.event` | `"read"` | always |
| `skill.triggered` | `true` / `false` | did the agent decide to use this skill? |
| `skill.query` | `"greet Guna"` | only if non-empty |

### Trace structure in Jaeger

```
skill.greet          ← parent span (execution)
  └── skill.read.greet   ← child span (SKILL.md read)
```

---

## Jaeger fallback — view spans offline

When Jaeger is unreachable, spans are written to `telemetry_spans.json` automatically.  
View them with:

```bash
python view_spans.py                   # all spans
python view_spans.py --skill greet     # filter by skill name
python view_spans.py --status error    # only errors
python view_spans.py --tail 10         # last 10 spans
```

---

## Adding a new skill

1. Create `.claude/skills/<name>/SKILL.md`:

```markdown
---
name: myskill
description: What it does. Use when user says ...
argument-hint: <arg>
user-invocable: true
---

## Instructions

When the user says "...":
1. Run: `python3 .claude/skills/myskill/index.py --arg <value> --triggered-by claude`
2. Return the message field from the JSON output
```

2. Create `.claude/skills/<name>/index.py`:

```python
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from hooks.otel_skill_tracer import trace_skill, trace_skill_read

_SKILL_MD = Path(__file__).parent / "SKILL.md"

def run_myskill_skill(triggered_by: str, context: dict) -> dict[str, str]:
    def _execute() -> dict[str, str]:
        trace_skill_read("myskill", str(_SKILL_MD), "", triggered=True)
        return {"skill": "myskill", "message": "Hello from myskill"}

    return trace_skill(
        skill_name="myskill",
        skill_path=str(_SKILL_MD),
        triggered_by=triggered_by,
        fn=_execute,
        inputs={"triggered_by": triggered_by},
    )

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--triggered-by", default="cli")
    args = parser.parse_args()
    print(json.dumps(run_myskill_skill(args.triggered_by, {})))
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint for Jaeger |

---

## Project structure

```
.
├── .claude/
│   ├── settings.json
│   └── skills/
│       ├── greet/
│       │   ├── SKILL.md          # argument-hint, user-invocable, run instruction
│       │   └── index.py          # run_greet_skill + __main__ CLI entry
│       └── joke/
│           ├── SKILL.md
│           └── index.py
├── hooks/
│   └── otel_skill_tracer.py      # singleton TracerProvider, trace_skill, trace_skill_read
├── test_spans.py                 # exercises all span types
├── view_spans.py                 # offline span viewer for telemetry_spans.json
├── telemetry_spans.json          # auto-created when Jaeger is unreachable
├── docker-compose.yml            # Jaeger all-in-one
├── requirements.txt
└── README.md
```
