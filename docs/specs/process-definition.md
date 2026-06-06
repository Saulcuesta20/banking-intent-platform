# Process Definition

## Purpose
Define a fixed YAML structure for executable process and flow graphs. Runtime
execution is node-based, not step-based. A flow can be executed directly when a
flow execution definition exists.

## File Location
Process definitions live in:

```text
config/definitions/processes/*.yaml
config/definitions/flows/*.yaml
```

The runtime layer is called the orchestrator. It is the workflow adapter for
confirmed execution: it coordinates flows and processes, creates/updates
instances, and invokes the LangGraph process workflow without exposing a VM name
in the public model.

## Required Top-Level Shape
```yaml
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

`steps` is legacy metadata. Runtime execution uses `execution_nodes` and
`transitions` as the canonical graph.

## Flow vs Process
| Artifact | Purpose |
|---|---|
| `Neo4j Flow nodes` | Runtime intent, utterances, business event, plan, user tasks, entity values currently stored as concepts, capabilities. Defined by `FlowDefinition`. |
| `process assets in the asset repository` | Canonical business-process structure with actors, systems, rules, documents, decisions, exceptions, and execution metadata. |

## Runtime Contract
Runtime can keep selecting flows first. Once a flow is selected, the platform can
resolve `related_flow_ids` to retrieve the richer process definition for guided
use cases, execution validation, approvals, and explainability.

## Runtime Execution
Business process runtime lives under:

```text
app/orchestrator/
```

`OrchestrationExecutorService` is part of the orchestrator runtime. It can load both
artifacts from both sources:

- `Neo4j Flow nodes`
- `process assets in the asset repository`
- `config/definitions/flows/*.yaml`
- `config/definitions/processes/*.yaml`

When a `flow_id` is requested, runtime first checks flow execution YAML
definitions. If a flow executable graph is present, it is executed directly.
If not, runtime resolves a matching process by `related_flow_ids`.

When `use_langgraph=true`, execution compiles a LangGraph `StateGraph` and
invokes it over the process execution state.

Before any node executes, `OrchestrationExecutorService` checks approved
`business_rule` assets related to the selected flow/process. A rule can define a
pre-execution gate:

```yaml
payload:
  gate:
    applies_before_execution: true
    required_data:
      - customer_has_eligible_payment_account
```

If required gate data is missing, the process returns
`status=waiting_for_user_input` and the workflow trace records
`rule_gate_check`. This keeps business rules as governed assets while still
allowing them to constrain execution.

## Orchestrator Asset Registry
The orchestrator exposes a formal asset registry through:

```text
app/orchestrator/assets.py
```

The registry lists:

- flow assets from `Neo4j`
- process assets from `process assets`
- links from `flow_id` to `process_id`

Runtime entry points:

```text
GET /orchestrator/assets
python -m app.cli orchestrator-assets
```

This is an asset registry, not a LangGraph checkpoint store.

## Node Model
Every executable process node uses this fixed shape:

```yaml
{
  "node_id": "wait_for_loan_application_data",
  "name": "Wait For Loan Application Data",
  "type": "wait_for_user_input",
  "node_kind": "system",
  "implementation": "builtin.wait_for_user_input",
  "description": "Pause until the user provides required data.",
  "required_inputs": ["customer_id", "loan_amount"],
  "produced_outputs": ["customer_id", "loan_amount"],
  "related_user_task_id": null,
  "actions": [],
  "tools": [],
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
| `user_task` | Executes a user-task node in the runtime graph. |
| `agent` | Executes an agent node in the runtime graph. |
| `wait_for_user_input` | Pauses until required data is provided by the user or UI. |
| `state_update` | Updates process execution data without external calls. |
| `service_call` | Invokes an integration provider. |
| `tool_call` | Invokes a registered tool call through integration providers. |
| `subprocess_call` | Invokes a subprocess call path. |
| `decision` | Evaluates a process decision or routing condition. |
| `approval` | Waits for or records human approval. |
| `notification` | Prepares or sends notification through an integration. |
| `end` | Completes the process execution. |

Node type permissions are validated by Python policy:

```text
app/orchestrator/node_policy.py::ExecutionNodePolicy
```

The policy can differ for `flow` vs `process` definitions.

Transitions are explicit movements between execution nodes:

```yaml
{
  "from_node": "wait_for_loan_application_data",
  "to_node": "create_loan_application",
  "condition": "required_inputs_present",
  "description": "Continue after the user provides required data."
}
```

## Integration Model
Service calls use `integrations`:

```yaml
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
app/orchestrator/assets.py
```

There is no separate `app/process_execution` package; process execution is part
of the orchestrator. Conceptually, `OrchestrationExecutorService` is the adapter that
turns a selected flow/process into a LangGraph workflow invocation.

## Workflow Trace
`OrchestrationExecutorService` records an explicit `workflow_trace` in each
`ProcessExecutionResult`. The trace includes:

- workflow compile metadata
- node start events
- node completion or waiting events
- route decisions

In the current implementation the compiled LangGraph workflow has one reusable
node, `execute_current_node`, with a conditional edge back to itself while the
process should continue. The current process node id is stored in state. This
keeps process definitions data-driven while LangGraph owns workflow execution
and routing.

The current implementation intentionally does not use LangGraph `MemorySaver`,
checkpoints, or `thread_id`. Active instance state is recorded through the
orchestrator repository.

Runtime entry points:

```text
POST /orchestrator/process/execute
GET /orchestrator/instances
python -m app.cli orchestrator-execute --flow-id money.transfer --data '{"customer_id":"C-123"}'
python -m app.cli orchestrator-instances --all
python -m app.cli orchestrator-validate-definitions
```
