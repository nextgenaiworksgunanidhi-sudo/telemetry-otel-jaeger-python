"""Ask skill — answers technical questions. Telemetry sent via send_span.py."""
from __future__ import annotations

import time

_QA: dict[str, str] = {
    "opentelemetry": "OpenTelemetry is an open-source observability framework for collecting traces, metrics, and logs from applications.",
    "otel":          "OTel is shorthand for OpenTelemetry — a vendor-neutral standard for distributed tracing, metrics, and logs.",
    "jaeger":        "Jaeger is an open-source distributed tracing system used to monitor and troubleshoot microservices.",
    "span":          "A span represents a single unit of work in a trace — it has a name, start time, duration, and attributes.",
    "trace":         "A trace is a collection of spans that represent the full journey of a request across a distributed system.",
    "python":        "Python is a high-level, interpreted programming language known for readability and a rich ecosystem.",
    "claude":        "Claude is an AI assistant made by Anthropic, designed to be helpful, harmless, and honest.",
    "skill":         "A skill is a reusable capability defined in SKILL.md that Claude Code and VS Code Copilot can discover and invoke.",
}

_DEFAULT = "That's a great question! I don't have a specific answer for that topic in my knowledge base yet."


def run_ask_skill(question: str, triggered_by: str) -> dict[str, str | float]:
    """Return an answer dict with metadata for telemetry."""
    start = time.time()
    print(f"[ask] question={question!r}, triggered_by={triggered_by!r}")
    key = next((k for k in _QA if k in question.lower()), None)
    answer = _QA[key] if key else _DEFAULT
    return {
        "skill":            "ask",
        "message":          answer,
        "answer_source":    "knowledge_base" if key else "fallback",
        "question_matched": key or "",
        "model":            "rule-based",
        "duration_ms":      round((time.time() - start) * 1000, 3),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--question",     required=True, help="Question to answer")
    parser.add_argument("--triggered-by", default="cli")
    args = parser.parse_args()

    result = run_ask_skill(args.question, args.triggered_by)
    print(json.dumps(result))
