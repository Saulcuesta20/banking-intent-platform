# Enterprise Asset Registry

## Purpose
Define the governed enterprise asset model used by ingestion, ask routing,
planning, and process execution. The platform should not hardcode only flows,
processes, Q&A, plans, rules, entities, tasks, or tools. It should load asset
type behavior from configuration and keep one clear owner knowledge base for
each asset type.

Initial configuration and approved asset examples:

```text
config/asset_registry/asset_types.yaml
processed asset catalog qa assets
processed asset catalog business_rule assets
processed asset catalog plan assets
Neo4j Flow nodes
process assets in the asset repository
UserTask nodes attached to Flow records
graph Tool nodes/tools.registry.yaml
```

## Core Rule
Every asset has one owner knowledge base.

```text
asset owner KB
  -> source of truth, approval, version, schema, lifecycle

cross-KB reference
  -> points to an asset owned elsewhere; does not duplicate ownership

technical index
  -> optional search/cache projection; not a knowledge base owner
```

This replaces the deprecated idea that one asset is owned by multiple stores
such as repository, graph, and vector at the same time. A graph or vector index
can accelerate retrieval, but the asset still belongs to exactly one owner KB.

## Agentic Meta-Model
The model follows the agentic separation used in the architecture: understand
the environment, retrieve governed context, plan over known capabilities, and
execute only guarded tools after validation.

```text
Ask signal
  -> goal
  -> user needs
  -> known targets
  -> route decision
  -> confirmed process execution

Process or flow
  -> composes tasks, tools, events, rules, plans, and entities by reference

Task
  -> reusable unit of user/system work
  -> composed of tools

Tool
  -> lowest invocable capability level
  -> frontend_tool or backend_tool
```

The LLM may infer needs and propose candidates, but it cannot invent new
banking capabilities. Planning and execution must resolve to approved assets.

## Entity And Synonyms
`entity` is the canonical name for the domain meaning asset. In this platform,
what we previously called `concept` and what we call `entity` are the same
business-model asset.

```text
entity
  -> business meaning / object / retrieval anchor
  -> can have synonyms
  -> can have relationships to other entities
  -> can later carry attributes, identifiers, schemas, or validation metadata
  -> examples: Customer, Loan, Account, Payment, Refinance, LoanConditions
```

`concept` remains a legacy compatibility name because the current code and
Neo4j graph use `concepts`, `concept_aliases`, and `Concept -> Synonym` nodes.
New specs should use `entity` as the business name and treat `concept` as the
technical legacy label until code/data are migrated.

Synonyms are not separate business assets in the MVP. They are alternate names
attached to an entity for retrieval and normalization.

```text
entity.loan
  has_synonym -> prestamo
  has_synonym -> credito
  has_synonym -> loan

entity.savings_account
  has_synonym -> cuenta
  has_synonym -> cuenta ahorro
  has_synonym -> savings account
```

## Knowledge Bases
The recommended owner KB split is:

| Knowledge Base | Owns | Role |
|---|---|---|
| `process_kb` | `flow`, `process`, `process_node` | Business routes and executable workflow structures. |
| `planning_kb` | `plan`, `plan_step` | Approved blueprints for composing work. |
| `business_model_kb` | `entity` (canonical), legacy `concept`/`ontology`, `user_task`, `tool`, `business_event` | Reusable business vocabulary and capabilities. In the federated topology, `concept` and `ontology` normalize to `entity`. |
| `rules_kb` | `business_rule` | Policies, eligibility rules, constraints, and execution gates. |
| `qa_kb` | `qa` | Approved direct-answer knowledge. |
| `config_kb` | asset type config, route policy, validators | Platform behavior and governance configuration. |
| `document_kb` | `document` | Source evidence, manuals, policies, raw references, and citations. |

Only the owner KB can approve or change an asset. Other KBs may reference it by
`asset_id`.

## Asset Categories

