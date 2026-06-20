# Extraction Prompts (rendered from config/model)

This file documents the LLM prompts rendered from
`config/model/extraction_schema.yaml`.

## Key Changes

- The schema is now an asset contract, not an example library.
- Prompts render required fields, optional fields, payload composition,
  relations, and runtime semantics.
- Container/configuration assets now have contracts too: `domain`, `module`,
  `menu`, `form`, `form_version`, and `asset_set`.
- Flow and user_task still use the legacy top-level arrays consumed by
  `CorpusFlowLoader`, but they are governed by the same `asset_contracts`
  section as other assets.
- Optional asset arrays returned by the same extraction result are preserved:
  `entity`, `business_rule`, `process`, `plan`, `qa`, and `causality`.
- Flow matching text is captured as `purpose`; `intent` is no longer requested
  from the LLM contract and remains only an internal Ask compatibility field.
- Relations derived from composition are named `derived_relations`.
- User actions carry a `lifecycle_state` field with
  `not_started`, `on_user_enter`, `cancelled`, and `completed`.
- Business rules support `when` / `then` semantics.
- Process and plan contracts support event-driven `business_event` semantics.
- Examples are intentionally not rendered to avoid prompt copying.

## Primary Extraction Prompt

```text
Analyze this corpus and extract governed assets.
Return this JSON object shape, with arrays populated from corpus evidence only:
{
  "user_tasks": [],
  "flows": [],
  "domain": [],
  "module": [],
  "menu": [],
  "form": [],
  "form_version": [],
  "asset_set": [],
  "entity": [],
  "business_rule": [],
  "process": [],
  "plan": [],
  "qa": [],
  "causality": []
}

Compatibility notes:
- The legacy flow loader still consumes top-level user_tasks and flows.
- All asset types are governed by asset_contracts and follow one ingestion lifecycle.

Type definitions:
- user_action: User-facing action within a user_task.
  lifecycle_states: not_started, on_user_enter, cancelled, completed
  - front: UI or channel interaction.
    required_fields: action_id, type, implementation_type
    optional_fields: label, triggers, description, lifecycle_state
  - back: Operation invocation from a task.
    required_fields: action_id, type, implementation_type
    optional_fields: tool_id, tool_ids, label, description, lifecycle_state
- tool: Tool or system operation.
  - frontend_tool: UI event or client-side action.
    required_fields: tool_id, tool_type, operation, resource
    optional_fields: label, frontend_event, description
  - backend_tool: System/API/database/service operation.
    required_fields: tool_id, tool_type, operation, resource
    optional_fields: description, backend_protocol, endpoint, requires_approval
  - llm_tool: LLM-backed decision or generation operation.
    required_fields: tool_id, tool_type, operation
    optional_fields: description, llm_model, llm_provider, llm_operation

Asset contracts:
- domain:
  required_fields: domain_id, name, purpose
- module:
  required_fields: module_id, domain_id, name, purpose
- menu:
  required_fields: menu_id, module_id, label, path
- form:
  required_fields: form_id, module_id, name, purpose
- form_version:
  required_fields: form_id, version, schema
- asset_set:
  required_fields: asset_set_id, version, primary_asset_type, members
- user_task:
  description: Reusable human/business step that may appear in flows or process nodes.
  output_array: user_tasks
  required_fields: user_task_id, task, type, name, description
  optional_fields: user_actions, tools
  payload_fields: user_task_id, task, type, name, description, user_actions, tools
  allowed_relations: invokes_tool, used_by_flow, used_by_process, governed_by_rule, uses_concept
- flow:
  description: User-facing use case selected by Ask and routed to process or plan execution options.
  output_array: flows
  required_fields: flow_id, flow_name, purpose, business_event, user_task_refs, explanation
  optional_fields: inputs, outputs
  payload_fields: flow_id, flow_name, purpose, business_event, user_task_refs, related_process_ids, inputs, outputs, explanation
  derived_relations: decomposes_to_user_task from user_task_refs
  allowed_relations: implemented_by_process, governed_by_rule, decomposes_to_user_task, uses_concept

Rules:
- Return only JSON. Do not include markdown.
- Derive every asset name, purpose, field value, event, relation, and rule from the corpus.
- Do not copy placeholder values; no examples are provided intentionally.
- Create flows for complete end-to-end business processes or customer journeys.
- Use purpose to describe why an asset exists and provide semantic text that helps Ask match user needs.
- Create user_tasks for business/user steps; reuse them across flows where possible.
- A flow references tasks through user_task_refs; the task definitions live in user_tasks.
- Model each user_task with user_actions and/or tools.
- A user_action.type is either front for UI/channel interaction or back for operation invocation.
- A back user_action can reference one or more tools through tool_id or tool_ids.
- Keep user_actions as the primary hierarchy and tools as the flattened lookup list for the task.
- Back actions reference backend or LLM tools through tool_id/tool_ids.
- Tool types are frontend_tool, backend_tool, or llm_tool.
- Put CRUD/calculation/API/checking operations under backend_tool, never as user_tasks.
- Put clicks/submits/views under frontend_tool.
- Model entities as separate entity assets, not as flow fields.
- For process, plan, and business_rule, capture when/business_event semantics when the corpus states or implies triggering.
- For business_rule, prefer when/then plus conditions/consequences when source text contains event-driven rule logic.
- For entity, include relations only when the corpus supports them.
- If images are provided, first read their visible text and diagrams, then use that information with text files.
- Do not manually add concept_aliases; aliases are normalized by the ingestion pipeline.
```

