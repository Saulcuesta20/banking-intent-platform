# Flow DSL

## Purpose

Define user-facing banking intents as governed flow assets.

Flows are the first thing a user normally names in the domain, so the language
should make them easy to declare and inspect.

## Example

```text
CREATE FLOW loan_refinance
  USING process_kb
  INTENT 'Quiero refinanciar mi prestamo'
  BUSINESS_EVENT LoanRefinancingRequested
  DESCRIPTION 'Customer requests a refinance with new terms';
```

## Relationship Example

```text
CREATE FLOW loan_refinance
  RELATED_TO process.loan_refinance TYPE dependency
  RELATED_TO plan.loan_refinance TYPE dependency
  RELATED_TO entity.loan TYPE usage;
```

## Design Notes

- Flow is the user-facing entry point.
- Flow should map to an approved process and supporting assets.
- Flow should be simple enough to author by business teams.

## More Examples

```text
CREATE FLOW money_transfer
  USING process_kb
  INTENT 'Quiero transferir dinero'
  BUSINESS_EVENT MoneyTransferRequested
  DESCRIPTION 'Customer wants to move money between accounts';
```

```text
CREATE FLOW savings_account_open
  USING process_kb
  INTENT 'Quiero abrir una cuenta de ahorro'
  BUSINESS_EVENT SavingsAccountOpeningRequested
  DESCRIPTION 'Customer wants to open a savings account';
```

```text
CREATE FLOW loan_payment
  USING process_kb
  INTENT 'Quiero pagar mi prestamo'
  BUSINESS_EVENT LoanPaymentRequested
  DESCRIPTION 'Customer wants to make a loan payment';
```

```text
CREATE FLOW loan_inquiry
  USING process_kb
  INTENT 'Quiero revisar el estado de mi prestamo'
  BUSINESS_EVENT LoanInformationRequested
  DESCRIPTION 'Customer wants loan status information';
```

```text
CREATE FLOW customer_onboarding
  USING process_kb
  INTENT 'Quiero registrar a un cliente'
  BUSINESS_EVENT CustomerOnboardingRequested
  DESCRIPTION 'Customer onboarding and KYC route';
```

## Ingestion Role

During ingestion, a flow can be generated from raw corpus evidence and then
validated into the repository before indexing.

The DSL should support both:

- creating a new flow
- revising an existing flow
- deleting a draft or rejected flow