| Asset | Owner KB | Consultable | Direct Route | Executable | Typical Role |
|---|---|---:|---:|---:|---|
| `flow` | `process_kb` | Yes | Yes | No | User-facing intent or use case. |
| `process` | `process_kb` | Yes | Yes | Yes | Executable workflow definition. |
| `process_node` | `process_kb` | Yes | No | Through process | Workflow node that references tasks/tools/rules. |
| `plan` | `planning_kb` | Yes | No | No | Blueprint for composing approved work. |
| `plan_step` | `planning_kb` | Yes | No | No | Step reference inside a plan. |
| `qa` | `qa_kb` | Yes | Yes | No | Direct answer. |
| `business_rule` | `rules_kb` | Yes | Consult only | No | Constraint, validation, decision explanation, or gate. |
| `entity` | `business_model_kb` | Yes | No | No | Business meaning/object with synonyms, relationships, and optional attributes. |
| `concept` | `business_model_kb` | Yes | No | No | Legacy technical alias for `entity`. |
| `user_task` | `business_model_kb` | Yes | No | No | Reusable work unit composed of tools. |
| `tool` | `business_model_kb` | Yes | Consult only | Yes | Lowest executable capability. |
| `business_event` | `business_model_kb` | Yes | No | No | Domain signal emitted/projected by flows/processes. |
| `tool` | `business_model_kb` | Yes | Consult only | Yes | Adapter-backed capability invoked by backend tools. |
| `document` | `document_kb` | Yes | No | No | Evidence and source context. |
| `ontology` | `business_model_kb` | Yes | No | No | Formal relationship semantics and validation. |

`rule` and `business_rule` mean the same thing in this platform. Use
`business_rule` as the canonical asset type.

## Task And Tool Model
A `user_task` is a reusable unit of work. It is not the lowest execution level.
It is composed of tools.

```text
user_task.identify_customer
  tools:
    - ui.customer.search_submit
  tools:
    - customer.read
    - customer.identity.validate
```

`frontend_tool` describes a user/system interaction at the UI or channel
boundary. Examples:

```text
ui.customer.search_submit
ui.refinance.calculate
ui.account.open_submit
```

`backend_tool` describes a backend capability invocation. It can map to API,
gRPC, MCP, event, database, manual, or another configured protocol. Examples:

```text
customer.read
loan.conditions.calculate
account.create
approval.update
```

Tools are the final approved capability level. A process node or task can
reference tools, but runtime must not invent new tools.

## Process And Flow Composition
Processes and flows are composed assets. They reference reusable model assets
owned by other KBs.

```text
flow.loan_refinance                       owned by process_kb
  implemented_by_process -> process.loan_refinance
  realizes_plan -> plan.loan_refinance
  uses_entity -> entity.loan

process.loan_refinance                    owned by process_kb
  has_node -> process_node.identify_customer
  has_node -> process_node.review_loan_status
  governed_by_rule -> business_rule.refinance_eligibility
  emits_event -> business_event.loan_refinance_requested

process_node.identify_customer            owned by process_kb
  performs_task -> user_task.identify_customer

user_task.identify_customer               owned by business_model_kb
  invokes_tool -> tool.customer.read
  invokes_tool -> tool.customer.identity.validate

tool.customer.read                      owned by business_model_kb
business_rule.refinance_eligibility       owned by rules_kb
plan.loan_refinance                       owned by planning_kb
```

This lets tasks and tools be reused across account opening, loans, claims,
transfers, and operations without duplicating their definitions inside each
process.

## Why Rules Are Different
Business rules are part of enterprise knowledge and must be consultable:

```text
Pregunta:
  Cuales son las reglas para refinanciar?

Retrieved:
  business_rule.refinance_eligibility
  qa.refinance_rules

Route:
  qa_route
```

But a rule should not execute by itself:

```text
Pregunta:
  Quiero refinanciar mi prestamo

Retrieved:
  flow.loan_refinance
  process.loan_refinance
  business_rule.refinance_eligibility

Route:
  flow_route

Runtime:
  business_rule.refinance_eligibility gates or validates the process.
```

Execution happens through a flow/process/plan that uses the rule.

## Why Plans Are Different
Plans are knowledge assets, but they should not be primary ask routers. A plan
describes approved steps and references tasks/tools. A flow or process gives
the user-facing business intent.

```text
flow.loan_refinance
  realizes_plan -> plan.loan_refinance
  implemented_by_process -> process.loan_refinance
```

Ask should normally route to the flow or process:

```text
execution_path: flow_route
selected_flow: loan.refinance
plan: plan.loan_refinance
```

The plan is still crucial:

- previews execution steps
- composes multiple intentions
- validates required tools
- feeds the orchestrator with an execution blueprint
- provides explainability

## Ownership Configuration
Each asset type should declare exactly one owner knowledge base:

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
  qa_kb:
    role: approved_answer_owner
  config_kb:
    role: platform_configuration_owner

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
      - explains_entity

  process:
    owner_kb: process_kb
    direct_route: true
    executable: true
    execution_target: orchestrator.langgraph
    valid_relations:
      - has_node
      - governed_by_rule
      - realizes_plan
      - emits_event

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
      - requires_approval
