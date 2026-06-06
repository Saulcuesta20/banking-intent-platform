# User Task DSL

## Purpose

Define reusable work units composed of tools.

User tasks are not the lowest executable level. They are the business-facing
composition layer above tools.

## Example

```text
CREATE USER_TASK identify_customer
  USING business_model_kb
  DESCRIPTION 'Identify the customer before account or loan operations'
  RELATED_TO tool.customer.read TYPE usage
  RELATED_TO tool.customer.identity.validate TYPE usage;
```

## Another Example

```text
CREATE USER_TASK review_loan_status
  USING business_model_kb
  RELATED_TO tool.loan.status.read TYPE usage
  RELATED_TO tool.loan.payment.history.read TYPE usage;
```

## Design Notes

- Tasks should be reusable across flows and processes.
- Tasks should only reference approved tools.
- Tasks should be easy to inspect in the dictionary view.

## Ingestion Role

Tasks are created when the corpus or curated source identifies a stable unit
of work. The task should be written into the governed asset repository and
then projected into graph and search indexes.

## More Examples

```text
CREATE USER_TASK collect_documents
  USING business_model_kb
  DESCRIPTION 'Collect supporting documents from the user'
  RELATED_TO tool.document.upload TYPE usage
  RELATED_TO tool.document.validate TYPE usage;
```

```text
CREATE USER_TASK run_kyc_screening
  USING business_model_kb
  DESCRIPTION 'Run KYC and identity checks'
  RELATED_TO tool.kyc.screen TYPE usage
  RELATED_TO tool.customer.identity.validate TYPE usage;
```

```text
CREATE USER_TASK prepare_loan_proposal
  USING business_model_kb
  DESCRIPTION 'Prepare a loan proposal for review'
  RELATED_TO tool.loan.proposal.generate TYPE usage
  RELATED_TO tool.loan.conditions.calculate TYPE usage;
```

```text
CREATE USER_TASK execute_transfer
  USING business_model_kb
  DESCRIPTION 'Execute a money transfer after validation'
  RELATED_TO tool.account.debit TYPE usage
  RELATED_TO tool.transfer.submit TYPE usage;
```

```text
CREATE USER_TASK create_savings_account
  USING business_model_kb
  DESCRIPTION 'Create a savings account'
  RELATED_TO tool.account.create TYPE usage
  RELATED_TO tool.account.open.confirm TYPE usage;
```
