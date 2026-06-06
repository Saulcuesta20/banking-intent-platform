# Planning Engine

## Purpose
Define how plans are projected from known flows and how runtime can compose a
multiple intentions plan from approved knowledge.

## Responsibilities
- Create flow plans from corpus evidence during ingestion.
- Keep plan steps as stable user task identifiers.
- Detect the user's goal during ask.
- Identify user needs and the resolution action for each need.
- Compose multiple intentions runtime plans only from known flows, processes, user tasks,
  and registered tools.
- Reject or flag missing capabilities instead of inventing banking tools.
- Let approval policy append required approval steps at runtime.

## Main Components
- `app.ingestion.llm_flow_loader.CorpusFlowLoader`
- `app.ingestion.orchestrator.RoleBasedExtractionInstructionBuilder`
- `app.knowledge_base.registry.EnterpriseAssetRegistry`
- `app.knowledge_base.repository.EnterpriseAssetRepository`
- `app.knowledge_base.search.AssetSearchService`
- `KnowledgeRecord.plan`
- `AnswerBuilder`
- `app.planning.service.PlanningService`
- `app.planning.models.Goal`
- `app.planning.models.UserNeed`
- `app.planning.models.RouteDecision`
- `app.planning.models.MultipleIntentionsPlan`
- Human approval policy

## Data Flow
The ingestion orchestrator extracts `plan` from corpus evidence and validates it
with flow/user-task references. During ask, the selected flow's `record.plan`
is still projected by `AnswerBuilder`.

The runtime planning layer adds a goal-routing trace:

1. `Goal`: what the customer is trying to accomplish.
2. `UserNeed`: each need inside the question.
3. `resolution_action`: what the system should do for each need.
4. `RouteDecision`: whether the request is a known route, multiple intentions,
   clarification, or unsupported.
5. `MultipleIntentionsPlan`: composed steps using only known user tasks and registered
   tools.

Multiple intentions planning composes approved pieces; it does not create new banking
tools.

## Enterprise Asset Model

Planning should not treat `plan` as the only first-class artifact. The platform
needs a configurable enterprise asset system where every knowledge artifact has
a common lifecycle, one owner knowledge base, and a relationship model.

Examples of asset types:

| Asset Type | Owner KB | Purpose | Direct Ask Route? | Executable? |
|---|---|---|---:|---:|
| `plan` | `planning_kb` | Versioned sequence of approved business steps and tool references. | No; used through flow/process/multiple intentions | No; blueprint only |
| `flow` | `process_kb` | User-facing intent/use case and business event projection. | Yes | Through linked plan/process |
| `process` | `process_kb` | Canonical executable business workflow with nodes, systems, rules, documents, exceptions. | Yes | Yes |
| `qa` | `qa_kb` | Approved answerable business question. | Yes | No |
| `business_rule` | `rules_kb` | Constraint, eligibility condition, policy, or decision rule. | Consult only; usually through QA/explanation | No, but can gate flow/process/plan execution |
| `entity` | `business_model_kb` | Canonical business meaning/object with synonyms, relationships, retrieval, explainability, and optional attributes. | No | No |
| `concept` | `business_model_kb` | Legacy technical alias for `entity` in current code/data. | No | No |
| `user_task` | `business_model_kb` | Reusable work unit composed of tools. | No | No |
| `tool` | `business_model_kb` | Lowest executable capability; frontend tool or back tool. | Consult only | Yes, when invoked by a workflow |
| `business_event` | `business_model_kb` | Domain signal projected or emitted by flows/processes. | No | No |
| `ontology` | `business_model_kb` | Formal relationship model for entities and process semantics. | No | No |
| `document` | `document_kb` | Source evidence and citations. | No | No |

Every asset should share a base contract:

```yaml
asset_id: loan.refinance
asset_type: flow
owner_kb: process_kb
version: 1.0.0
status: approved
owner: lending.operations
source_refs:
  - corpus://loan_refinance_manual.pdf#page=12
tags:
  - lending
  - refinance
relations:
  - type: realizes_plan
    target_asset_id: plan.loan_refinance
  - type: governed_by_rule
    target_asset_id: business_rule.refinance_eligibility
```

