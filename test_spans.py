"""
test_spans.py — exercises all span types against a running Jaeger instance.

Run:
    docker compose up -d
    python test_spans.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

from hooks.otel_skill_tracer import trace_skill, trace_skill_read, _get_provider  # noqa: E402


def _import_skills() -> tuple:
    """Import skill runners via importlib — handles the dot in .claude path."""
    import importlib.util

    def load(rel: str) -> object:
        spec = importlib.util.spec_from_file_location("_skill", _ROOT / rel)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    greet_mod = load(".claude/skills/greet/index.py")
    joke_mod = load(".claude/skills/joke/index.py")
    return greet_mod.run_greet_skill, joke_mod.run_joke_skill


def main() -> None:
    run_greet, run_joke = _import_skills()

    # 1. SKILL.md read — greet (triggered)
    print("→ trace_skill_read: greet (triggered=True)")
    trace_skill_read(
        "greet",
        ".claude/skills/greet/SKILL.md",
        "greet Guna",
        triggered=True,
    )

    # 2. SKILL.md read — joke (not triggered)
    print("→ trace_skill_read: joke (triggered=False)")
    trace_skill_read(
        "joke",
        ".claude/skills/joke/SKILL.md",
        "what is the weather",
        triggered=False,
    )

    # 3. Successful greet span
    print("→ run_greet_skill: Guna / test runner")
    result = run_greet("Guna", "test runner")
    print(f"   {result['message']}")

    # 4. Successful joke span
    print("→ run_joke_skill: test runner")
    result = run_joke("test runner", {})
    print(f"   {result['message']}")

    # 5. Error span — simulated missing xlsx skill
    print("→ trace_skill: xlsx (error simulation)")
    try:
        trace_skill(
            skill_name="xlsx",
            skill_path=".claude/skills/xlsx/SKILL.md",
            triggered_by="test runner",
            fn=lambda: (_ for _ in ()).throw(Exception("SKILL.md not found")),
        )
    except Exception as exc:
        print(f"   caught expected error: {exc}")

    # Final flush to ensure nothing is lost
    _get_provider().force_flush()
    print("\nDone! Open http://localhost:16686 → service: claude-skills → Search")


if __name__ == "__main__":
    main()
