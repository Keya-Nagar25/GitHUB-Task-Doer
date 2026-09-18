"""Throwaway terminal demo: type plain English, see the resolved action.

Validates the offline classifier end-to-end before any UI exists.
Run from backend/: python scripts/cli_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.resolve import ResolveRequest, resolve  # noqa: E402


def main() -> None:
    print("GitHub Task Doer -- offline NLU demo. Type a request, or 'quit' to exit.\n")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() in {"quit", "exit"}:
            break

        response = resolve(ResolveRequest(text=text))
        if response.status == "resolved":
            action = response.resolved_action
            print(f"  action: {action.action.value}")
            print(f"  params: {action.params}")
            print(f"  explanation: {action.explanation}")
            print(f"  destructive: {action.destructive}  confidence: {action.confidence}")
            if action.requires_double_confirmation:
                print("  ** requires double confirmation **")
            if action.clarifying_question:
                print(f"  note: {action.clarifying_question}")
        else:
            print(f"  [{response.status}] {response.message}")
        print()


if __name__ == "__main__":
    main()
