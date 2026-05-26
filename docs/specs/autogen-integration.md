# AutoGen Integration

## Purpose
Use AutoGen for bounded multi-agent recommendations during ingestion, where raw banking corpus files need reasoning support before deterministic extraction and validation.

## Responsibilities
- Analyze corpus content through specialist agent roles.
- Compare candidate flows and reusable user tasks before deterministic JSON validation.
- Validate action boundaries: UI events become `front_actions`; backend/service operations become `back_actions`.
- Keep AutoGen out of the customer-question runtime path unless a future provider is explicitly approved.
- Produce advisory findings that are included in auditable ingestion runs before Neo4j graph loading.

## Main Components
- `app.ingestion.reasoning.IngestionReasoningService`
- `app.ingestion.reasoning.AutoGenIngestionReasoningProvider`
- `CorpusReaderAgent`
- `FlowDesignerAgent`
- `TaskDecomposerAgent`
- `ActionExtractorAgent`
- `ConceptAgent`
- `ValidatorAgent`
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`

## Data Flow
Raw corpus files are loaded and summarized by deterministic code. AutoGen agents analyze the corpus, propose candidate flows, decompose them into reusable user tasks, extract front/back actions, attach concepts, and flag ambiguity or validation risks. The final extraction still passes through schema normalization and deterministic validation before writing `data/flows`, `data/user_tasks`, and `data/action_registry`. After review, those artifacts are loaded into Neo4j by the custom graph loader.

## Example Input/Output
Input: raw corpus notes describing loan refinance operations, customer utterances, UI actions, backend validations, and approval rules.

Output: `loan_refinance.flow.json`, reusable user task JSON files, action registry entries, concepts, and utterance examples.

## Interfaces
- `app/ingestion/reasoning.py::IngestionReasoningProvider`
- `app/ingestion/reasoning.py::IngestionReasoningService`
- `app/ingestion/llm_flow_loader.py::CorpusFlowLoader`

## Implementation Notes
AutoGen is intended for ingestion-time reasoning, not free-form runtime planning. The runtime ask path remains constrained: GraphRAG retrieves valid flows/actions from Neo4j, LangChain builds a restricted prompt, and the LLM selects one existing flow or returns `unknown`.

`AutoGenIngestionReasoningProvider` creates one `AssistantAgent` for each ingestion role and runs them as a `RoundRobinGroupChat`. The result is parsed into `IngestionReasoningFinding` values and injected into `CorpusFlowLoader` as prompt context before the final schema-constrained extraction.

AutoGen does not control the pipeline sequence, write files, or load Neo4j. `IngestionPipelineService` owns those deterministic responsibilities.

Command:

```bash
OPENAI_API_KEY=... python tools/extract_flows_from_corpus.py --raw-dir data/raw --autogen-ingestion-reasoning
```

## Future Replacement Strategy
Replace AutoGen, CrewAI, or another agent framework by implementing the same ingestion reasoning provider interface. Keep generated artifacts schema-compatible with existing flow/user-task loaders.
