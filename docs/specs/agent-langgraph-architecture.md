# Agent And LangGraph Architecture

## Purpose
Define how this platform should model agents on top of LangGraph without
fighting LangGraph's native model.

LangGraph gives us state graphs, nodes, transitions, and compiled execution.
It does not require a first-class `Agent` object. This platform should add an
`Agent` abstraction above LangGraph so that each agent has an explicit name,
role, goals, skills, tools, state schema, graph, class family, and governance
policy. Execution is handled by an `AgentEngine` layer that compiles the
definition into a runnable graph when the agent is declarative.

## Book-Informed Design Notes
The local reference `Biswas A. Building Agentic AI Systems...2025.pdf` supports
three ideas that fit this project:

- Tools extend an agent beyond the model's native reasoning. The LLM may decide
  which tool is needed, but an external controller/runtime must execute it.
- Multi-agent systems benefit from specialized agents that cooperate,
  coordinate, and negotiate around shared goals.
- The coordinator-worker-delegator pattern maps well to this platform: the
  coordinator owns the run, a delegator/router assigns specialized work, and
  worker agents handle asset-specific extraction, retrieval, validation, or
  answer construction.
- Agents need internal state: goals, working context, memory, and knowledge
  updates. LangGraph's `StateGraph` is a natural fit for this stateful control
  loop.

## Canonical Agent Object
```python
class Agent:
    name: str
    role: str
    agent_class: Literal["planning", "coordinator", "delegator", "worker", "monitoring"]
    goals: list[str]
    skills: list[str]
    tool_ids: list[str]
    state_schema: type
    graph_factory: AgentGraphFactory
    policies: AgentPolicy
```

The object is not a replacement for LangGraph. It is the platform contract that
wraps LangGraph.

```text
Agent
  owns -> AgentState schema
  owns -> node registry
  owns -> tool access policy
  compiles -> LangGraph StateGraph
  emits -> trace/audit events
```

## Implemented Package
```text
app/agents/
  models.py
  registry.py
  runtime.py
  engine.py
  state.py
  catalog.py
  catalog_loader.py
  generic/
    base.py
    planning.py
    coordinator.py
    delegator.py
    worker.py
    monitoring.py
    factory.py
  ingestion/
    coordinator.py
  ask/
    coordinator.py
    knowledge_router.py
  assets/
    base.py
    flow_agent.py
    process_agent.py
    rule_agent.py
    qa_agent.py
    entity_agent.py
    tool_agent.py
    configuration_agent.py
```

`app/agents` is intentionally a thin runtime layer first. It gives each agent
an explicit identity, class family, role, goals, skills, tool ids, graph name,
policy, and auditable result envelope. The coordinator agents wrap the
existing LangGraph-backed services; specialist asset agents start as registered
workers and can later own deeper asset-specific LangGraph nodes. A declarative
catalog at `config/agents/agent_catalog.yaml` now loads generic planning,
coordinator, delegator, worker, and monitoring agents for configurable
business roles. `AgentEngine` compiles those declarative definitions into a
small LangGraph workflow that validates tool policy, routes by class, and
emits a structured trace.

## Knowledge Source Routing
The platform can consult several knowledge bases/views for the same question.
The router does not choose a final answer. It decides where evidence should be
retrieved from.

```text
QuestionUnderstanding
  -> KnowledgeRouterAgent
      -> qa              repository + vector
      -> process_flows   graph + repository
      -> rules_policies  repository + graph + vector
      -> tools_apis      repository + graph + external_api
      -> configurations  repository + document
      -> entities        graph + repository + vector
  -> EvidenceBundle
  -> PlanningService
```

Example: "Como se aplica esta regla en el proceso?"

```text
KnowledgeRouterAgent selects:
  qa              for the answerable question
  process_flows   for the process/flow context
  rules_policies  for the business rule and policy evidence
  entities        for synonyms and relationship expansion
```

This is complementary retrieval. The same ask may need rule evidence,
process structure, entity synonyms, and an approved Q&A asset before the
planner can decide the route.

Executable boundary:

