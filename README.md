# telemetry-otel-jaeger-python

Local Claude skill telemetry using OpenTelemetry + Jaeger.  
Each skill traces itself directly — no hooks required.  
Works with **Claude Code CLI** and **VS Code Copilot Chat** from the same `.claude/skills/` folder.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User (Claude Code / VS Code Copilot)         │
│                                                                      │
│   "greet Guna"  /  "tell me a joke"  /  "ask what is jaeger?"      │
│   "/health-check"  /  "health check the system"                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │  trigger phrase / slash command
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     .claude/skills/<name>/SKILL.md                  │
│                                                                      │
│   • Discovered automatically by Claude Code and VS Code Copilot     │
│   • Contains: description, argument-hint, run instructions          │
│   • Claude reads SKILL.md and follows the steps inside              │
└──────┬──────────────────────────────┬───────────────────────────────┘
       │                              │
       ▼                              ▼
┌─────────────────┐        ┌──────────────────────────┐
│   index.py      │        │   Direct curl POST        │
│  (greet, joke,  │        │   (health-check skill)    │
│   ask skills)   │        │                           │
│                 │        │  5 spans per run:         │
│  Runs skill     │        │  • health-check.start     │
│  logic, returns │        │  • health-check.cpu       │
│  JSON output    │        │  • health-check.memory    │
└──────┬──────────┘        │  • health-check.disk      │
       │                   │  • health-check.summary   │
       ▼                   └────────────┬──────────────┘
┌─────────────────────────┐            │
│   hooks/                │            │  curl POST
│                         │            │  /v1/traces
│  otel_skill_tracer.py   │            │
│  (greet, joke)          │            │
│  → OTLP gRPC :4317      │            │
│                         │            │
│  send_span.py           │            │
│  (ask)                  │            │
│  → OTLP HTTP :4318      │            │
└──────────┬──────────────┘            │
           │                           │
           └──────────┬────────────────┘
                      │  OTLP (gRPC or HTTP)
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Jaeger  (docker compose)                        │
│                                                                      │
│   UI  →  http://localhost:16686                                      │
│   OTLP gRPC  →  :4317   (OTel SDK)                                  │
│   OTLP HTTP  →  :4318   (send_span.py + health-check curl)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Skills

| Skill | Trigger | Telemetry approach | Spans |
|---|---|---|---|
| `greet` | "greet Guna", "hello Alice" | OTel SDK (`otel_skill_tracer.py`) → gRPC | 2 (parent + child) |
| `joke`  | "tell me a joke", "make me laugh" | OTel SDK (`otel_skill_tracer.py`) → gRPC | 2 (parent + child) |
| `ask`   | "ask what is jaeger?", "what is a span?" | Stdlib HTTP (`send_span.py`) → HTTP | 1 |
| `health-check` | "/health-check", "health check the system" | Direct `curl` POST → HTTP | 5 (one per step) |

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

## Invoking skills

### Claude Code CLI
```bash
cd telemetry-otel-jaeger-python
claude
# type: greet Guna
# type: ask what is opentelemetry?
# type: /health-check
```

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

4. Make sure the chat mode is set to **Agent** (not Ask or Edit).

5. Use a slash command or natural language:
   ```
   /greet Guna
   /joke
   /ask what is opentelemetry?
   /health-check
   health check the system
   ```

6. Open **http://localhost:16686** → service `claude-skills` → Search to view traces.

---

## Telemetry approaches

### Approach 1 — OTel SDK (`greet`, `joke`)
Uses `hooks/otel_skill_tracer.py` with the OpenTelemetry Python SDK.  
Spans are exported via **OTLP gRPC** (port 4317). Parent/child linking is automatic.

```
skill.greet              ← parent span
  └── skill.read.greet  ← child span (SKILL.md read)
```

### Approach 2 — Stdlib HTTP (`ask`)
Uses `hooks/send_span.py` — no OTel SDK required, pure Python stdlib.  
Spans are exported via **OTLP HTTP** (port 4318) using `urllib`.

```
Step 1: python3 .claude/skills/ask/index.py --question "..."   → JSON output
Step 2: python3 hooks/send_span.py --skill-output '<json>'     → span to Jaeger
```

### Approach 3 — Direct curl (`health-check`)
No Python SDK or helper script — SKILL.md instructs Claude to POST directly to Jaeger using `curl`.  
All 5 spans share the same `traceId` so they appear as one linked trace.

