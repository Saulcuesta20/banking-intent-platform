# Goal Routing

## Purpose
Explain how ask questions become goals, user needs, route decisions, and
multiple intentions plans.

## Core Concepts

`Goal` is the customer's high-level objective.

`UserNeed` is one resolvable need inside the question.

`KnownTarget` should point to a registered enterprise asset and its owner
knowledge base, not only to a flow/process/QA/tool hardcoded in the ask
pipeline.

`Primary route assets` are assets that can be selected directly from ask, such
as approved Q&A, flows, or processes.

`Supporting assets` are assets that normally do not route directly but help
explain, constrain, compose, or validate another asset. Examples: business
rules, entities, user tasks, tools, events, ontology nodes,
documents, data attributes, and policies.

`resolution_action` is what the system should do for that need. It is not a
banking tool. Banking tools are still values such as `loan.read` or
`loan.conditions.calculate`. Tools are the lowest capability level; a task is
a reusable work unit composed of tools.

Supported resolutiontools:

- `answer_question`
- `explain_tool`
- `invoke_known_flow`
- `invoke_known_process`
- `compose_multiple_intentions_plan`
- `ask_clarification`
- `reject_unsupported`
- `escalate_to_human`

## Route Modes

`known_route`: one known flow, process, QA topic, or tool explanation can
resolve the request.

`multiple_intentions`: the request combines multiple needs or targets and must
compose a plan from approved pieces.

`clarification`: the system has multiple plausible execution routes and needs
the customer to choose.

`unsupported`: no known route can resolve the request.

## Asset-Aware Routing

The ask/goal router should use the enterprise asset registry to decide how a
retrieved asset participates in routing:

```text
registered asset -> direct_route? -> can become route target
registered asset -> executable? -> needs user confirmation and orchestrator
registered asset -> supporting? -> attach to explanation, validation, or plan gate
registered asset -> owner_kb? -> source of truth for validation and lifecycle
```

Example:

```text
business_rule.refinance_eligibility
  owner_kb: rules_kb
  direct_route: consult_only
  executable: false
  runtime_usage:
    - constrain_plan
    - explain_decision
```

If a question asks about the rule itself, the route can still be QA because an
approved Q&A topic references the rule:

```text
qa.refinance_eligibility_question
  references_rule -> business_rule.refinance_eligibility
```

If a question asks to execute a refinance flow, the same rule becomes a gate:

```text
flow.loan_refinance
  governed_by_rule -> business_rule.refinance_eligibility
```

So the rule is visible to understanding and planning, but it does not become a
standalone execution route unless the registry explicitly allows it.

## Router Boundaries

Ask routing has two levels:

| Router | Question It Answers | Current Owner |
|---|---|---|
| Ask/Goal Router | What does the user need: Q&A, flow selection, process explanation, execution, multiple intentions, clarification, or unsupported? | `QuestionUnderstandingService`, `PlanningService`, `AskService` route methods |
| Knowledge Source Router | Where should the system look for evidence: QA, rules/policies, process/flow, entity, configuration, or tool/API knowledge? | `KnowledgeSourceRouter` inside `app/knowledge_base` |

The knowledge source router is downstream from ask routing. It should not
choose the final user route by itself; it prepares evidence for planning,
selection, explanation, and future rule evaluation.

Updated runtime shape:

```text
Pregunta
  -> LLM Question Understanding
  -> Ask/Goal Router
       answer_question
       explain_tool
       invoke_known_flow
       invoke_known_process
       compose_multiple_intentions_plan
       ask_clarification
       reject_unsupported
  -> Knowledge Source Router
       qa
       rules_policies
       process_flows
       entities
       configurations
       tools_apis
  -> Retrieve from Knowledge Views
  -> EvidenceBundle
  -> Planning + selection + answer
```

## Composition Boundary

Flows and processes are route/workflow assets. They compose reusable assets by
reference:

```text
flow/process
  -> plan
  -> process_node
  -> user_task
  -> tool
  -> business_event
  -> business_rule
  -> entity
```

Ownership stays with each asset's KB:

```text
flow/process       -> process_kb
plan               -> planning_kb
business_rule      -> rules_kb
qa                 -> qa_kb
entity             -> business_model_kb
user_task/tool   -> business_model_kb
business_event     -> business_model_kb
```

The planner may compose known tasks and tools, but it cannot create new
tools. Missing operations must appear in `missing_capabilities`.

## Example

Question:

`Quiero refinanciar mi prestamo para bajar la cuota, explicame como calculan las condiciones y dime si necesito abrir una cuenta para pago automatico.`

Output:

```json
{
  "goal": {
    "summary": "Reducir la cuota del prestamo y entender los pasos relacionados.",
    "type": "business_goal",
    "confidence": 0.85
  },
  "user_needs": [
    {
      "need_id": "need_1",
      "kind": "execution",
      "text": "Quiero refinanciar mi prestamo para bajar la cuota",
      "resolution_action": "invoke_known_flow",
      "known_targets": [{"type": "flow", "id": "loan.refinance"}]
    },
    {
      "need_id": "need_2",
      "kind": "explanation",
      "text": "explicame como calculan las condiciones",
      "resolution_action": "explain_tool",
      "known_targets": [{"type": "tool", "id": "loan.conditions.calculate"}]
    },
    {
      "need_id": "need_3",
      "kind": "question",
      "text": "dime si necesito abrir una cuenta para pago automatico",
      "resolution_action": "answer_question",
      "known_targets": [{"type": "qa", "id": "qa.automatic_payment_account_required"}]
    }
  ],
  "route": {
    "mode": "multiple_intentions",
    "reason": "The goal combines multiple user needs or multiple known targets."
  }
}
```

## Safety Rule

The multiple intentions planner can compose known steps. It cannot invent
banking capabilities. Missing operations must appear in `missing_capabilities`.
