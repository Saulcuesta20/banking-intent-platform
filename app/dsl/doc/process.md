# Process DSL

## Purpose

Define executable workflow structure.

Processes are more operational than flows. A flow expresses the business need;
a process expresses the sequence of governed steps that can implement it.

## Example

```text
CREATE PROCESS loan_refinance
  USING process_kb
  VERSION '1.0.0'
  STATUS approved
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.review_loan_status TYPE step
  RELATED_TO process_node.calculate_terms TYPE step
  RELATED_TO rule.refinance_eligibility TYPE dependency
  EMITS_EVENT LoanRefinancingRequested;
```

## Node Example

```text
CREATE PROCESS_NODE identify_customer
  USING process_kb
  RELATED_TO user_task.identify_customer TYPE step;
```

## Design Notes

- A process is executable structure.
- A process node should reference tasks, tools, and rules by id.
- The DSL should validate that referenced nodes and tasks exist.

## Ingestion Role

Processes are created during ingestion from corpus or curated authoring. The
compiler should translate the declarative process into the current YAML
definition artifacts and any execution metadata needed by the orchestrator.

## More Examples

```text
CREATE PROCESS money_transfer
  USING process_kb
  VERSION '1.0.0'
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.validate_transfer TYPE step
  RELATED_TO process_node.execute_transfer TYPE step
  RELATED_TO rule.transfer_limit_daily TYPE dependency
  EMITS_EVENT MoneyTransferRequested;
```

```text
CREATE PROCESS savings_account_opening
  USING process_kb
  VERSION '1.0.0'
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.collect_documents TYPE step
  RELATED_TO process_node.kyc_screening TYPE step
  RELATED_TO process_node.create_account TYPE step
  RELATED_TO rule.kyc_must_pass TYPE obligation
  EMITS_EVENT SavingsAccountOpeningRequested;
```

```text
CREATE PROCESS loan_payment
  USING process_kb
  VERSION '1.0.0'
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.review_loan_status TYPE step
  RELATED_TO process_node.apply_payment TYPE step
  RELATED_TO rule.payment_auto_debit_required TYPE obligation
  EMITS_EVENT LoanPaymentRequested;
```

```text
CREATE PROCESS loan_evaluation
  USING process_kb
  VERSION '1.0.0'
  RELATED_TO process_node.collect_application_data TYPE step
  RELATED_TO process_node.score_customer TYPE step
  RELATED_TO process_node.evaluate_eligibility TYPE step
  RELATED_TO rule.evaluation_policy TYPE dependency
  EMITS_EVENT LoanEvaluationRequested;
```

```text
CREATE PROCESS customer_onboarding
  USING process_kb
  VERSION '1.0.0'
  RELATED_TO process_node.identify_customer TYPE step
  RELATED_TO process_node.collect_documents TYPE step
  RELATED_TO process_node.run_kyc TYPE step
  RELATED_TO process_node.approve_onboarding TYPE step
  RELATED_TO rule.onboarding_policy TYPE dependency
  EMITS_EVENT CustomerOnboardingRequested;
```