This gives the system one extensible pattern for adding future assets. For
example, adding `business_rule` should not require a new ask pipeline; it should
mean registering the asset type owner KB, valid relations, route behavior, and
how it participates in planning.

## Knowledge Base Ownership

Each asset has exactly one owner knowledge base:

| Knowledge Base | Owns | Used For |
|---|---|---|
| `process_kb` | flows, processes, process nodes | Route selection and workflow execution structure. |
| `planning_kb` | plans, plan steps | Preview and composition of approved work. |
| `business_model_kb` | entities, legacy concepts, user tasks, tools, business events, tools | Reusable vocabulary and capability model. |
| `rules_kb` | business rules | Policy explanation, validation, and execution gates. |
| `qa_kb` | approved Q&A | Direct answer behavior. |
| `document_kb` | documents and source evidence | Traceability and citation. |
| `config_kb` | asset registry, route policy, validators | Platform governance configuration. |

Graph, vector, and relational databases are implementation choices or technical
indexes. They can accelerate search, store operational state, or support
runtime audit, but they do not change asset ownership. When planning needs the
truth about an asset, it resolves the asset from its owner KB.

Deprecated wording:

```text
same asset -> repository + graph + vector
```

Current wording:

```text
same asset -> one owner KB
technical indexes -> references or cached search views
```

## Asset Relationships

Some assets are primary routes, while others are supporting assets.

```text
flow
  realizes_plan -> plan
  implemented_by_process -> process
  uses_entity -> entity
  governed_by_rule -> business_rule
  emits_event -> business_event

process
  has_node -> process_node
  realizes_plan -> plan
  governed_by_rule -> business_rule
  requires_document -> document
  emits_event -> business_event

plan
  decomposes_to -> user_task
  invokes_tool -> tool
  governed_by_rule -> business_rule

process_node
  performs_task -> user_task
  invokes_tool -> tool
  governed_by_rule -> business_rule

user_task
  invokes_tool -> tool
  uses_entity -> entity

tool
  backed_by_tool -> tool
  reads_entity -> entity
  writes_entity -> entity

qa
  explains_entity -> entity
  references_rule -> business_rule
  suggests_flow -> flow

business_rule
  applies_to -> flow | process | plan | tool
  depends_on -> entity | data_attribute
```

This distinction matters for routing. A rule is consultable knowledge, but it
usually should not become a direct execution route. It is retrieved as a
sub-element that can answer a rule question, explain a decision, or constrain a
flow/process/plan.

## Current Runtime Integration

`AskService` searches assets during the `search_knowledge` node and passes the
result into `PlanningService.analyze(...)`.

```text
understand_question
  -> search_knowledge
     -> KnowledgeBaseService.search(search_terms)
     -> AssetSearchService.search(question)
     -> CapabilityService.list_registered_tools()
  -> analyze_goal
     -> PlanningService.analyze(..., asset_search)
```

The planning layer uses approved assets without replacing the existing routers:

| Asset | Planning Usage |
|---|---|
| `qa` | Can become an `answer_question` target. |
| `business_rule` | Can become a consultable answer target or a supporting gate. |
| `plan` | Supports preview/composition; it is not a router. |
| `flow` / `process` | Continue to drive execution choices through existing route paths. |

Example:

```text
Question:
  Cuales son las reglas para refinanciar?

asset_search:
  supporting_assets:
    - business_rule.refinance_eligibility

planning:
  user_needs:
    - answer_question -> business_rule.refinance_eligibility
  route.mode: known_route
  execution_path: qa_route
```

Example:

```text
Question:
  Puedo refinanciar si mi prestamo esta vencido?

Understanding:
  ask_posture: consultation
  inferred_need: answer_question

Retrieved assets:
  qa.refinance_overdue_loan
  business_rule.refinance_eligibility
  flow.loan_refinance

Route:
  qa_route

Answer:
  Uses the QA topic and cites the rule.
  Does not execute the refinance flow.
```

Another example:

```text
Question:
  Quiero refinanciar mi prestamo

Retrieved assets:
  flow.loan.refinance
  plan.loan_refinance
  process.loan_refinance
  business_rule.refinance_eligibility

Route:
  flow_route

Execution options:
  Continue with approved refinance plan/process.

Before execution:
  The rule is used as a gate or validation step.
```

