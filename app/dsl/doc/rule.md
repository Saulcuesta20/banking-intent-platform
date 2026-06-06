# Rule DSL

## Purpose

Define business rules in a readable, business-friendly way.

This should feel closer to IBM-style business rule authoring than to low-level
programming. The author writes policy in a structured sentence form, and the
compiler turns it into the governed asset metadata used by the platform.

## Example

```text
CREATE RULE refinance_eligibility
  USING rules_kb
  STATUS approved
  DESCRIPTION 'Eligibility checks for refinance requests'
  WHEN loan.age_months >= 6
   AND customer.payment_history = 'good'
   AND loan.delinquency_days = 0
  THEN approve_refinance = true;
```

## Another Example

```text
CREATE RULE payment_auto_debit_required
  USING rules_kb
  STATUS approved
  WHEN loan.product = 'refinance'
   AND customer.requested_auto_pay = true
  THEN require_bank_account = true;
```

## Design Notes

- Rules should read like business language.
- Rules should be compiled into the asset registry and repository model.
- Rules should remain consultable during ask-time retrieval.
- Rules should not be executed directly by the DSL layer.
- Rules should keep version history and source references so changes can be
  reviewed and traced.

## Ingestion Role

Rules are created during ingestion because they belong to the governed
knowledge set.

The ingest pipeline can produce:

- the rule asset metadata
- normalized conditions
- source references
- version lineage
- validation output
- sync-ready repository rows

## Suggested Rule Forms

- single if-then rule
- decision-table style rule set
- guard rule
- explanation rule
- approval rule

## More Examples

```text
CREATE RULE transfer_limit_daily
  USING rules_kb
  STATUS approved
  WHEN transfer.amount > customer.daily_limit
  THEN require_manual_approval = true;
```

```text
CREATE RULE customer_identity_required
  USING rules_kb
  STATUS approved
  WHEN process = 'loan_refinance'
  THEN require_identity_check = true;
```

```text
CREATE RULE kyc_must_pass
  USING rules_kb
  STATUS approved
  WHEN customer.kyc_status != 'passed'
  THEN block_onboarding = true;
```

```text
CREATE RULE document_missing_block
  USING rules_kb
  STATUS approved
  WHEN required_document.missing = true
  THEN request_missing_documents = true;
```

```text
CREATE RULE low_risk_fast_track
  USING rules_kb
  STATUS approved
  WHEN customer.risk_level = 'low'
   AND customer.payment_history = 'good'
  THEN fast_track_review = true;
```
