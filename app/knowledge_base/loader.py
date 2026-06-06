from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.knowledge_base.models import AssetRegistryConfig


class AssetRegistryLoader:
    """Load enterprise asset type configuration from YAML."""

    def load_file(self, path: Path) -> AssetRegistryConfig:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Asset registry YAML must contain an object: {path}")
        return AssetRegistryConfig.model_validate(payload)

    def load_dict(self, payload: dict[str, Any]) -> AssetRegistryConfig:
        return AssetRegistryConfig.model_validate(payload)

