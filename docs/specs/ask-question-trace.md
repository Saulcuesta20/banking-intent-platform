# Ask Question Trace

## Purpose
Explain the runtime path for `ask Q="..."`, including which component queries Neo4j, which component builds the LangChain prompt, and which component calls the LLM.

## Key Clarification
LangGraph owns runtime node orchestration, but LangChain does not search Neo4j
and does not infer intent by itself. The order is:

`Question understanding -> Neo4j graph retrieval + asset search -> goal planning -> LangChain prompt template -> LLM JSON decision -> answer building`

Before Neo4j retrieval, the question is converted into graph search terms and
entity hints. `LLMQuestionUnderstandingProvider` uses an OpenAI-compatible LLM to
correct obvious typos, expand synonyms, detect ambiguity, and propose possible
intent hints. It does not choose the final flow. It only improves graph
retrieval.

Neo4j retrieval is filtered by those search terms. The provider matches terms
against flow metadata, utterances, entities, and synonyms. Current code stores
these as `concepts` and `concept_aliases`.
For example, `credito` and `prestamo` normalize into the loan entity search
space. If no terms or no rows match, the provider falls back to a limited
broad Neo4j graph context so the LLM can still return `unknown` explicitly.

## Step Table
| Step | Component | Class / Method | What it does | Output |
|---|---|---|---|---|
| 1 | CLI script | `ask` command | Runs the ask runtime with `USE_AI_PROVIDERS=true` and passes `Q`. | CLI process. |
| 2 | CLI | `app.cli.ask` | Calls `build_ask_service().resolve(question, trace=...)`. | Trace callback + question. |
| 3 | Composition | `app.factory.build_ask_service` | Wires GraphRAG retrieval, LangChain reasoning, answer, approval, audit. | `AskService`. |
| 4 | Orchestrator | `AskService.resolve` + `AskState` | Compiles a LangGraph `StateGraph` for runtime ask orchestration. | Control flow state. |
| 5 | Question understanding | `QuestionUnderstandingService.understand` | Calls the LLM to expand the question into corrected text, search terms, entity hints, synonyms, possible intent hints, and ambiguity. | `QuestionUnderstanding`. |
| 6 | Knowledge base service | `KnowledgeBaseService.search` | Delegates the understood search terms to the configured repository/adapter. | Candidate `KnowledgeRecord` list. |
| 7 | Graph adapter search | `Neo4jKnowledgeBaseGraphAdapter.search` | Calls `_query_graph_context(search_terms)`, maps Neo4j rows to approved flow records, attaches `graph_context` metadata. | Candidate records with graph context. |
| 8 | Neo4j query | `Neo4jKnowledgeBaseGraphAdapter._query_graph_context` | Runs filtered Cypher over `Flow`, `Utterance`, current `Concept`, `Synonym`, `UserTask`, and `Tool` nodes. It matches search terms against flow id/name/intent/event/explanation/utterances/entity/synonym aliases. | Ranked graph rows. |
| 9 | Asset search | `AssetSearchService.search` | Searches approved enterprise assets from YAML/generated repository. | Direct, consultable, and supporting assets. |
| 10 | Goal planning | `PlanningService.analyze` | Uses records, tools, question understanding, and asset search to produce goal, needs, route, and execution options. | `PlanningTrace`. |
| 11 | Intent classification | `FlowSelectionService.select` | Delegates to semantic reasoning provider when the route is not direct Q&A. | Selected record or `None`. |
| 12 | LangChain prompt | `LLMFlowSelectionProvider.select_intent` | Uses `PromptTemplate` to combine question + graph context into a constrained prompt. | Prompt string. |
| 13 | LLM call | `OpenAIJSONClient.complete_json` | Sends JSON-mode chat completion request to OpenAI-compatible API. | JSON answer with `can_resolve`, `selected_flow_id`, `confidence`, `reason`. |
| 14 | Flow validation | `LLMFlowSelectionProvider.select_intent` | Accepts the LLM choice only if `selected_flow_id` matches an existing candidate flow. | Selected `KnowledgeRecord`. |
| 15 | Flow projection | `AnswerBuilder.build` | Reads ingested event, plan, tasks, tools, and entities currently stored as concepts from selected flow. | `AnswerContext`. |
| 16 | Approval | `ApprovalService.enforce` | Adds required approval step/task. | Guarded plan/tasks. |
| 17 | Audit | `AuditService.record_intent_result` | Records result through configured audit sink. | Audit event. |
| 18 | Output | `AnswerResult.to_dict` | Serializes answer for CLI/API. | JSON-like result. |

## LangGraph Ask State
Runtime ask orchestration uses `app.ask.service.AskState`.

State fields:

- `question`: original user question
- `entities`: query-understanding entity hints
- `question_understanding`: interpreted question data and search terms
- `knowledge_candidates`: candidate `KnowledgeRecord` list
- `asset_search`: compact result with primary, supporting, and evidence asset ids
- `planning_trace`: goal, user needs, route, and multiple-intentions plan
- `selected_flow`: selected flow summary
- `result`: final serialized result

Internal state also carries the trace callback, selected `KnowledgeRecord`, flow
projection, and `AnswerResult` model so the use case can keep returning the
same public API.

## Trace Output
The CLI trace now includes:

- candidate flow count and first candidate flow ids
- LangGraph ask workflow marker
- question-understanding provider, search terms, and entities
- Neo4j provider name
- asset search primary/supporting/evidence asset ids
- planning goal, user needs, route mode, execution path, and execution options
- Cypher query summary, tokens, search mode, and rows returned
- LangChain/LLM provider name
- LLM prompt length
- LLM JSON decision summary
- selected flow, reason, projected event/plan/tasks/tools/entity
- debug trace file path

## Debug Trace File
Every ask run writes a JSON trace under:

`data/processed/ask_trace/ask_trace_*.json`

The file includes:

- original question
- question understanding terms/entities/provider
- all candidate flow ids
- `asset_search`
- `planning`
- Neo4j Cypher summary
- graph rows preview
- entity synonyms returned by graph rows as current `concept_aliases`
- full LangChain prompt when LLM mode is used
- LLM JSON answer when LLM mode is used
- selected flow metadata
- projected answer
- final result

Print the latest trace by running ask with debug tracing enabled:

```bash
ask "Quiero refinanciar mi prestamo" --debug-trace
```

## Safety Boundary
The LLM can only choose one existing `flow_id` from retrieved graph context. It
does not create plans, tasks, tools, events, or entities during ask question.
Approved assets can inform planning and rule answers, but tools/processes still
require confirmation before execution.
