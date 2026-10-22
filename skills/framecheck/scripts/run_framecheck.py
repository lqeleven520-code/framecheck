"""Run the source bundled with this skill, without downloading a FrameCheck runtime."""
from __future__ import annotations

import sys


def run() -> int:
    try:
        from framecheck.cli import main
    except ModuleNotFoundError as exc:
        if exc.name in {"numpy", "PIL"}:
            print("Missing Python dependencies. Install this skill's requirements.txt in your chosen "
                  "virtual environment, then run this helper with that environment's Python.", file=sys.stderr)
            return 2
        raise
    return main()


if __name__ == "__main__":
    raise SystemExit(run())
