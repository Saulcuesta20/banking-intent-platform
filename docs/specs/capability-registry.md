# Capability Service

## Purpose
Resolve and register banking actions related to intents and tasks without executing them.

## Responsibilities
- Treat capability as an action exposed by a user task.
- Register both `front_actions` and `back_actions` in one action registry.
- Link registered actions to user tasks and flows.
- Mark execution as blocked by human approval.

## Main Components
- `CapabilityService`
- `app/capability/providers.py::CapabilityProvider`
- `app/capability/local.py`
- `ActionRegistryEntry`
- `data/action_registry/actions.registry.json`

## Data Flow
Corpus extraction creates flows and reusable user tasks. Every `front_action` and `back_action` found in those user tasks is matriculated into a single action registry. When the service starts, `app/factory.py` loads the current flow/user-task files and initializes `CapabilityService` with a runtime registry. During question answering, resolved flow records and decomposed user tasks are passed to `CapabilityService`, which returns the related action capabilities.

## Example Input/Output
Input user task: `review_refinance_options`

Output registry entries: `ui.refinance.calculate` as `front_action`, `loan.conditions.calculate` as `back_action`.

## Interfaces
- `CapabilityService.find_related_capabilities(record, tasks)`
- `CapabilityProvider.find_for_record(record, tasks)`
- `CapabilityService.list_registered_actions()`
- `CapabilityProvider.list_registered_actions()`
- `CapabilityService.build_action_registry(records)`
- `CapabilityProvider.build_action_registry(records)`

## Implementation Notes
Flow and user task files provide the source actions. The registry is derived, not manually curated. The persisted `data/action_registry/actions.registry.json` is an output artifact from extraction; the live service registry is rebuilt from the current JSON files on startup. The component is independent under `app/capability` and is wired in `app/factory.py`.

## Future Replacement Strategy
Action metadata can later be enriched from OpenAPI specs, BPMN definitions, service catalogs, or UI event telemetry.
