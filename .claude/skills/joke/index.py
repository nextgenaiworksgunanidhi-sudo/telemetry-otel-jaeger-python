"""Joke skill — returns a random programming joke with OTel tracing."""
from __future__ import annotations

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_ROOT))

from hooks.otel_skill_tracer import trace_skill, trace_skill_read  # noqa: E402

_SKILL_MD = Path(__file__).parent / "SKILL.md"

_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "A SQL query walks into a bar, walks up to two tables and asks: 'Can I join you?'",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None — it's a hardware problem.",
    "There are 10 types of people: those who understand binary and those who don't.",
]


def run_joke_skill(triggered_by: str, context: dict) -> dict[str, str]:  # type: ignore[type-arg]
    """Return a random joke dict; the entire execution is captured in a span."""

    def _execute() -> dict[str, str]:
        trace_skill_read("joke", str(_SKILL_MD), "tell me a joke", triggered=True)
        print(f"[joke] Running skill, triggered_by={triggered_by!r}")
        _SKILL_MD.read_text()  # confirms file is accessible
        joke = random.choice(_JOKES)
        return {"skill": "joke", "message": joke}

    return trace_skill(  # type: ignore[return-value]
        skill_name="joke",
        skill_path=str(_SKILL_MD),
        triggered_by=triggered_by,
        fn=_execute,
        inputs={"triggered_by": triggered_by},
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--triggered-by", default="cli", help="Caller identity")
    args = parser.parse_args()

    result = run_joke_skill(args.triggered_by, {})
    print(json.dumps(result))
