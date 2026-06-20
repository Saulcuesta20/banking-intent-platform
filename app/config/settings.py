from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from pydantic import Field, ConfigDict

try:
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover
    BaseSettings = None
from dotenv import load_dotenv

load_dotenv()


if BaseSettings is not None:
    class Settings(BaseSettings):
        project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
        asset_registry_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "asset_registry" / "asset_types.yaml")
        agent_catalog_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "agents" / "agent_catalog.yaml")
        agent_skills_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "agents" / "skills")
        relation_pattern_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "ingestion" / "relation_type_patterns.yaml")
        relation_registry_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "ingestion" / "relation_registry.yaml")
        federated_topology_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "ingestion" / "federated_topology.yaml")
        projection_rules_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "ingestion" / "projection_rules.yaml")
        ontology_layers_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "ontology" / "universal_layers.yaml")
        model_schema_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "model" / "extraction_schema.yaml")
        node_type_model_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "model" / "node_types.yaml")
        raw_directory: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "raw")
        processed_directory: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "processed")
        asset_catalog_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "processed" / "knowledge_base" / "asset_catalog.sqlite")
        asset_source_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "app" / "assets" / "catalog" / "modules")
        flow_definition_directory: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "definitions" / "flows")
        process_definition_directory: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "config" / "definitions" / "processes")
        neo4j_uri: str = Field("bolt://localhost:7687")
        neo4j_user: str = Field("neo4j")
        neo4j_password: str = Field("banking-intent-dev")
        qdrant_host: str = Field("http://localhost:6333")
        qdrant_api_key: str | None = None
        openai_api_key: str | None = None
        openai_base_url: str = Field("https://api.openai.com/v1")
        intent_llm_model: str = Field("gpt-4o-mini")
        intent_llm_timeout_seconds: int = Field(180)
        use_ai_providers: bool = Field(False)

        model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

else:
    @dataclass(frozen=True)
    class Settings:
        project_root: Path
        asset_registry_path: Path
        agent_catalog_path: Path
        agent_skills_path: Path
        relation_pattern_path: Path
        relation_registry_path: Path
        federated_topology_path: Path
        projection_rules_path: Path
        ontology_layers_path: Path
        raw_directory: Path
        processed_directory: Path
        asset_catalog_path: Path
        asset_source_path: Path
        flow_definition_directory: Path
        process_definition_directory: Path
        model_schema_path: Path
        node_type_model_path: Path
        neo4j_uri: str = "bolt://localhost:7687"
        neo4j_user: str = "neo4j"
        neo4j_password: str = "banking-intent-dev"
        qdrant_host: str = "http://localhost:6333"
        qdrant_api_key: str | None = None
        openai_api_key: str | None = None
        openai_base_url: str = "https://api.openai.com/v1"
        intent_llm_model: str = "gpt-4o-mini"
        intent_llm_timeout_seconds: int = 180
        use_ai_providers: bool = False


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    if BaseSettings is not None:
        settings = Settings()
        settings.openai_api_key = _resolve_openai_api_key(settings.openai_api_key, settings.openai_base_url)
        settings.intent_llm_model = _resolve_intent_llm_model(settings.openai_base_url, settings.intent_llm_model)
        return settings
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_api_key = _resolve_openai_api_key(os.getenv("OPENAI_API_KEY"), openai_base_url)
    intent_llm_model = _resolve_intent_llm_model(openai_base_url)
    return Settings(
        project_root=project_root,
        asset_registry_path=project_root / "config" / "asset_registry" / "asset_types.yaml",
        agent_catalog_path=project_root / "config" / "agents" / "agent_catalog.yaml",
        agent_skills_path=project_root / "config" / "agents" / "skills",
        relation_pattern_path=project_root / "config" / "ingestion" / "relation_type_patterns.yaml",
        relation_registry_path=project_root / "config" / "ingestion" / "relation_registry.yaml",
        federated_topology_path=project_root / "config" / "ingestion" / "federated_topology.yaml",
        projection_rules_path=project_root / "config" / "ingestion" / "projection_rules.yaml",
        ontology_layers_path=project_root / "config" / "ontology" / "universal_layers.yaml",
        raw_directory=project_root / "data" / "raw",
        processed_directory=project_root / "data" / "processed",
        asset_catalog_path=project_root / "data" / "processed" / "knowledge_base" / "asset_catalog.sqlite",
        asset_source_path=project_root / "app" / "assets" / "catalog" / "modules",
        flow_definition_directory=project_root / "config" / "definitions" / "flows",
        process_definition_directory=project_root / "config" / "definitions" / "processes",
        use_ai_providers=(os.getenv("USE_AI_PROVIDERS", "false").lower() == "true"),
        qdrant_host=os.getenv("QDRANT_HOST", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        intent_llm_model=intent_llm_model,
        intent_llm_timeout_seconds=int(os.getenv("INTENT_LLM_TIMEOUT_SECONDS", "180")),
        model_schema_path=project_root / "config" / "model" / "extraction_schema.yaml",
        node_type_model_path=project_root / "config" / "model" / "node_types.yaml",
    )


def _resolve_openai_api_key(openai_api_key: str | None, openai_base_url: str) -> str | None:
    if "opencode.ai/zen" not in openai_base_url:
        return openai_api_key
    if openai_api_key and not openai_api_key.startswith("sk-or-"):
        return openai_api_key
    return os.getenv("OPENCODE_ZEN_API_KEY") or _load_opencode_auth_key() or openai_api_key


def _resolve_intent_llm_model(openai_base_url: str, default: str | None = None) -> str:
    env_model = os.getenv("INTENT_LLM_MODEL")
    if env_model:
        return env_model
    if "opencode.ai/zen" in openai_base_url:
        return "deepseek-v4-flash"
    return default or "gpt-4o-mini"


def _load_opencode_auth_key() -> str | None:
    auth_path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    opencode = data.get("opencode")
    if not isinstance(opencode, dict):
        return None
    key = opencode.get("key")
    return str(key) if key else None
