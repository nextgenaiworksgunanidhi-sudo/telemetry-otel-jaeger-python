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

| Skill | Trigger | Slash command (Copilot) | Telemetry approach |
|---|---|---|---|
| `greet` | "greet Guna", "hello Alice" | `/greet Guna` | OTel SDK (`otel_skill_tracer.py`) |
| `joke`  | "tell me a joke", "make me laugh" | `/joke` | OTel SDK (`otel_skill_tracer.py`) |
| `ask`   | "ask what is jaeger?", "what is a span?" | `/ask what is python?` | Stdlib HTTP (`send_span.py`) |

All skills live in `.claude/skills/` — this single folder is read by both Claude Code and VS Code Copilot (open standard defined at agentskills.io).

---

## Invoking skills

### Claude Code CLI
```bash
cd telemetry-otel-jaeger-python
claude
# type: greet Guna
# type: ask what is opentelemetry?
```
Claude reads `SKILL.md`, follows the run instruction, executes `index.py`, and a span is exported.

### VS Code Copilot Chat

**Prerequisites**
- VS Code 1.99 or later
- GitHub Copilot extension installed and signed in
- Agent skills enabled (VS Code 1.99+ enables them by default; if not, add to VS Code `settings.json`):

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
   /ask what is opentelemetry?
   greet Guna
   tell me a joke
   ask what is a span?
   ```

6. Copilot reads the matching `SKILL.md`, follows the run instruction, and executes the skill:
   ```bash
   # greet
   python3 .claude/skills/greet/index.py --name Guna --triggered-by claude

   # ask (2-step: run skill then send telemetry)
   python3 .claude/skills/ask/index.py --question "what is jaeger?" --triggered-by claude | tail -1
   python3 hooks/send_span.py --skill ask --input "..." --skill-output '...' --triggered-by claude --status ok
   ```

7. The skill prints its output and a span is exported to Jaeger automatically.

**Verify traces**

Open http://localhost:16686 → service `claude-skills` → Search.  
If Jaeger is not running, check `telemetry_spans.json` and run:
```bash
python view_spans.py --skill ask
```

### Direct CLI (debugging / CI)
```bash
python .claude/skills/greet/index.py --name Guna --triggered-by cli
python .claude/skills/joke/index.py --triggered-by cli
python .claude/skills/ask/index.py --question "what is jaeger?" --triggered-by cli
```
Output is JSON: `{"skill": "ask", "message": "...", "answer_source": "knowledge_base", ...}`.

---

## Telemetry approaches

### Approach 1 — OTel SDK (`greet`, `joke`)
Uses `hooks/otel_skill_tracer.py` with the OpenTelemetry Python SDK.  
Spans are exported via **OTLP gRPC** (port 4317). Parent/child linking is automatic.

```
skill.greet          ← parent span
  └── skill.read.greet   ← child span (SKILL.md read)