## Task And Tool Boundaries

A task is a reusable work unit. It is composed of tools. The tool is the
lowest approved capability level.

```text
user_task.review_loan_status
  tools:
    - ui.loan.lookup
  tools:
    - loan.read
    - loan.status.summarize
```

`frontend_tool` is a UI/channel interaction, such as clicking a button,
submitting a form, selecting an option, or invoking a screen command.

`backend_tool` is a backend capability invocation, such as an API call, gRPC
operation, MCP tool call, database operation, event emission, manual adapter, or
other configured protocol.

Processes and flows can reference tasks and tools, but they should not own
their definitions. The business model KB owns reusable tasks/tools; the
process KB owns how they are arranged in a workflow.

## Asset Registry Responsibilities

`EnterpriseAssetRegistry` answers:

```text
What asset types exist?
Which owner KB owns each asset type?
Can this asset type be routed directly from ask?
Can this asset type be executed?
What relationships are valid?
What validator must run before approval?
What runtime adapter consumes it?
```

The registry declares one owner KB for each asset type. Search indexes may be
configured separately, but they are not owners.

Suggested configuration:

```yaml
knowledge_bases:
  process_kb:
    role: route_and_workflow_owner
  rules_kb:
    role: policy_and_gate_owner
  business_model_kb:
    role: vocabulary_task_tool_event_owner
  planning_kb:
    role: plan_blueprint_owner

asset_types:
  business_rule:
    owner_kb: rules_kb
    direct_route: consult_only
    executable: false
    valid_relations:
      - applies_to_flow
      - applies_to_process
      - applies_to_plan
      - depends_on_entity
    validators:
      - rule_schema
      - owner_required
    runtime_usage:
      - constrain_plan
      - explain_decision

  qa:
    owner_kb: qa_kb
    direct_route: true
    executable: false
    valid_relations:
      - references_rule
      - explains_entity
      - suggests_flow

  process:
    owner_kb: process_kb
    direct_route: true
    executable: true
    runtime_adapter: orchestrator.langgraph

  user_task:
    owner_kb: business_model_kb
    direct_route: false
    executable: false
    valid_relations:
      - invokes_tool
      - uses_entity

  tool:
    owner_kb: business_model_kb
    direct_route: consult_only
    executable: true
    valid_relations:
      - backed_by_tool
      - reads_entity
      - writes_entity
```

The ask pipeline should consume this registry instead of hardcoding the universe
of routable knowledge. That keeps the current behavior but makes future asset
types pluggable.

## Ask Planning Architecture

`AskService` owns the ask workflow. LangGraph routes the question through
understanding, graph search, route intentions, goal planning, and final
resolution options.

```text
                         ┌──────────────────────┐
                         │ User Question         │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ understand_question  │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ search_knowledge     │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────────┐
                         │ generate_route_intentions│
                         └──────────┬───────────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ analyze_goal_and_plan│
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┬──────────────────┬──────────────────┐
                    v               v                v                  v                  v
              ┌──────────┐   ┌────────────┐   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
              │ QA route │   │ Flow route │   │Process route│   │Multiple Int. │   │Clarification │
              └────┬─────┘   └─────┬──────┘   └──────┬──────┘   └──────┬───────┘   └──────┬───────┘
                   │               │                 │                 │                  │
                   v               v                 v                 v                  v
           answer_question   select_flow       select_process    compose_plan       ask_clarification
                   │               │                 │                 │                  │
                   v               v                 v                 v                  v
              direct answer  execution_options execution_options execution_options  clarification_options
                                   │                 │                 │                  │
                                   └─────────────────┴─────────────────┴──────────────────┘
                                                     │
                                                     v
                                            User chooses option
                                                     │
                                                     v
                                            Orchestrator invokes workflow
```

Only `QA route` can answer without user confirmation because it does not
execute tools or business processes. Flow, process, multiple intentions, and clarification
routes must present options before execution.

## Route Responsibilities