```text
consultable/supporting assets:
  qa, business_rule, entity, document, configuration, tool
  -> retrieved and cited; not executed

executable assets:
  flow, process
  -> require confirmation
  -> handed to OrchestrationExecutorService / OrchestratorService
```

Only flows and processes are execution targets. Rules can block, enrich, or
explain execution through rule gates, but they do not execute by themselves.
Tools are invoked only inside an approved process/flow execution path or by an
explicit runtime adapter with policy checks.

## Agent Model
```python
class AgentDefinition(BaseModel):
    agent_id: str
    name: str
    role: str
    agent_class: Literal["planning", "coordinator", "delegator", "worker", "monitoring"] = "worker"
    goals: list[str]
    skills: list[str]
    skill_ids: list[str]
    tool_ids: list[str]
    state_schema: str
    graph_name: str
    max_retries: int = 0
    requires_human_review: bool = False
    enabled: bool = True
    description: str | None = None
```

```python
class AgentRuntime:
    def compile(self, definition: AgentDefinition):
        graph = StateGraph(definition.state_schema)
        for node in self.node_registry.nodes_for(definition):
            graph.add_node(node.name, node.callable)
        for edge in self.edge_registry.edges_for(definition):
            graph.add_edge(edge.source, edge.target)
        for route in self.edge_registry.conditional_edges_for(definition):
            graph.add_conditional_edges(route.source, route.router, route.path_map)
        return graph.compile()
```

## Ingestion Agent Graph
The ingestion coordinator owns the whole ingestion run. Specialist agents own
asset-specific analysis and extraction.

```text
IngestionCoordinatorAgent
  node: scan_corpus
  node: semantic_classification
  node: route_assets
  node: extract_flows
  node: extract_processes
  node: extract_rules
  node: extract_qa
  node: extract_entities
  node: extract_tools
  node: validate_assets
  node: write_preview
  node: human_review_gate
  node: apply_assets
  node: sync_knowledge_base
```

Specialists:

```text
FlowAssetAgent
ProcessAssetAgent
RuleAssetAgent
QAAssetAgent
EntityAssetAgent
ToolAssetAgent
ConfigurationAssetAgent
```

Each specialist receives the same shared ingestion state but writes only its
own candidate assets.

```python
class IngestionAgentState(TypedDict):
    run_id: str
    raw_sources: list[CorpusDocument]
    semantic_analysis: dict
    candidate_assets: dict[str, list[dict]]
    validation_errors: list[str]
    review_required: bool
    written_paths: list[str]
    traces: list[dict]
```

Recommended graph:

```text
START
  -> scan_corpus
  -> semantic_classification
  -> route_assets
  -> specialist_extractors
  -> validate_assets
  -> human_review_gate
      -> write_preview when review required

## Declarative Business Agents
The platform now supports a declarative agent catalog for business-facing
support roles. The catalog is loaded from YAML and mapped into runtime agent
classes based on the `agent_class` field.

```text
config/agents/agent_catalog.yaml
  -> AgentCatalogLoader
  -> build_agents_from_definitions()
  -> AgentRegistry
```

Supported classes:

```text
planning
coordinator
delegator
worker
monitoring
```

This is the recommended path for user-configurable business assistants. Ask
and ingestion remain dedicated service-backed coordinators because they own
platform workflows and orchestrators rather than a generic business-support
template.

## Skill Standard
For business-oriented agents, the project now adopts the Anthropic skill
pattern as a declarative markdown package:

```text
config/agents/skills/<skill-id>/SKILL.md
```

The upstream standard uses YAML frontmatter plus Markdown instructions. The
official Anthropic guidance emphasizes `name` and `description` in the
frontmatter, with additional files for deeper reference when needed. That fits
this project well because it keeps skills concise, reviewable, and versionable
while still allowing a richer skill library to grow over time.

Current implementation:

```text
AgentDefinition.skill_ids
  -> SkillCatalogLoader
  -> AgentEngine load_skills node
  -> loaded skill summaries in trace/output
