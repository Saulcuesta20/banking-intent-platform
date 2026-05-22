from __future__ import annotations

import sys
from pathlib import Path

from app.cli import app


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.cli.ingest <source_path>", file=sys.stderr)
        raise SystemExit(2)

    source = Path(sys.argv[1])
    app(["ingest", str(source)])