| Route | Used When | Output | User Confirmation |
|---|---|---|---|
| `qa` | The user ask is first classified as a `doubt`, `consultation`, or `problem`, and then matched to a known QA topic. | Direct answer plus optional follow-up choices. | Not required for the answer. |
| `flow` | One known flow clearly matches the request. | Selected flow and execution options. | Required before tools/processes. |
| `process` | One known business process clearly matches the request. | Selected process preview and execution options. | Required before process execution. |
| `multiple_intentions` | Multiple intentions are complementary and can form one plan. | Multiple intentions plan plus execution options. | Required before tools/processes; user may choose one or many options. |
| `clarification` | Multiple intentions compete or critical information is missing. | Clarification options. | Required; user must choose one competing option. |
| `unsupported` | No known asset can resolve the request. | Unsupported response or human escalation. | No execution. |

## Reasoning Modes

`RouteIntentionService` is the intention layer. It performs abductive-style
reasoning without using that term in the public component name:

```text
What could this user mean?
Which known flows, processes, QA topics, or tools could explain the question?
Are these intentions complementary or competing?
What information is missing?
```

`PlanningService` is the controlled planning layer. It applies deductive rules
and safe composition:

```text
If there is one strong execution target -> known route.
If targets are complementary -> multiple intentions route.
If targets compete -> clarification route.
If tool/task does not exist -> do not execute.
```

## LLM Understanding First

The ask workflow follows the agent pattern described in the book: first sense
and understand the environment, then plan, then prepare tool. In this project,
the customer question is the environment signal.

`QuestionUnderstandingService` is the first semantic component. It should use
the LLM to understand the user's ask before routing:

```text
Input:
  "Necesito una cuenta para pago automatico?"

LLM understanding:
  corrected_question: Necesito una cuenta para pago automatico?
  ask_posture: doubt
  inferred_needs:
    - kind: question
      text: Necesito una cuenta para pago automatico?
      confidence: 0.86
      reason: The user is asking whether an account is required, not asking to open one yet.
  routing_hints:
    needs_answer: true
    needs_flow: false
    needs_process: false
    needs_tool_explanation: false
    needs_clarification: false
    intention_relation: single
```

The router must not infer this only from fixed words. Fixed words are a fallback
for tests and resilience, but the preferred path is:

```text
understand_question
  -> LLM detects ask_posture and inferred_needs
search_knowledge
  -> KB search and technical indexes retrieve known flows, processes, QA topics,
     rules, tasks, tools, entities, and capabilities
analyze_goal_and_plan
  -> PlanningService validates LLM needs against known assets
route
  -> qa, flow, process, multiple intentions, clarification, or unsupported
```

This gives each component a clear responsibility:

| Component | Responsibility | Must Not Do |
|---|---|---|
| `QuestionUnderstandingService` | Understand language, typo correction, ask posture, inferred needs, ambiguity, search terms. | Execute tools or select final business flow. |
| `KnowledgeBaseService` | Retrieve approved assets related to the understood question. | Invent missing flows. |
| `PlanningService` | Validate inferred needs against known targets and compose a safe plan. | Trust an LLM target that is not in the graph/tool registry. |
| `AskService` LangGraph router | Runs the ask workflow: understand, retrieve, plan, route, and produce execution options. | Execute business tools/processes. |
| Orchestrator | Adapts confirmed execution options into a process workflow and invokes LangGraph node execution. | Execute before user validation. |

### Functional Algorithm

```text
1. Understand
   - Ask the LLM for corrected_question, ask_posture, inferred_needs,
     routing_hints, ambiguity, search_terms, and possible_intents.

2. Retrieve
   - Search owner KBs or technical indexes using LLM search_terms and entities.
   - Return only approved flows, processes, QA topics, rules, tasks, tools,
     entities and registered capabilities.

3. Generate route intentions
   - Map inferred_needs to known targets:
     question -> qa target
     execution -> flow or process target
     explanation -> tool target
   - If there are no known targets, mark unsupported or clarification.

4. Validate and classify route
   - Only question + QA target -> qa_route.
   - One execution target -> flow_route or process_route.
   - Complementary needs -> multiple_intentions_route.
   - Competing intentions or missing critical information -> clarification_route.

5. Present options
   - QA answers immediately because it does not execute tools.
   - Every flow/process/multiple intentions/clarification path returns execution options.
   - Multiple intentions options can be multi-select.
   - Clarification options are single-select.

6. Invoke workflow
   - After user confirmation, the orchestrator resolves the selected flow or
     process to a process definition.
   - The orchestrator invokes the LangGraph-backed workflow runner for the
     process nodes.
   - LangGraph controls node-to-node execution and route decisions while node
     bodies call deterministic service/integration adapters.
```

