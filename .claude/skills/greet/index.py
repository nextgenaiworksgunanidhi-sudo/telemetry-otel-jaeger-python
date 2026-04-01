"""Greet skill — says hello to a named person with OTel tracing."""
from __future__ import annotations

import sys
from pathlib import Path

# Resolve project root so hooks package is importable regardless of cwd
_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_ROOT))

from hooks.otel_skill_tracer import trace_skill, trace_skill_read  # noqa: E402

_SKILL_MD = Path(__file__).parent / "SKILL.md"


def run_greet_skill(name: str, triggered_by: str) -> dict[str, str]:
    """Return a greeting dict; the entire execution is captured in a span."""

    def _execute() -> dict[str, str]:
        trace_skill_read("greet", str(_SKILL_MD), f"greet {name}", triggered=True)
        print(f"[greet] Running skill for name={name!r}, triggered_by={triggered_by!r}")
        skill_md = _SKILL_MD.read_text()  # noqa: F841 — confirms file is accessible
        return {
            "skill": "greet",
            "message": f"Hello, {name}! Greetings from Claude Skills with OTel tracing.",
        }

    return trace_skill(  # type: ignore[return-value]
        skill_name="greet",
        skill_path=str(_SKILL_MD),
        triggered_by=triggered_by,
        fn=_execute,
        inputs={"name": name},
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Name to greet")
    parser.add_argument("--triggered-by", default="cli", help="Caller identity")
    args = parser.parse_args()

    result = run_greet_skill(args.name, args.triggered_by)
    print(json.dumps(result))
