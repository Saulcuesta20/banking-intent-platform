# Capability Service

## Purpose
Resolve and register banking tools related to intents and tasks without executing them.

## Responsibilities
- Treat capability as a tool-backed capability exposed by a user task.
- Register `frontend_tool`, `backend_tool`, and `llm_tool` definitions in one tool registry.
- Link registered tools to user tasks and flows.
- Mark execution as blocked by human approval.
- Keep tool definitions in the business model knowledge base.

## Main Components
- `CapabilityService`
- `app/capability/providers.py::CapabilityProvider`
- `app/capability/registry.py`
- `ToolRegistryEntry`
- `graph Tool nodes/tools.registry.yaml`

## Data Flow
Corpus extraction creates flows and reusable user tasks. Every `frontend_tool`
and `backend_tool` found in those user tasks is registered into a single tool
registry. When the service starts, `app/factory.py` loads the current
flow/user-task files and initializes `CapabilityService` with a runtime
registry. During question answering, resolved flow records and decomposed user
tasks are passed to `CapabilityService`, which returns the related tool
capabilities.

Tool boundary:

```text
frontend_tool
  -> UI/channel interaction, such as click, submit, select, upload, confirm

backend_tool
  -> backend capability invocation through a configured backend protocol such
     as HTTP, gRPC, MCP, or database
```

Tools are the lowest approved capability level. A process, flow, process
node, plan, or user task can reference a tool, but should not redefine it.

## Example Input/Output
Input user task: `review_refinance_options`

Output registry entries: `ui.refinance.calculate` as `frontend_tool`, `loan.conditions.calculate` as `backend_tool`.

## Interfaces
- `CapabilityService.find_related_capabilities(record, tasks)`
- `CapabilityProvider.find_for_record(record, tasks)`
- `CapabilityService.list_registered_tools()`
- `CapabilityProvider.list_registered_tools()`
- `CapabilityService.build_tool_registry(records)`
- `CapabilityProvider.build_tool_registry(records)`

## Implementation Notes
Flow and user task files currently provide the source tools. The registry is
derived, not manually curated. The persisted
`graph Tool nodes/tools.registry.yaml` is an output artifact from
extraction; the live service registry is rebuilt from the current YAML files on
startup. In the owner-KB model, tools should be governed by
`business_model_kb`, while flow/process assets reference them. The component is
independent under `app/capability` and is wired in `app/factory.py`.

## Future Replacement Strategy
Tool metadata can later be enriched from OpenAPI specs, BPMN definitions, service catalogs, or UI event telemetry.
