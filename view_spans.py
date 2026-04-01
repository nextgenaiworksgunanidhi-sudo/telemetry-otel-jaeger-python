"""
view_spans.py — pretty-print telemetry_spans.json when Jaeger is unavailable.

Usage:
    python view_spans.py                 # show all spans
    python view_spans.py --skill greet   # filter by skill name
    python view_spans.py --status error  # filter by status (ok / error)
    python view_spans.py --tail 10       # show last N spans
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

_SPANS_FILE = Path(__file__).parent / "telemetry_spans.json"

_COL = {
    "time":        14,
    "trace_id":    14,
    "operation":   26,
    "status":       6,
    "duration_ms":  9,
    "input":       22,
    "llm_response": 40,
}


def _load_spans() -> list[dict]:
    if not _SPANS_FILE.exists():
        print(f"[view_spans] File not found: {_SPANS_FILE}")
        return []
    return json.loads(_SPANS_FILE.read_text())


def _fmt_time(ms: int) -> str:
    if not ms:
        return "-"
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%H:%M:%S.%f")[:-3]


def _truncate(value: str, width: int) -> str:
    return value if len(value) <= width else value[: width - 1] + "…"


def _header() -> str:
    parts = [f"{'TIME':<{_COL['time']}}",
             f"{'TRACE ID':<{_COL['trace_id']}}",
             f"{'OPERATION':<{_COL['operation']}}",
             f"{'STATUS':<{_COL['status']}}",
             f"{'DUR(ms)':<{_COL['duration_ms']}}",
             f"{'INPUT':<{_COL['input']}}",
             f"{'LLM RESPONSE / ERROR':<{_COL['llm_response']}}"]
    line = "  ".join(parts)
    return f"{line}\n{'─' * len(line)}"


def _row(span: dict) -> str:
    attrs = span.get("attributes", {})
    status = attrs.get("skill.status", "-")
    dur = attrs.get("skill.duration_ms")
    llm = attrs.get("skill.llm_response") or attrs.get("skill.error", "-")

    parts = [
        f"{_truncate(_fmt_time(span.get('start_time_ms', 0)), _COL['time']):<{_COL['time']}}",
        f"{_truncate(span.get('trace_id', '-')[:12], _COL['trace_id']):<{_COL['trace_id']}}",
        f"{_truncate(span.get('operation', '-'), _COL['operation']):<{_COL['operation']}}",
        f"{_truncate(status, _COL['status']):<{_COL['status']}}",
        f"{_truncate(f'{dur:.1f}' if dur else '-', _COL['duration_ms']):<{_COL['duration_ms']}}",
        f"{_truncate(attrs.get('skill.input', '-'), _COL['input']):<{_COL['input']}}",
        f"{_truncate(llm, _COL['llm_response']):<{_COL['llm_response']}}",
    ]
    return "  ".join(parts)


def _summary(spans: list[dict]) -> str:
    total = len(spans)
    ok = sum(1 for s in spans if s.get("attributes", {}).get("skill.status") == "ok")
    errors = sum(1 for s in spans if s.get("attributes", {}).get("skill.status") == "error")
    reads = sum(1 for s in spans if s.get("attributes", {}).get("skill.event") == "read")
    return f"\nTotal: {total}  ok: {ok}  error: {errors}  reads: {reads}"


def _filter_spans(
    spans: list[dict],
    skill: str | None,
    status: str | None,
    tail: int | None,
) -> list[dict]:
    if skill:
        spans = [s for s in spans if s.get("attributes", {}).get("skill.name") == skill]
    if status:
        spans = [s for s in spans if s.get("attributes", {}).get("skill.status") == status]
    if tail:
        spans = spans[-tail:]
    return spans


def main() -> None:
    parser = argparse.ArgumentParser(description="View telemetry_spans.json")
    parser.add_argument("--skill",  help="Filter by skill name (e.g. greet)")
    parser.add_argument("--status", help="Filter by status: ok or error")
    parser.add_argument("--tail",   type=int, help="Show last N spans")
    args = parser.parse_args()

    spans = _load_spans()
    if not spans:
        return

    spans = _filter_spans(spans, args.skill, args.status, args.tail)
    if not spans:
        print("No spans match the filter.")
        return

    print(f"\nSource: {_SPANS_FILE}  ({len(spans)} span(s) shown)\n")
    print(_header())
    for span in spans:
        print(_row(span))
    print(_summary(spans))


if __name__ == "__main__":
    main()
