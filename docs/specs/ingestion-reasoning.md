# Ingestion Reasoning

## Purpose
Use agentic reasoning during knowledge ingestion to recommend grounded flows, reusable user tasks, front actions, back actions, ontology nodes, and utterances before deterministic validation.

## Responsibilities
- Analyze raw corpus content before normalized flow generation.
- Let multiple specialist roles compare, challenge, and validate extracted knowledge.
- Generate recommendations for candidate flow/user-task/action structures only during ingestion.
- Keep runtime customer question answering constrained to already validated graph knowledge.
- Reject unsupported inferred actions, missing task references, and backend operations modeled as user tasks.
- Keep final JSON writing and graph loading outside the agents.

## Main Components
- `app.ingestion.reasoning.IngestionReasoningService`
- `app.ingestion.reasoning.IngestionReasoningProvider`
- `RoleBasedIngestionReasoningProvider`
- `AutoGenIngestionReasoningProvider`
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`
- Flow/user-task/action validators

## Data Flow
Raw corpus files are loaded by `CorpusFlowLoader`, summarized, and passed to an ingestion reasoning provider. The reasoning provider returns agent findings such as business events, candidate flows, reusable user tasks, action boundaries, ontology concepts, ambiguity notes, and validation warnings. Those findings are added to the LLM extraction prompt. The extractor then produces normalized JSON, and deterministic validators approve or reject it before the pipeline writes `data/flows`, `data/user_tasks`, and `data/action_registry`.

## Agent Roles
| Agent | Responsibility |
|---|---|
| `CorpusReaderAgent` | Reads raw documents and identifies business events, customer intents, rules, entities, and process steps. |
| `FlowDesignerAgent` | Proposes complete business flows only when the corpus supports the end-to-end process. |
| `TaskDecomposerAgent` | Converts business steps into reusable `user_tasks`. |
| `ActionExtractorAgent` | Separates UI `front_actions` from system/API `back_actions`. |
| `OntologyAgent` | Attaches domain concepts that help retrieval and explanation. |
| `ValidatorAgent` | Rejects missing references, invalid schemas, unsupported actions, and backend operations disguised as user tasks. |

## Interfaces
- `IngestionReasoningService.analyze(corpus_summary)`
- `IngestionReasoningProvider.analyze(corpus_summary)`
- `CorpusFlowLoader(..., reasoning_service=...)`

## Implementation Notes
This component belongs under ingestion, not runtime ask question. Runtime uses `FlowAnswerContextService` to project already-created flow knowledge after a flow has been selected. Ingestion reasoning operates before the flow exists and is allowed to spend more LLM/agent effort because the result is reviewed, validated, versioned, and loaded into Neo4j before customer use.

`RoleBasedIngestionReasoningProvider` models the same roles as deterministic guidance for local runs and tests. `AutoGenIngestionReasoningProvider` runs the real agents with AutoGen AgentChat using `AssistantAgent`, `RoundRobinGroupChat`, `MaxMessageTermination`, and `OpenAIChatCompletionClient`.

The sequence and write boundary are owned by `IngestionPipelineService`, not by AutoGen. AutoGen findings are advisory input to extraction and validation.

Use role-based guidance:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --ingestion-reasoning
```

Use real AutoGen agents:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --autogen-ingestion-reasoning
```

## Runtime Boundary
AutoGen should not be used as a free-form runtime planner for customer questions. Runtime should remain:

`question -> Neo4j GraphRAG -> constrained LLM flow selection -> validated plan/tasks/actions -> approval -> JSON`

Ingestion can be:

`raw corpus -> AutoGen/LLM reasoning -> normalized flow/user-task/action JSON -> validation -> human review -> Neo4j`

## Future Replacement Strategy
AutoGen, CrewAI, or another agent framework can be swapped by preserving the `IngestionReasoningProvider` interface. The runtime ask path stays unchanged.