## Examples By Route

### QA Route

Question:

`Necesito una cuenta para pago automatico?`

The planner does not enter QA only because the text has a question mark. It
first detects the ask posture:

```text
question_intent: doubt
signal: "necesito una cuenta"
known_qa_target: qa.automatic_payment_account_required
```

Expected summary:

```text
goal: entender requisito de cuenta para pago automatico
user_needs:
  - answer_question: Necesito una cuenta para pago automatico?
    why: The user ask is classified as doubt and matches a known QA topic.
route.mode: known_route
execution_path: qa_route
selected_target: qa.automatic_payment_account_required
answer: depende de si ya tienes una cuenta elegible
execution_options:
  1. Solo responder la pregunta
  2. Abrir flujo de cuenta si no tiene cuenta elegible
  3. No ejecutar nada todavia
```

The answer is safe to return immediately. Any follow-up execution still needs
confirmation.

### Flow Route

Question:

`Quiero refinanciar mi prestamo`

Expected summary:

```text
goal: refinanciar prestamo
user_needs:
  - invoke_known_flow
route.mode: known_route
selected_flow: loan.refinance
plan: identify_customer, review_loan_status, review_refinance_options, prepare_refinance_request
execution_options:
  1. Continuar con flujo loan.refinance
  2. No ejecutar nada todavia
```

This is mostly deductive: the request maps clearly to one known flow.

### Process Route

Question:

`Quiero iniciar una solicitud de prestamo`

Expected summary:

```text
goal: iniciar solicitud de prestamo
user_needs:
  - invoke_known_process
route.mode: known_route
selected_process: loan.application
process_preview:
  - wait_for_loan_application_data
  - create_loan_application
  - read_credit_bureau
  - calculate_loan_scoring
  - wait_for_loan_approval
execution_options:
  1. Continuar con proceso loan.application
  2. Solo ver requisitos
  3. No ejecutar nada todavia
```

The process cannot run until the user confirms one option.

### Multiple Intentions Route

Question:

`Quiero bajar mi cuota y saber si necesito una cuenta para pago automatico`

Expected summary:

```text
goal: bajar cuota y evaluar pago automatico
user_needs:
  - invoke_known_flow
  - answer_question
route.mode: multiple_intentions
multiple_intentions_plan:
  - identify_customer
  - review_loan_status
  - review_refinance_options
  - open_savings_account, conditional
  - prepare_refinance_request
execution_options:
  1. Continuar con plan de multiples intenciones completo
  2. Solo continuar con flujo loan.refinance
  3. Solo responder la duda
  4. No ejecutar nada todavia
execution_path: multiple_intentions_route
selection_mode: multiple
```

Multiple intentions route means the intentions are complementary. They can be safely
composed into a single proposed plan, but execution still needs confirmation.
Because the options are complementary, the user may select one or many options.

### Clarification Route

Question:

`Me estan cobrando mucho cada mes`

Expected summary:

```text
goal: resolver cobro mensual alto
observations:
  - menciona cobro mensual alto
  - no especifica si es cuota, comision o cargo
intentions:
  - loan.refinance
  - fees.claims
  - loan.payment
route.mode: clarification
clarification_question: Te refieres a cuota de prestamo, comision/cargo o pago pendiente?
execution_options:
  1. Revisar refinanciamiento
  2. Revisar reclamo de cargos
  3. Consultar pagos
  4. No ejecutar nada todavia
execution_path: clarification_route
selection_mode: single
```

Clarification route means the intentions compete. The system must not compose
them as one plan because it does not yet know which explanation is correct.
Because the options are competing, the user must select only one.

## Parallel Routes

The current ask implementation selects one validated `execution_path` per ask:

```text
qa_route | flow_route | process_route | multiple_intentions_route | clarification_route | unknown_route
```