```

### Approach 2 — Stdlib HTTP (`ask`)
Uses `hooks/send_span.py` — **no OTel SDK required**, pure Python stdlib.  
Spans are exported via **OTLP HTTP** (port 4318) using `urllib`.  
SKILL.md instructs the agent to run the skill then call `send_span.py` with the captured output.

```
Step 1: python3 .claude/skills/ask/index.py --question "..."   → JSON output
Step 2: python3 hooks/send_span.py --skill-output '<json>'     → span to Jaeger
```

---

## Span attributes

### OTel SDK spans (`greet`, `joke`) — `trace_skill`

| Attribute | Example value | Notes |
|---|---|---|
| `skill.name` | `"greet"` | always |
| `skill.file_path` | `".claude/skills/greet/SKILL.md"` | always |
| `skill.triggered_by` | `"claude"` | always |
| `skill.session_id` | `"8e38203a-..."` | UUID per process |
| `skill.input` | `{"name": "Guna"}` | JSON string of arguments |
| `skill.status` | `"ok"` / `"error"` | always |
| `skill.duration_ms` | `3.14` | always |
| `skill.response` | `"{'skill': 'greet', ...}"` | first 1024 chars of return value |
| `skill.llm_response` | `"Hello, Guna! ..."` | `message` field from result dict |
| `skill.error` | `"SKILL.md not found"` | only on exception |

### OTel SDK spans (`greet`, `joke`) — `trace_skill_read`

| Attribute | Example value | Notes |
|---|---|---|
| `skill.name` | `"greet"` | always |
| `skill.file_path` | `".claude/skills/greet/SKILL.md"` | always |
| `skill.session_id` | `"8e38203a-..."` | same UUID as execution span |
| `skill.event` | `"read"` | always |
| `skill.triggered` | `true` / `false` | did the agent decide to use this skill? |
| `skill.query` | `"greet Guna"` | only if non-empty |

### Stdlib HTTP spans (`ask`) — `send_span.py`

| Attribute | Example value | Notes |
|---|---|---|
| `skill.name` | `"ask"` | always |
| `skill.file_path` | `".claude/skills/ask/SKILL.md"` | always |
| `skill.triggered_by` | `"claude"` | always |
| `skill.session_id` | `"4a385a5f-..."` | persisted in `/tmp` across calls |
| `skill.input` | `"what is jaeger?"` | user's original prompt |
| `skill.llm_response` | `"Jaeger is an open-source..."` | full answer from skill |
| `skill.answer_source` | `"knowledge_base"` / `"fallback"` | whether topic was found |
| `skill.question_matched` | `"jaeger"` | matched keyword from Q&A dict |
| `skill.model` | `"rule-based"` | skill type identifier |
| `skill.duration_ms` | `0.007` | real measured execution time |
| `skill.status` | `"ok"` / `"error"` | always |
| `skill.error` | `"..."` | only on failure |

### Process section (Jaeger) — `send_span.py`

| Field | Example value |
|---|---|
| `service.name` | `"claude-skills"` |
| `service.version` | `"1.0.0"` |
| `host.name` | `"my-macbook.local"` |
| `process.pid` | `"48053"` |
| `telemetry.sdk.name` | `"send_span.py"` |
| `telemetry.sdk.language` | `"python"` |

---

## Jaeger fallback — view spans offline

When Jaeger is unreachable, spans are written to `telemetry_spans.json` automatically.  
View them with:

```bash
python view_spans.py                   # all spans
python view_spans.py --skill ask       # filter by skill name
python view_spans.py --status error    # only errors
python view_spans.py --tail 10         # last 10 spans
```

---

## Adding a new skill

### Option A — OTel SDK (greet/joke pattern)

```python
# .claude/skills/myskill/index.py
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

### Option B — Stdlib HTTP (ask pattern)

```python
# .claude/skills/myskill/index.py — no OTel SDK needed
import time, json, argparse

def run_myskill_skill(arg: str) -> dict:
    start = time.time()
    result = {"skill": "myskill", "message": f"Result for {arg}",
              "model": "rule-based", "duration_ms": round((time.time()-start)*1000, 3)}
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arg", required=True)
    args = parser.parse_args()
    print(json.dumps(run_myskill_skill(args.arg)))
```

SKILL.md instructions for Option B:
```markdown
1. Run: `python3 .claude/skills/myskill/index.py --arg <value> --triggered-by claude | tail -1`
2. Run: `python3 hooks/send_span.py --skill myskill --input "<value>" --skill-output '<json from step 1>' --triggered-by claude --status ok`
3. Return the message to the user.
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` (OTel SDK) / `http://localhost:4318` (send_span.py) | OTLP endpoint for Jaeger |

---

## Project structure

```
.
├── .claude/
│   ├── settings.json
│   └── skills/
│       ├── greet/
│       │   ├── SKILL.md          # argument-hint, user-invocable, run instruction
│       │   └── index.py          # OTel SDK tracing via otel_skill_tracer.py
│       ├── joke/
│       │   ├── SKILL.md
│       │   └── index.py          # OTel SDK tracing via otel_skill_tracer.py
│       └── ask/
│           ├── SKILL.md          # 2-step: run index.py then send_span.py
│           └── index.py          # returns JSON with llm_response + metadata
├── hooks/
│   ├── otel_skill_tracer.py      # OTel SDK — singleton TracerProvider, trace_skill, trace_skill_read
│   └── send_span.py              # Stdlib HTTP — no SDK, posts OTLP JSON to Jaeger port 4318
├── test_spans.py                 # exercises all span types (greet, joke, ask, error)
├── view_spans.py                 # offline span viewer for telemetry_spans.json
├── telemetry_spans.json          # auto-created when Jaeger is unreachable
├── docker-compose.yml            # Jaeger all-in-one (ports 16686, 4317, 4318)
├── requirements.txt
└── README.md
```