The actual rendered flow prompt also includes JSON-formatted `composition` and
`runtime_semantics` blocks for each configured contract.

## Asset Extraction Prompt

```text
Extract governed asset candidates from this corpus.
Return this JSON object shape, with arrays populated from corpus evidence only:
{
  "domain": [],
  "module": [],
  "menu": [],
  "form": [],
  "form_version": [],
  "asset_set": [],
  "entity": [],
  "business_rule": [],
  "process": [],
  "plan": [],
  "qa": [],
  "causality": []
}

Compatibility notes:
- The legacy flow loader still consumes top-level user_tasks and flows.
- All asset types are governed by asset_contracts and follow one ingestion lifecycle.

Asset contracts:
- domain:
  required_fields: domain_id, name, purpose
  optional_fields: description, order, icon, tags
  payload_fields: domain_id, name, purpose, description, order, icon, tags
- module:
  required_fields: module_id, domain_id, name, purpose
  optional_fields: description, order, icon, menus, tags
  payload_fields: module_id, domain_id, name, purpose, description, order, icon, menus, tags
  derived_relations: belongs_to_domain from domain_id
- menu:
  required_fields: menu_id, module_id, label, path
  optional_fields: description, order, icon, parent_menu_id, children, target_asset_id
  payload_fields: menu_id, module_id, label, path, description, order, icon, parent_menu_id, children, target_asset_id
  derived_relations: belongs_to_module from module_id
- form:
  required_fields: form_id, module_id, name, purpose
  optional_fields: description, fields, layout, validation, bindings, current_version
  payload_fields: form_id, module_id, name, purpose, description, fields, layout, validation, bindings, current_version
- form_version:
  required_fields: form_id, version, schema
  optional_fields: renderer, bindings, validation, migration_notes
  payload_fields: form_id, version, schema, renderer, bindings, validation, migration_notes
- asset_set:
  required_fields: asset_set_id, version, primary_asset_type, members
  optional_fields: domain_id, module_id, status, description, owner, tags, metadata
  payload_fields: asset_set_id, version, primary_asset_type, members, domain_id, module_id, status, description, owner, tags, metadata
- entity:
  required_fields: name
  optional_fields: description, aliases, evidence, attributes, relations
  payload_fields: entity_id, name, aliases, attributes, relations, description, evidence
- business_rule:
  required_fields: name
  optional_fields: description, transaction_id, ruleset_name, rule_text, when, conditions, then, consequences, applies_to
  payload_fields: rule_id, rule_text, when, conditions, then, consequences, applies_to, transaction_id, ruleset_name
- process:
  required_fields: name
  optional_fields: description, transaction_id, business_event, triggers, steps, execution_nodes, transitions, rules, tools
  payload_fields: process_id, process_name, business_event, triggers, execution_nodes, transitions, decisions, systems, exceptions, rules, tools
- plan:
  required_fields: name
  optional_fields: description, objective, transaction_id, business_event, steps, tools, dependencies
  payload_fields: plan_id, objective, business_event, steps, tools, dependencies, execution_options
- qa:
  required_fields: question, answer
  optional_fields: purpose, transaction_id, citations
  payload_fields: question, answer, purpose, source, citations, transaction_id
- causality:
  required_fields: statement
  optional_fields: transaction_id, relation_kind, cause_text, effect_text, evidence
  payload_fields: cause_text, effect_text, relation_kind, evidence, targets, transaction_id

Rules:
- Return only JSON. Do not include markdown.
- Derive every asset name, field value, event, relation, and rule from the corpus.
- Do not copy placeholder values; no examples are provided intentionally.
- For process, plan, and business_rule, capture when/business_event semantics when the corpus states or implies triggering.
- For business_rule, prefer when/then plus conditions/consequences when source text contains event-driven rule logic.
- For entity, include relations only when the corpus supports them.
```

The actual rendered asset prompt also includes each contract's composition,
allowed relations, and runtime semantics.