That means the ask router is not executing multiple route branches in parallel yet.
When the LLM understanding detects several compatible intentions, the system
uses `multiple_intentions_route` and returns a single composed plan with multiple selectable
options.

Example:

```text
Question:
  Quiero refinanciar mi prestamo, explicame como calculan las condiciones,
  y dime si necesito cuenta para pago automatico.

Validated route today:
  execution_path: multiple_intentions_route
  intentions:
    - invoke_known_flow: loan.refinance
    - explain_tool: loan.conditions.calculate
    - answer_question: qa.automatic_payment_account_required
  selection_mode: multiple
```

This is parallel in the planning sense, because several intentions are detected
and can be selected together. It is not parallel in the execution sense at the
ask layer, because `ask` does not run tools or processes. Execution belongs to
the orchestrator workflow after validation.

A future version can add parallel route groups after validation:

```text
route_groups:
  - group_id: answer
    path: qa_route
    can_run_immediately: true
  - group_id: refinance
    path: flow_route
    requires_confirmation: true
  - group_id: explain_conditions
    path: tool_explanation_route
    requires_confirmation: false

execution_policy:
  mode: parallel_after_confirmation
  join: wait_all
```

The important boundary stays the same: the LLM may propose multiple intentions,
but only validated assets can be executed, and any flow/process/tool execution
must wait for user confirmation. Once confirmed, the orchestrator is the
workflow adapter that calls LangGraph to execute process nodes.

## Example Input/Output
Input flow: `loan.refinance`

Projected plan: `identify_customer`, `review_loan_status`, `review_refinance_options`, `prepare_refinance_request`, `approve_business_case`.

Multiple intentions input:

`Quiero refinanciar mi prestamo para bajar la cuota, explicame como calculan las condiciones y dime si necesito abrir una cuenta para pago automatico.`

Runtime planning trace:

```json
{
  "goal": {
    "summary": "Reducir la cuota del prestamo y entender los pasos relacionados.",
    "type": "business_goal",
    "confidence": 0.85
  },
  "user_needs": [
    {
      "kind": "execution",
      "resolution_action": "invoke_known_flow",
      "known_targets": [{"type": "flow", "id": "loan.refinance"}]
    },
    {
      "kind": "explanation",
      "resolution_action": "explain_tool",
      "known_targets": [{"type": "tool", "id": "loan.conditions.calculate"}]
    },
    {
      "kind": "question",
      "resolution_action": "answer_question",
      "known_targets": [{"type": "qa", "id": "qa.automatic_payment_account_required"}]
    }
  ],
  "route": {
    "mode": "multiple_intentions"
  }
}
```

Before any tool or process execution, `ask` returns validation options:

```json
{
  "requires_execution_confirmation": true,
  "execution_selection_policy": {
    "path": "multiple_intentions_route",
    "selection_mode": "multiple",
    "requires_user_selection": true,
    "reason": "Multiple intentions route contains complementary options; the user may choose one or many."
  },
  "execution_options": [
    {
      "option_id": "continue_multiple_intentions_plan",
      "label": "Continuar con el plan de multiples intenciones completo",
      "executes_tools_now": false,
      "requires_confirmation": true
    },
    {
      "option_id": "need_1",
      "label": "Continuar con flujo loan.refinance",
      "executes_tools_now": false,
      "requires_confirmation": true
    },
    {
      "option_id": "do_not_execute",
      "label": "No ejecutar nada todavia",
      "executes_tools_now": false
    }
  ]
}
```

The ask command never executes banking tools directly. It only proposes options
that a later execution step can confirm.

## Interfaces
- `KnowledgeRecord.plan`
- `AnswerBuilder.build(question, record)`
- `PlanningService.analyze(question, records, registered_tools)`

## Implementation Notes
Runtime planning is constrained. `PlanningService` can compose known pieces, but
cannot invent flows, user tasks, or tools. If a customer asks for something
outside the graph, the plan exposes `missing_capabilities` or returns an
unsupported route.

## Future Replacement Strategy
The deterministic `PlanningService` can be replaced by an LLM provider as long
as validation keeps the same boundary: multiple intentions is allowed, free-form
banking execution is not.