```

Current code still uses `stores` in `config/asset_registry/asset_types.yaml`.
That field should be migrated to `owner_kb`. Search and graph/vector structures
should become technical indexes over the owner KBs, not asset ownership.

## Runtime Algorithm

```text
1. understand_question
   - LLM identifies ask posture and inferred needs.

2. search_knowledge
   - Search approved KBs or technical indexes.
   - Return primary and supporting assets with their owner KB.

3. classify_assets
   - direct_route=true -> candidate route target
   - direct_route=consult_only -> answer/explanation target
   - direct_route=false -> supporting asset

4. analyze_goal_and_plan
   - Select route target.
   - Attach supporting rules, entities, documents, and plans.
   - Compose multiple intentions only from approved assets.

5. validate_before_execution
   - Executable assets require user confirmation.
   - Rules can gate execution.
   - Tools execute only through confirmed workflow/tool adapters.

6. orchestrator
   - Invokes LangGraph workflow for confirmed process execution.
```

## Implementation Path

Implemented structure:

```text
app/knowledge_base/
  models.py
  registry.py
  loader.py
  repository.py
  search.py
  service.py
  asset_adapters.py
  adapters/
    graph/
    vector/
    nosql/
    relational/
    file/
```

`models.py` defines the common `EnterpriseAsset` contract. `registry.py`
currently reads asset type behavior from `config/asset_registry/asset_types.yaml`.
`repository.py` loads approved YAML/JSON asset instances and adapts current
flow/process assets into the same asset catalog. `service.py` provides a search
result that groups assets as direct route targets, consultable supporting
knowledge, or evidence/supporting assets.

Runtime ask still keeps the existing router names:

```text
qa_route
flow_route
process_route
multiple_intentions_route
clarification_route
unknown_route
```

The asset registry is the shared governance layer under those routers. It lets
a new asset type be registered without rewriting the ask workflow, as long as
the type declares its owner KB, valid relations, route behavior, and execution
rules.

## Current Code Entry Points

```text
build_enterprise_asset_registry()
  -> loads config/asset_registry/asset_types.yaml

build_enterprise_asset_repository()
  -> loads the processed asset catalog
  -> adapts Neo4j and process assets into EnterpriseAsset values

build_asset_search_service()
  -> combines registry + repository

build_asset_validation_service()
  -> validates asset types and allowed relations

build_asset_sync_service()
  -> writes data/processed/asset_index/enterprise_assets.index.json
```

## CLI Commands

```bash
python -m app.cli assets-list
python -m app.cli assets-list TYPE=business_rule
python -m app.cli assets-show ID=business_rule.automatic_payment_account_required
python -m app.cli assets-search Q="pago automatico cuenta"
python -m app.cli assets-validate
python -m app.cli assets-sync
```

`assets-sync` currently writes a neutral processed index. Under the owner-KB
model, the next version should write KB-oriented indexes such as:

```text
process_kb.index.json
rules_kb.index.json
business_model_kb.index.json
planning_kb.index.json
qa_kb.index.json
document_kb.index.json
```

These files can feed graph/vector/search infrastructure, but they must not
change asset ownership.

## Example Search

Question:

```text
Necesito una cuenta para pago automatico?
```

Asset search result:

```text
primary_assets:
  - qa.automatic_payment_account_required             owner: qa_kb
supporting_assets:
  - business_rule.automatic_payment_account_required  owner: rules_kb
evidence_assets:
  - plan.savings_account_opening                      owner: planning_kb
```

The direct answer path can use the Q&A asset. The account-opening plan and rule
remain visible for explanation and for a later confirmed execution path.

## Runtime Integration

`AskService` calls `AssetSearchService` during `search_knowledge`. The result is
written to the ask trace as `asset_search` and is passed to
`PlanningService.analyze(...)`.

Planning uses these assets conservatively:

- `qa` assets can reinforce direct `answer_question` routing.
- `business_rule` assets are consultable answer targets and can support a
  direct rule explanation.
- `plan` assets remain supporting/evidence assets; they do not become routers.
  - `user_task`, `tool`, `entity`, legacy `concept`, and `business_event` assets
  support explanation and plan validation.
- flow/process routing remains compatible with the existing GraphRAG path.

## Rule Gates

Business rules can define a pre-execution gate:

```yaml
payload:
  gate:
    applies_before_execution: true
    required_data:
      - customer_has_eligible_payment_account
```

`OrchestrationExecutorService` checks matching `business_rule` assets before running
process nodes. If required gate data is missing, execution stops in
`waiting_for_user_input` and the workflow trace includes `rule_gate_check`.
