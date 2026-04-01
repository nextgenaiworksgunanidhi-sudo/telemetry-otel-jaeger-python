---
name: health-check
description: Check system health (CPU, memory, disk) and send a Jaeger span via curl for each step. Use when user says /health-check or health-check.
argument-hint: (no arguments needed)
user-invocable: true
---

## Instructions

Before running the script, substitute the placeholder values:
- Replace `<USER_PROMPT>` with the exact message the user typed (e.g. `/health-check` or `run health check`)
- Replace `<LLM_RESPONSE>` after collecting metrics with the summary string: `CPU: <cpu_value>, Memory: <mem_value> free pages, Disk: <disk_value> used`

Then run the following bash script as a single command. It checks system health and sends one curl POST to Jaeger per step. All spans share the same `traceId`.

```bash
TRACE_ID=$(python3 -c "import os; print(os.urandom(16).hex())")
ENDPOINT="http://localhost:4318/v1/traces"
USER_PROMPT="<USER_PROMPT>"

echo "Health Check — Trace ID: $TRACE_ID"
echo ""

send_span() {
  local SPAN_NAME="$1" STEP="$2" ATTR_KEY="$3" ATTR_VAL="$4"
  local SPAN_ID TS PAYLOAD
  SPAN_ID=$(python3 -c "import os; print(os.urandom(8).hex())")
  TS=$(python3 -c "import time; print(time.time_ns())")

  PAYLOAD=$(python3 - <<PYEOF
import json
print(json.dumps({
  "resourceSpans": [{
    "resource": {"attributes": [
      {"key": "service.name",    "value": {"stringValue": "claude-skills"}},
      {"key": "service.version", "value": {"stringValue": "1.0.0"}}
    ]},
    "scopeSpans": [{
      "scope": {"name": "health-check"},
      "spans": [{
        "traceId":           "$TRACE_ID",
        "spanId":            "$SPAN_ID",
        "name":              "$SPAN_NAME",
        "kind":              1,
        "startTimeUnixNano": "$TS",
        "endTimeUnixNano":   "$TS",
        "attributes": [
          {"key": "skill.name",         "value": {"stringValue": "health-check"}},
          {"key": "skill.step",         "value": {"stringValue": "$STEP"}},
          {"key": "skill.triggered_by", "value": {"stringValue": "claude"}},
          {"key": "skill.input",        "value": {"stringValue": "$USER_PROMPT"}},
          {"key": "$ATTR_KEY",          "value": {"stringValue": "$ATTR_VAL"}}
        ],
        "status": {"code": 1}
      }]
    }]
  }]
}))
PYEOF
)

  curl -s -o /dev/null -w "  curl POST [$SPAN_NAME]: HTTP %{http_code}\n" \
    -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD"
}

send_summary_span() {
  local SPAN_ID TS PAYLOAD
  SPAN_ID=$(python3 -c "import os; print(os.urandom(8).hex())")
  TS=$(python3 -c "import time; print(time.time_ns())")
  local LLM_RESPONSE="$1"

  PAYLOAD=$(python3 - <<PYEOF
import json
print(json.dumps({
  "resourceSpans": [{
    "resource": {"attributes": [
      {"key": "service.name",    "value": {"stringValue": "claude-skills"}},
      {"key": "service.version", "value": {"stringValue": "1.0.0"}}
    ]},
    "scopeSpans": [{
      "scope": {"name": "health-check"},
      "spans": [{
        "traceId":           "$TRACE_ID",
        "spanId":            "$SPAN_ID",
        "name":              "health-check.summary",
        "kind":              1,
        "startTimeUnixNano": "$TS",
        "endTimeUnixNano":   "$TS",
        "attributes": [
          {"key": "skill.name",         "value": {"stringValue": "health-check"}},
          {"key": "skill.step",         "value": {"stringValue": "summary"}},
          {"key": "skill.triggered_by", "value": {"stringValue": "claude"}},
          {"key": "skill.input",        "value": {"stringValue": "$USER_PROMPT"}},
          {"key": "skill.llm_response", "value": {"stringValue": "$LLM_RESPONSE"}},
          {"key": "skill.result",       "value": {"stringValue": "all-checks-complete"}}
        ],
        "status": {"code": 1}
      }]
    }]
  }]
}))
PYEOF
)

  curl -s -o /dev/null -w "  curl POST [health-check.summary]: HTTP %{http_code}\n" \
    -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD"
}

# ── Step 1: Start ─────────────────────────────────────────────────────────────
echo "[1/5] health-check.start"
send_span "health-check.start" "start" "skill.triggered_by" "claude"

# ── Step 2: CPU ───────────────────────────────────────────────────────────────
echo "[2/5] health-check.cpu"
CPU=$(top -l 1 -n 0 2>/dev/null | grep "CPU usage" | awk '{print $3}' || echo "N/A")
send_span "health-check.cpu" "cpu" "system.cpu_usage" "$CPU"
echo "  CPU usage: $CPU"

# ── Step 3: Memory ────────────────────────────────────────────────────────────
echo "[3/5] health-check.memory"
MEM=$(vm_stat 2>/dev/null | grep "Pages free" | awk '{print $3}' | tr -d '.' || echo "N/A")
send_span "health-check.memory" "memory" "system.memory_free_pages" "$MEM"
echo "  Free memory pages: $MEM"

# ── Step 4: Disk ──────────────────────────────────────────────────────────────
echo "[4/5] health-check.disk"
DISK=$(df -h / 2>/dev/null | tail -1 | awk '{print $5}' || echo "N/A")
send_span "health-check.disk" "disk" "system.disk_used_percent" "$DISK"
echo "  Disk used: $DISK"

# ── Step 5: Summary (with user prompt + LLM response) ─────────────────────────
echo "[5/5] health-check.summary"
LLM_RESPONSE="CPU: $CPU, Memory: $MEM free pages, Disk: $DISK used"
send_summary_span "$LLM_RESPONSE"
echo "  Summary: $LLM_RESPONSE"

echo ""
echo "Done. View in Jaeger: http://localhost:16686"
echo "Search by Service: claude-skills | Operation: health-check.*"
```

If any curl call returns a non-200 status, note the step and report it to the user. Report the Trace ID and the Jaeger URL at the end.

## Example triggers

- `/health-check`
- `health-check`
- `run health check`
