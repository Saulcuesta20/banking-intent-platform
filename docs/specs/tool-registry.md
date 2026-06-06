# Tool Registry

## Purpose
`Tool` is the canonical name for anything the platform can invoke or explain as
an operational capability. It replaces the older wording of tools.

User tasks, flows, plans, and processes can reference tools. The ask path may
explain tools, but it must not execute them without an explicit execution path
and confirmation.

## Tool Types
```yaml
tool_type:
  - frontend_tool
  - backend_tool
  - llm_tool
```

`protocol` is not a generic tool property. It only applies to backend tools,
because protocol means a backend invocation transport or adapter.

```yaml
backend_protocol:
  - http
  - grpc
  - mcp
  - database
```

Frontend tools describe UI interaction through `frontend_event`.
LLM tools describe model usage through `llm_operation`, `llm_model`, and
`llm_provider`.

## Runtime Model
```text
Flow
  -> UserTask
       -> frontend_tool
       -> backend_tool
       -> llm_tool

Process
  -> ExecutionNode
       -> backend_tool / llm_tool
```

## Canonical YAML
User tasks use `tools` as the official field:

```yaml
tools:
- tool_id: ui.refinance.calculate
  tool_type: frontend_tool
  frontend_event: loan_refinance.calculate

- tool_id: loan.conditions.calculate
  tool_type: backend_tool
  backend_protocol: http
```

The runtime can still read legacy `frontend_tools` and `backend_tools` for
backward compatibility, but generated and curated definitions should use
`tools`.

## LLM Tools
The current codebase invokes LLMs in three explicit places:

- `llm.question_understanding.complete_json`
- `llm.flow_selection.complete_json`
- `llm.corpus_flow_extrtool.complete_json`

Those tools are defined in `graph Tool nodes/tools.registry.yaml` and are
also exposed by the concrete OpenAI-compatible clients through
`tool_definition`.

## Capability Relationship
Capability remains useful as a higher-level promise or need. A capability can be
provided by one or more tools.

```text
capability: calculate_loan_conditions
  provided_by:
    - tool.loan.conditions.calculate.http
    - tool.loan.conditions.calculate.grpc
    - tool.llm.loan_conditions.explain
```
