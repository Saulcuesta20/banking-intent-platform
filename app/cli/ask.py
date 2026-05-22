from __future__ import annotations

import sys

from app.cli import app


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m app.cli.ask "question"', file=sys.stderr)
        raise SystemExit(2)

    question = " ".join(sys.argv[1:])
    app(["ask", question])
