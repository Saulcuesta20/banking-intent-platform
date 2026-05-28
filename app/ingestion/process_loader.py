from __future__ import annotations

import json
from pathlib import Path

from app.models import ProcessDefinition


class ProcessDefinitionLoader:
    """Load fixed JSON process definitions from data/processes."""

    def load_directory(self, directory: Path) -> list[ProcessDefinition]:
        if not directory.exists():
            return []

        processes: list[ProcessDefinition] = []
        for path in sorted(directory.rglob("*.process.json")):
            processes.append(self.load_file(path))
        return sorted(processes, key=lambda item: item.process_id)

    def load_file(self, path: Path) -> ProcessDefinition:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProcessDefinition(**data)
