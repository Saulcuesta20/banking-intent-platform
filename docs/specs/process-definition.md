# Process Definition

## Purpose
Define a fixed JSON structure for business processes. A process is the canonical
map of actors, systems, rules, decisions, exceptions, and ordered steps. A flow
remains the runtime intent/use-case projection that the ask path can select.

## File Location
Process definitions live in:

```text
data/processes/*.process.json
```

The runtime layer is called the orchestrator. It coordinates both flows and
processes without exposing a VM name in the public model.

## Required Top-Level Shape
```json
{
  "process_id": "customer.onboarding",
  "process_name": "Customer Onboarding",
  "version": "1.0.0",
  "status": "draft",
  "domain": "banking.customer",
  "owner": "Customer Operations",
  "description": "What this process accomplishes.",
  "related_flow_ids": ["customer.onboarding"],
  "triggers": ["alta de cliente"],
  "inputs": ["customer_documents"],
  "outputs": ["customer_profile"],
  "actors": [],
  "systems": [],
  "documents": [],
  "rules": [],
  "decisions": [],
  "exceptions": [],
  "integrations": [],
  "activities": [],
  "execution_nodes": [],
  "transitions": [],
  "timers": [],
  "async_continuations": [],
  "event_listeners": [],
  "compensations": [],
  "subprocesses": [],
  "message_correlations": [],
  "jobs": [],
  "steps": [],
  "metadata": {}
}
```

## Flow vs Process
| Artifact | Purpose |
|---|---|
| `data/flows/*.flow.json` | Runtime intent, utterances, business event, plan, user tasks, concepts, capabilities. Defined by `FlowDefinition`. |
| `data/processes/*.process.json` | Canonical business-process structure with actors, systems, rules, documents, decisions, exceptions, and execution metadata. |

## Runtime Contract
Runtime can keep selecting flows first. Once a flow is selected, the platform can
resolve `related_flow_ids` to retrieve the richer process definition for guided
use cases, execution validation, approvals, and explainability.

## Runtime Execution
Business process runtime lives under:

```text
app/orchestrator/
```

`ProcessExecutionService` can load both artifacts:

- `data/flows/*.flow.json`
- `data/processes/*.process.json`

The flow identifies the user-facing intent. The process supplies the executable
business structure.

## Node Model
Every executable process node uses this fixed shape:

```json
{
  "node_id": "wait_for_loan_application_data",
  "step_id": "capture_loan_application",
  "name": "Wait For Loan Application Data",
  "type": "wait_for_user_input",
  "implementation": "builtin.wait_for_user_input",
  "description": "Pause until the user provides required data.",
  "required_inputs": ["customer_id", "loan_amount"],
  "produced_outputs": ["customer_id", "loan_amount"],
  "integration_id": null,
  "next_nodes": [],
  "on_success": "create_loan_application",
  "on_failure": null,
  "metadata": {}
}
```

Supported node types:

| Node type | Runtime behavior |
|---|---|
| `start` | Initializes execution state. |
| `wait_for_user_input` | Pauses until required data is provided by the user or UI. |
| `state_update` | Updates process execution data without external calls. |
| `service_call` | Invokes an integration provider. |
| `decision` | Evaluates a process decision or routing condition. |
| `approval` | Waits for or records human approval. |
| `notification` | Prepares or sends notification through an integration. |
| `end` | Completes the process execution. |

Transitions are explicit movements between execution nodes:

```json
{
  "from_node": "wait_for_loan_application_data",
  "to_node": "create_loan_application",
  "condition": "required_inputs_present",
  "description": "Continue after the user provides required data."
}
```

## Integration Model
Service calls use `integrations`:

```json
{
  "integration_id": "loan_scoring_grpc",
  "name": "Evaluate Loan Scoring",
  "type": "legacy_service",
  "protocol": "grpc",
  "operation": "calculate",
  "endpoint": "LoanScoringService/Evaluate",
  "timeout_seconds": 60,
  "requires_approval": false,
  "metadata": {}
}
```

Supported protocols are `api`, `grpc`, `mcp`, `event`, `database`, and `manual`.
The default runtime provider simulates calls safely until real adapters are
registered.

## Orchestrator Capabilities
The process model supports long-running orchestration concerns:

| Capability | Model |
|---|---|
| Long-running instances | `OrchestratorInstance` |
| Timers | `OrchestratorTimer` |
| Async continuations | `OrchestratorAsyncContinuation` |
| Event listeners | `OrchestratorEventListener` |
| Compensations | `OrchestratorCompensation` |
| Subprocesses | `OrchestratorSubprocess` |
| Message correlation | `OrchestratorMessageCorrelation` |
| Pending jobs | `OrchestratorJobDefinition` and `OrchestratorJob` |

Runtime services live under:

```text
app/orchestrator/
```

Process execution is part of the orchestrator package:

```text
app/orchestrator/process_execution.py
app/orchestrator/process_providers.py
```

There is no separate `app/process_execution` package; process execution is part
of the orchestrator.