```
/health-check
  curl POST → health-check.start    (skill.input = user prompt)
  curl POST → health-check.cpu      (system.cpu_usage)
  curl POST → health-check.memory   (system.memory_free_pages)
  curl POST → health-check.disk     (system.disk_used_percent)
  curl POST → health-check.summary  (skill.input + skill.llm_response)
```

OS detection is built in — macOS/Linux uses `bash` + `awk`, Windows uses `PowerShell` + `Get-WmiObject`.

---

## Span attributes

### OTel SDK spans (`greet`, `joke`)

| Attribute | Example |
|---|---|
| `skill.name` | `"greet"` |
| `skill.triggered_by` | `"claude"` |
| `skill.session_id` | `"8e38203a-..."` |
| `skill.input` | `{"name": "Guna"}` |
| `skill.status` | `"ok"` / `"error"` |
| `skill.llm_response` | `"Hello, Guna! ..."` |

### Stdlib HTTP spans (`ask`)

| Attribute | Example |
|---|---|
| `skill.name` | `"ask"` |
| `skill.input` | `"what is jaeger?"` |
| `skill.llm_response` | `"Jaeger is an open-source..."` |
| `skill.answer_source` | `"knowledge_base"` / `"fallback"` |
| `skill.duration_ms` | `0.007` |
| `skill.status` | `"ok"` / `"error"` |

### Direct curl spans (`health-check`)

| Attribute | Spans | Example |
|---|---|---|
| `skill.name` | all | `"health-check"` |
| `skill.step` | all | `"cpu"`, `"memory"`, `"disk"`, `"summary"` |
| `skill.input` | all | `"/health-check"` |
| `skill.triggered_by` | all | `"claude"` |
| `system.cpu_usage` | cpu | `"9.11%"` |
| `system.memory_free_pages` | memory | `"3922"` |
| `system.disk_used_percent` | disk | `"14%"` |
| `skill.llm_response` | summary only | `"CPU: 9.11%, Memory: 3922 free pages, Disk: 14% used"` |
| `skill.result` | summary only | `"all-checks-complete"` |

---

## Onboarding a new skill

Follow these steps to add a new skill to the project.

### Step 1 — Create the skill folder

```bash
mkdir .claude/skills/myskill
```

### Step 2 — Choose a telemetry approach

| Approach | Best for | Dependencies |
|---|---|---|
| A — OTel SDK | Rich parent/child traces | `opentelemetry-sdk` (already in requirements.txt) |
| B — Stdlib HTTP | Simple single span, no SDK | None — pure Python stdlib |
| C — Direct curl | No Python script needed, multiple spans | None — just `curl` |

### Step 3 — Create index.py (Approach A or B only)

**Approach A — OTel SDK:**
```python
# .claude/skills/myskill/index.py
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from hooks.otel_skill_tracer import trace_skill, trace_skill_read

_SKILL_MD = Path(__file__).parent / "SKILL.md"

def run_myskill_skill(triggered_by: str) -> dict[str, str]:
    def _execute() -> dict[str, str]:
        trace_skill_read("myskill", str(_SKILL_MD), "", triggered=True)
        return {"skill": "myskill", "message": "Hello from myskill!"}

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
    print(json.dumps(run_myskill_skill(args.triggered_by)))
```

**Approach B — Stdlib HTTP:**
```python
# .claude/skills/myskill/index.py
from __future__ import annotations
import time, json, argparse

def run_myskill_skill(arg: str) -> dict[str, str | float]:
    start = time.time()
    return {
        "skill":       "myskill",
        "message":     f"Result for {arg}",
        "model":       "rule-based",
        "duration_ms": round((time.time() - start) * 1000, 3),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arg", required=True)
    args = parser.parse_args()
    print(json.dumps(run_myskill_skill(args.arg)))
```

### Step 4 — Create SKILL.md

**Approach A — OTel SDK:**
```markdown
---
name: myskill
description: What this skill does. Use when user says myskill <arg>.
argument-hint: <arg>
user-invocable: true
---

## Instructions

Run: `python3 .claude/skills/myskill/index.py --triggered-by claude`

Return the `message` field from the JSON output to the user.
```

**Approach B — Stdlib HTTP:**
```markdown
---
name: myskill
description: What this skill does. Use when user says myskill <arg>.
argument-hint: <arg>
user-invocable: true
---

## Instructions

1. Run the skill:
   `python3 .claude/skills/myskill/index.py --arg "<arg>" --triggered-by claude | tail -1`

2. Send telemetry:
   `python3 hooks/send_span.py --skill myskill --input "<arg>" --skill-output '<json from step 1>' --triggered-by claude --status ok`

3. Return the `message` field to the user.
```

