from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.factory import build_ingestion_provider, build_intent_service


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    source_path: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="Banking Intent Platform",
        description="Enterprise banking intent resolution with AI-assisted planning and decomposition.",
    )

    @app.post("/ask")
    def ask(request: AskRequest) -> dict:
        service = build_intent_service()
        try:
            result = service.resolve(request.question)
            return result.to_dict()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/ingest")
    def ingest(request: IngestRequest) -> dict:
        ingestion = build_ingestion_provider()
        try:
            records = ingestion.ingest(Path(request.source_path))
            return {
                "status": "ok",
                "source": request.source_path,
                "records_ingested": len(records),
                "intents": [record.intent for record in records],
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return app