```

This matches the book’s direction too: specialized agents, composable tools,
clear delegation, and AgentOps-style visibility. Skills are the bridge between
business intent and governed agent behavior.

Phase 4 recommendation:

- expose skills in the launcher UI as editable markdown packages
- version and approve skills the same way AssetSets are versioned
- let business users compose approved skills into agent templates
- keep tool access policy separate from skill guidance
      -> apply_assets when approved/apply mode
  -> sync_knowledge_base
  -> END
```

## Ask Agent Graph
The ask coordinator owns the end-to-end question resolution. Specialist agents
should not directly answer the user unless the coordinator chooses that route.

```text
AskCoordinatorAgent
  node: understand_question
  node: retrieve_knowledge
  node: route_knowledge_sources
  node: collect_asset_evidence
  node: plan_goal
  node: select_flow_or_direct_answer
  node: build_answer
  node: build_execution_options
  node: approval_gate
  node: write_trace
```

Specialists:

```text
QAAgent             answers approved Q&A/rule questions
FlowAgent           evaluates flow candidates
ProcessAgent        evaluates process candidates
RuleAgent           retrieves constraints and gates
EntityAgent         normalizes concepts/entities/synonyms
ToolAgent           explains tools and checks tool availability
ConfigurationAgent  applies routing/source policies
```

Coordinator/delegator/worker split:

```text
AskCoordinatorAgent
  -> KnowledgeRouterAgent or deterministic KnowledgeSourceRouter
      -> QAAgent
      -> FlowAgent
      -> ProcessAgent
      -> RuleAgent
      -> EntityAgent
      -> ToolAgent
      -> ConfigurationAgent
  -> AnswerBuilder
  -> ApprovalService
  -> AuditSink
```

```python
class AskAgentState(TypedDict):
    question: str
    understanding: dict
    search_terms: list[str]
    source_routes: list[dict]
    evidence_bundle: dict
    known_targets: dict[str, list[dict]]
    planning_trace: dict
    selected_route: dict
    answer: dict
    execution_options: list[dict]
    approval: dict
    trace_events: list[dict]
```

Recommended graph:

```text
START
  -> understand_question
  -> retrieve_knowledge
  -> route_knowledge_sources
  -> collect_asset_evidence
  -> plan_goal
  -> route_after_planning
      -> qa_answer
      -> flow_selection
      -> process_option
      -> tool_explanation
      -> clarification
      -> unsupported
  -> build_response
  -> approval_gate
  -> write_trace
  -> END
```

## Router Agents
Routers should be agents only when they own policy, state, and traceable
decisions. A simple deterministic router can stay as a service.

Use an agent for:

- ambiguous routing
- multi-source evidence selection
- rule-governed route choices
- asset-specific validation
- coordinating multiple specialists

Keep a service for:

- simple source lookup
- deterministic mapping
- schema validation
- pure repository search

## Tool Execution Boundary
Agents can select or request tools, but tools execute through runtime adapters.

```text
Agent reasoning
  -> proposes tool_id + args
  -> ToolPolicy validates
  -> ApprovalPolicy gates sensitive tools
  -> ToolRuntime executes
  -> result returns to AgentState
```

The LLM should not execute code. It should produce structured intent/tool
requests. The platform runtime executes tools and records audit.

## Implementation Phases
1. Keep expanding `app/agents` with richer policies and optional graph factories.
2. Continue wrapping existing `LangGraphIngestionOrchestratorService` as
   `IngestionCoordinatorAgent`.
3. Continue wrapping existing `AskService` LangGraph path as `AskCoordinatorAgent`.
4. Move specialist asset agents from registered workers into deeper nodes when
   they need asset-specific state, retries, ranking, or LLM-assisted judgment.
5. Move `KnowledgeSourceRouter` behind a `KnowledgeRouterAgent` only after the
   route decisions need stateful policy or LLM-assisted ranking.
6. Add agent run traces to `data/processed/agent_trace`.

## Recommendation
Implement agents as platform-owned orchestration components, not as replacements
for services. Services remain the deterministic units; agents coordinate them
through LangGraph nodes.

This keeps the architecture auditable:

```text
Agent = role + goals + tools + graph + policy
Node = one deterministic or LLM-backed step
Tool = invocable capability
Service = deterministic business/runtime component
State = shared execution memory for the graph
Trace = audit evidence for every decision
```
