from __future__ import annotations

from dataclasses import dataclass
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
        flow_directory: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "flows")
        raw_directory: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "raw")
        processed_directory: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "processed")
        neo4j_uri: str = Field("bolt://localhost:7687")
        neo4j_user: str = Field("neo4j")
        neo4j_password: str = Field("banking-intent-dev")
        qdrant_host: str = Field("http://localhost:6333")
        qdrant_api_key: str | None = None
        openai_api_key: str | None = None
        openai_base_url: str = Field("https://api.openai.com/v1")
        intent_llm_model: str = Field("gpt-4o-mini")
        use_ai_providers: bool = Field(False)

        model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

else:
    @dataclass(frozen=True)
    class Settings:
        project_root: Path
        flow_directory: Path
        raw_directory: Path
        processed_directory: Path
        neo4j_uri: str = "bolt://localhost:7687"
        neo4j_user: str = "neo4j"
        neo4j_password: str = "banking-intent-dev"
        qdrant_host: str = "http://localhost:6333"
        qdrant_api_key: str | None = None
        openai_api_key: str | None = None
        openai_base_url: str = "https://api.openai.com/v1"
        intent_llm_model: str = "gpt-4o-mini"
        use_ai_providers: bool = False


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    if BaseSettings is not None:
        return Settings()
    return Settings(
        project_root=project_root,
        flow_directory=project_root / "data" / "flows",
        raw_directory=project_root / "data" / "raw",
        processed_directory=project_root / "data" / "processed",
        use_ai_providers=(os.getenv("USE_AI_PROVIDERS", "false").lower() == "true"),
        qdrant_host=os.getenv("QDRANT_HOST", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        intent_llm_model=os.getenv("INTENT_LLM_MODEL", "gpt-4o-mini"),
    )
