# Ask Question Trace

## Purpose
Explain the runtime path for `make ask Q="..."`, including which component queries Neo4j, which component builds the LangChain prompt, and which component calls the LLM.

## Key Clarification
LangGraph owns runtime node orchestration, but LangChain does not search Neo4j
and does not infer intent by itself. The order is:

`Question understanding -> Neo4j graph retrieval -> LangChain prompt template -> LLM JSON decision -> flow context projection`

Before Neo4j retrieval, the question is converted into graph search terms and
entity hints. In AI mode, `LLMQueryUnderstandingProvider` may use an
OpenAI-compatible LLM to expand synonyms and domain concepts. It does not choose
the final flow. It only improves graph retrieval. Local fallback uses
`OntologyTermNormalizer`, the same deterministic synonym catalog used during
ingestion.

Neo4j retrieval is filtered by those search terms. The provider matches terms
against flow metadata, utterances, ontology nodes, and ontology synonym aliases.
For example, `credito` and `prestamo` normalize into the loan concept search
space. If no terms or no rows match, the provider falls back to a limited
all-flow context.

## Step Table
| Step | Component | Class / Method | What it does | Output |
|---|---|---|---|---|
| 1 | Makefile | `ask` target | Runs app container with `USE_AI_PROVIDERS=true` and passes `Q`. | CLI process. |
| 2 | CLI | `app.cli.ask` | Calls `build_intent_service().resolve(question, trace=...)`. | Trace callback + question. |
| 3 | Composition | `app.factory.build_intent_service` | Wires GraphRAG retrieval, LangChain reasoning, flow context, approval, audit. | `IntentResolutionService`. |
| 4 | Orchestrator | `IntentResolutionService.resolve` + `AskState` | Compiles a LangGraph `StateGraph` for runtime ask orchestration, with a linear fallback if LangGraph is unavailable. | Control flow state. |
| 5 | Retrieval service | `KnowledgeRetrievalService.retrieve` | Delegates retrieval to configured provider. | Candidate `KnowledgeRecord` list. |
| 6 | Query understanding | `QueryUnderstandingService.understand` | Expands the question into search terms, entity hints, synonyms, and possible intent hints. Uses LLM in AI mode and local fallback otherwise. | `QueryUnderstanding`. |
| 7 | Graph retrieval | `GraphRAGKnowledgeRetrievalProvider.retrieve` | Calls `_query_graph_context(search_terms)`, maps Neo4j rows back to local flow records, attaches `graph_context` metadata. | Candidate records with graph context. |
| 8 | Neo4j query | `GraphRAGKnowledgeRetrievalProvider._query_graph_context` | Runs filtered Cypher over `Flow`, `Utterance`, `Ontology`, `Synonym`, `UserTask`, and `Action` nodes. It matches search terms against flow id/name/intent/event/explanation/utterances/ontology/aliases. | Ranked graph rows. |
| 9 | Intent classification | `IntentClassificationService.classify` | Delegates to semantic reasoning provider. | Selected record or `None`. |
| 10 | LangChain prompt | `LangchainGraphRAGReasoningProvider.classify_intent` | Uses `PromptTemplate` to combine question + graph context into a constrained prompt. | Prompt string. |
| 11 | LLM call | `OpenAIJSONClient.complete_json` | Sends JSON-mode chat completion request to OpenAI-compatible API. | JSON answer with `can_resolve`, `selected_flow_id`, `confidence`, `reason`. |
| 12 | Flow validation | `LangchainGraphRAGReasoningProvider.classify_intent` | Accepts the LLM choice only if `selected_flow_id` matches an existing candidate flow. | Selected `KnowledgeRecord`. |
| 13 | Flow projection | `FlowAnswerContextService.build` | Reads ingested event, plan, tasks, actions, and ontology nodes from selected flow. | `FlowAnswerContext`. |
| 14 | Approval | `ApprovalService.enforce` | Adds required approval step/task. | Guarded plan/tasks. |
| 15 | Audit | `AuditService.record_intent_result` | Records result through configured audit sink. | Audit event. |
| 16 | Output | `IntentResult.to_dict` | Serializes answer for CLI/API. | JSON-like result. |

## LangGraph Ask State
Runtime ask orchestration uses `app.intent.service.AskState`.

State fields:

- `question`: original user question
- `entities`: query-understanding entity hints
- `retrieved_context`: candidate `KnowledgeRecord` list
- `selected_flow`: selected flow summary
- `result`: final serialized result

Internal state also carries the trace callback, selected `KnowledgeRecord`, flow
projection, and `IntentResult` model so the use case can keep returning the
same public API.

## Trace Output
The CLI trace now includes:

- candidate flow count and first candidate flow ids
- LangGraph ask workflow marker or linear fallback marker
- query-understanding provider, search terms, and entities
- Neo4j provider name
- Cypher query summary, tokens, fallback flag, and rows returned
- LangChain/LLM provider name
- LLM prompt length
- LLM JSON decision summary
- selected flow, reason, projected event/plan/tasks/actions/ontology
- debug trace file path

## Debug Trace File
Every ask run writes a JSON trace under:

`data/processed/ask_trace/ask_trace_*.json`

The file includes:

- original question
- query understanding terms/entities/provider
- all candidate flow ids
- Neo4j Cypher summary
- graph rows preview
- ontology synonym aliases returned by graph rows
- full LangChain prompt when LLM mode is used
- LLM JSON answer when LLM mode is used
- selected flow metadata
- projected flow context
- final result

Print the latest trace:

```bash
make ask-trace-latest
```

## Safety Boundary
The LLM can only choose one existing `flow_id` from retrieved graph context. It does not create plans, tasks, actions, events, or ontology during ask question.
