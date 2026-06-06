# Extraction Instructions

## Purpose
Use role-based extraction instructions during knowledge ingestion to recommend grounded flows,
reusable user tasks, frontend tools, back tools, entities, synonyms, and
utterances before deterministic validation.

## Responsibilities
- Analyze raw corpus content before normalized flow generation.
- Let multiple specialist roles compare, challenge, and validate extracted knowledge.
- Generate recommendations for candidate flow/user-task/tool structures only during ingestion.
- Keep runtime customer question answering constrained to already validated graph knowledge.
- Reject unsupported inferred tools, missing task references, and backend operations modeled as user tasks.
- Keep final JSON writing and graph loading outside the agents.

## Main Components
- `app.ingestion.orchestrator.ExtractionInstructionBuilder`
- `RoleBasedExtractionInstructionBuilder`
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`
- Flow/user-task/tool validators

## Data Flow
Raw corpus files are loaded by `CorpusFlowLoader`, summarized, and passed to an
extraction instruction builder. The builder returns role-specific instructions
such as business events, candidate flows, reusable user tasks, tool
boundaries, entities, synonyms, ambiguity notes, and validation warnings. Those
instructions are added to the LLM extraction prompt. The extractor then produces
normalized JSON, and deterministic validators approve or reject it before the
orchestrator writes `Neo4j`, `Neo4j UserTask nodes`, and `graph Tool nodes`.

## Agent Roles
| Agent | Responsibility |
|---|---|
| `CorpusReaderAgent` | Reads raw documents and identifies business events, customer intents, rules, entities, and process steps. |
| `FlowDesignerAgent` | Proposes complete business flows only when the corpus supports the end-to-end process. |
| `TaskDecomposerAgent` | Converts business steps into reusable `user_tasks`. |
| `ToolExtractorAgent` | Separates UI `tools` from system/API `tools`. |
| `ConceptAgent` | Current compatibility name for the entity agent; attaches domain entities and synonyms that help retrieval and explanation. |
| `ValidatorAgent` | Rejects missing references, invalid schemas, unsupported tools, and backend operations disguised as user tasks. |

## Interfaces
- `ExtractionInstructionBuilder.build(corpus_summary)`
- `CorpusFlowLoader(..., instruction_builder=...)`

## Implementation Notes
This component belongs under ingestion, not runtime ask question. Runtime uses `AnswerBuilder` to project already-created flow knowledge after a flow has been selected. Extraction instructions operate before the flow exists and may spend more LLM/agent effort because the result is reviewed, validated, versioned, and loaded into Neo4j before customer use.

`RoleBasedExtractionInstructionBuilder` models the ingestion roles as deterministic instruction generation for local runs and tests.

The sequence and write boundary are owned by `IngestionOrchestratorService`. Extraction instructions are advisory input to extraction and validation.

Use role-based extraction instructions:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --build-extraction-instructions
```

## Runtime Boundary
Extraction instructions should not be used as a free-form runtime planner for customer questions. Runtime should remain:

`question -> Neo4j GraphRAG -> constrained LLM flow selection -> validated plan/tasks/tools -> approval -> JSON`

Ingestion can be:

`raw corpus -> role-based/LLM extraction instructions -> normalized flow/user-task/tool JSON -> validation -> human review -> Neo4j`

## Future Replacement Strategy
Another agent framework can be added later by preserving the `ExtractionInstructionBuilder` interface. The runtime ask path stays unchanged.
