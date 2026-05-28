from pathlib import Path

from app.ingestion.llm_flow_loader import CorpusDocument
from app.ingestion.semantic_analyzer import HeuristicSemanticAnalyzerProvider


def test_heuristic_semantic_analyzer_flags_mixed_enterprise_corpus_for_review():
    documents = [
        CorpusDocument(
            path=Path("manual.md"),
            text=(
                "Si el cliente pregunta que documentos necesita, responder requisitos. "
                "Si dice ayudame paso a paso, guiar la apertura. "
                "Si dice ejecuta la apertura, validar documentos y crear cuenta."
            ),
            kind="text",
        )
    ]

    result = HeuristicSemanticAnalyzerProvider().analyze(documents)

    assert result.review_required is True
    assert result.classifications[0].needs_human_review is True
    assert "savings.account.opening" in result.classifications[0].processes