**Approach C — Direct curl:**
```markdown
---
name: myskill
description: What this skill does. Use when user says myskill.
argument-hint: (no arguments)
user-invocable: true
---

## Instructions

Replace `<USER_PROMPT>` with the exact message the user typed, then run:

```bash
TRACE_ID=$(python3 -c "import os; print(os.urandom(16).hex())")
ENDPOINT="http://localhost:4318/v1/traces"
USER_PROMPT="<USER_PROMPT>"

send_span() {
  local SPAN_NAME="$1" STEP="$2" ATTR_KEY="$3" ATTR_VAL="$4"
  local SPAN_ID TS PAYLOAD
  SPAN_ID=$(python3 -c "import os; print(os.urandom(8).hex())")
  TS=$(python3 -c "import time; print(time.time_ns())")
  PAYLOAD=$(python3 - <<PYEOF
import json
print(json.dumps({"resourceSpans":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"claude-skills"}}]},"scopeSpans":[{"scope":{"name":"myskill"},"spans":[{"traceId":"$TRACE_ID","spanId":"$SPAN_ID","name":"$SPAN_NAME","kind":1,"startTimeUnixNano":"$TS","endTimeUnixNano":"$TS","attributes":[{"key":"skill.name","value":{"stringValue":"myskill"}},{"key":"skill.step","value":{"stringValue":"$STEP"}},{"key":"skill.input","value":{"stringValue":"$USER_PROMPT"}},{"key":"$ATTR_KEY","value":{"stringValue":"$ATTR_VAL"}}],"status":{"code":1}}]}]}]}))
PYEOF
)
  curl -s -o /dev/null -w "  curl POST [$SPAN_NAME]: HTTP %{http_code}\n" \
    -X POST "$ENDPOINT" -H "Content-Type: application/json" -d "$PAYLOAD"
}

send_span "myskill.start" "start" "skill.triggered_by" "claude"
# ... add more steps as needed
```
```

### Step 5 — Test locally

```bash
# Direct CLI test (Approach A or B)
python3 .claude/skills/myskill/index.py --triggered-by cli

# Test via Claude Code
claude
# type: myskill <arg>
```

### Step 6 — Verify in Jaeger

```
http://localhost:16686
→ Service: claude-skills
→ Operation: skill.myskill (or myskill.*)
→ Find Traces
```

### Step 7 — Commit and push

```bash
git add .claude/skills/myskill/
git commit -m "feat: add myskill with <approach> telemetry"
git push origin main
```

---

## Jaeger fallback — view spans offline

When Jaeger is unreachable, `send_span.py` spans are written to `telemetry_spans.json` automatically.  
*(Note: direct curl spans from `health-check` are not saved to file when Jaeger is unreachable.)*

```bash
python view_spans.py                   # all spans
python view_spans.py --skill ask       # filter by skill name
python view_spans.py --status error    # only errors
python view_spans.py --tail 10         # last 10 spans
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` (OTel SDK) / `http://localhost:4318` (send_span.py + curl) | OTLP endpoint for Jaeger |

---

## Project structure

```
.
├── .claude/
│   ├── settings.json
│   └── skills/
│       ├── greet/
│       │   ├── SKILL.md          # OTel SDK — 2 spans (parent + child)
│       │   └── index.py
│       ├── joke/
│       │   ├── SKILL.md          # OTel SDK — 2 spans (parent + child)
│       │   └── index.py
│       ├── ask/
│       │   ├── SKILL.md          # Stdlib HTTP — 1 span via send_span.py
│       │   └── index.py
│       └── health-check/
│           └── SKILL.md          # Direct curl — 5 spans, cross-platform (macOS/Linux/Windows)
├── hooks/
│   ├── otel_skill_tracer.py      # OTel SDK tracer (greet, joke)
│   └── send_span.py              # Stdlib OTLP HTTP sender (ask)
├── test_spans.py                 # Exercises all span types
├── view_spans.py                 # Offline span viewer for telemetry_spans.json
├── telemetry_spans.json          # Auto-created when Jaeger is unreachable
├── docker-compose.yml            # Jaeger all-in-one (ports 16686, 4317, 4318)
├── requirements.txt
└── README.md
```
