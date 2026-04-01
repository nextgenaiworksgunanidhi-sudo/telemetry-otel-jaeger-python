"""
send_span.py — stdlib-only OTLP HTTP span sender. No OTel SDK required.
Called directly from SKILL.md after the skill runs.

Usage:
    python3 hooks/send_span.py \
        --skill ask \
        --input "what is opentelemetry?" \
        --skill-output '{"message":"OTel is...","answer_source":"knowledge_base","duration_ms":2.1}' \
        --triggered-by claude \
        --status ok \
        --file-path .claude/skills/ask/SKILL.md
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import time
import uuid
from pathlib import Path
from urllib import error as urllib_error
from urllib import request

_ENDPOINT     = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
_SPANS_FILE   = Path(__file__).parent.parent / "telemetry_spans.json"
_SESSION_FILE = Path("/tmp/claude-skills-session-id")
_SERVICE      = "claude-skills"
_VERSION      = "1.0.0"


# ── Session ID ────────────────────────────────────────────────────────────────

def _get_session_id() -> str:
    if _SESSION_FILE.exists():
        return _SESSION_FILE.read_text().strip()
    sid = str(uuid.uuid4())
    _SESSION_FILE.write_text(sid)
    return sid


# ── Connectivity probe ────────────────────────────────────────────────────────

def _is_reachable(endpoint: str) -> bool:
    try:
        host = endpoint.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(endpoint.rsplit(":", 1)[-1])
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


# ── Skill output parser ───────────────────────────────────────────────────────

def _parse_skill_output(raw: str) -> dict[str, str]:
    """Extract span attributes from index.py JSON output."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    mapping = {
        "message":          "skill.llm_response",
        "answer_source":    "skill.answer_source",
        "question_matched": "skill.question_matched",
        "model":            "skill.model",
        "duration_ms":      "skill.duration_ms",
    }
    return {v: data[k] for k, v in mapping.items() if k in data}


# ── OTLP payload builders ─────────────────────────────────────────────────────

def _build_attributes(args: argparse.Namespace, session_id: str, extra: dict) -> list[dict]:
    base = [
        {"key": "skill.name",         "value": {"stringValue": args.skill}},
        {"key": "skill.triggered_by", "value": {"stringValue": args.triggered_by}},
        {"key": "skill.session_id",   "value": {"stringValue": session_id}},
        {"key": "skill.status",       "value": {"stringValue": args.status}},
    ]
    if args.file_path:
        base.append({"key": "skill.file_path", "value": {"stringValue": args.file_path}})
    if args.input:
        base.append({"key": "skill.input", "value": {"stringValue": args.input}})
    if args.error:
        base.append({"key": "skill.error", "value": {"stringValue": args.error}})
    for key, val in extra.items():
        vtype = "doubleValue" if isinstance(val, (int, float)) else "stringValue"
        base.append({"key": key, "value": {vtype: val}})
    return base


def _build_resource_attrs() -> list[dict]:
    return [
        {"key": "service.name",            "value": {"stringValue": _SERVICE}},
        {"key": "service.version",         "value": {"stringValue": _VERSION}},
        {"key": "host.name",               "value": {"stringValue": socket.gethostname()}},
        {"key": "process.pid",             "value": {"stringValue": str(os.getpid())}},
        {"key": "telemetry.sdk.name",      "value": {"stringValue": "send_span.py"}},
        {"key": "telemetry.sdk.language",  "value": {"stringValue": "python"}},
    ]


def _build_span(args: argparse.Namespace, session_id: str, extra: dict,
                start_ns: int, end_ns: int) -> dict:
    return {
        "traceId":           os.urandom(16).hex(),
        "spanId":            os.urandom(8).hex(),
        "name":              f"skill.{args.skill}",
        "kind":              1,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano":   str(end_ns),
        "attributes":        _build_attributes(args, session_id, extra),
        "status":            {"code": 2 if args.status == "error" else 1},
    }


def _build_payload(span: dict) -> dict:
    return {
        "resourceSpans": [{
            "resource":   {"attributes": _build_resource_attrs()},
            "scopeSpans": [{"scope": {"name": _SERVICE}, "spans": [span]}],
        }]
    }


# ── Export ────────────────────────────────────────────────────────────────────

def _send_to_jaeger(payload: dict, endpoint: str) -> bool:
    url  = f"{endpoint}/v1/traces"
    data = json.dumps(payload).encode()
    req  = request.Request(url, data=data,
                           headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 201, 204)
    except (urllib_error.URLError, OSError):
        return False


def _save_to_file(span: dict) -> None:
    attrs = {a["key"]: list(a["value"].values())[0] for a in span["attributes"]}
    record = {
        "trace_id":      span["traceId"],
        "span_id":       span["spanId"],
        "operation":     span["name"],
        "start_time_ms": int(span["startTimeUnixNano"]) // 1_000_000,
        "end_time_ms":   int(span["endTimeUnixNano"])   // 1_000_000,
        "duration_ms":   attrs.pop("skill.duration_ms", 0),
        "status":        "OK" if span["status"]["code"] == 1 else "ERROR",
        "attributes":    attrs,
    }
    existing = json.loads(_SPANS_FILE.read_text()) if _SPANS_FILE.exists() else []
    existing.append(record)
    _SPANS_FILE.write_text(json.dumps(existing, indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Send a span to Jaeger via OTLP HTTP")
    parser.add_argument("--skill",        required=True,    help="Skill name")
    parser.add_argument("--input",        default="",       help="User prompt")
    parser.add_argument("--skill-output", default="",       help="Raw JSON from index.py")
    parser.add_argument("--triggered-by", default="claude", help="Caller identity")
    parser.add_argument("--status",       default="ok",     choices=["ok", "error"])
    parser.add_argument("--file-path",    default="",       help="Path to SKILL.md")
    parser.add_argument("--error",        default="",       help="Error message")
    args = parser.parse_args()

    session_id = _get_session_id()
    extra      = _parse_skill_output(args.skill_output)
    end_ns     = time.time_ns()
    dur_ms     = extra.get("skill.duration_ms", 0)
    start_ns   = end_ns - int(float(dur_ms) * 1_000_000) if dur_ms else end_ns - 1_000_000

    span    = _build_span(args, session_id, extra, start_ns, end_ns)
    payload = _build_payload(span)

    if _is_reachable(_ENDPOINT):
        ok = _send_to_jaeger(payload, _ENDPOINT)
        print(f"[send_span] Jaeger {'ok' if ok else 'export failed'} — {_ENDPOINT}")
    else:
        _save_to_file(span)
        print(f"[send_span] Jaeger unreachable — saved to {_SPANS_FILE.name}")


if __name__ == "__main__":
    main()
