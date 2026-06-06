# Entity DSL

## Purpose

Define the domain vocabulary used by the knowledge base and ask routing.

Entities are the canonical business nouns that anchor retrieval and
normalization.

## Example

```text
CREATE ENTITY loan
  USING business_model_kb
  ATTRIBUTE loan_id TYPE string REQUIRED
  ATTRIBUTE principal_amount TYPE decimal REQUIRED
  ATTRIBUTE currency TYPE string REQUIRED
  ATTRIBUTE term_months TYPE integer REQUIRED
  ATTRIBUTE interest_rate TYPE decimal REQUIRED
  ATTRIBUTE status TYPE string OPTIONAL
  SYNONYM 'prestamo'
  SYNONYM 'credito'
  SYNONYM 'loan';
```

## Another Example

```text
CREATE ENTITY savings_account
  USING business_model_kb
  ATTRIBUTE account_id TYPE string REQUIRED
  ATTRIBUTE account_number TYPE string REQUIRED
  ATTRIBUTE balance TYPE decimal REQUIRED
  ATTRIBUTE currency TYPE string REQUIRED
  ATTRIBUTE opening_date TYPE date OPTIONAL
  SYNONYM 'cuenta de ahorro'
  SYNONYM 'savings account';
```

## Typed Attributes

Entities should support typed attributes because they model the business object,
not just its name.

Suggested DSL pattern:

```text
ATTRIBUTE <name> TYPE <data_type> <REQUIRED|OPTIONAL>
```

Suggested primitive types:

- `string`
- `integer`
- `decimal`
- `boolean`
- `date`
- `datetime`
- `enum`
- `json`

Optional future extensions:

- `array<string>`
- `array<decimal>`
- `reference<entity>`

## Design Notes

- Entities should replace legacy concept naming over time.
- Synonyms are not separate business assets in the MVP.
- The compiler should normalize synonyms into the existing vocabulary model.
- Entities should support explicit relations to other governed assets.
- Entity relations should be version-aware and validated before apply.
- A referenced entity must not create a second canonical copy of the same meaning.

## Ingestion Role

The ingestion pipeline should extract entities, synonyms, and relation hints
from corpus sources and emit them as governed metadata.

## Relations And Connections

An entity can connect to other assets through relationships stored in the
catalog payload and the relationships table.

Common relation patterns:

```text
entity.loan
  has_synonym -> prestamo
  related_to entity.payment type dependency
  related_to flow.loan_refinance type usage
  related_to process.loan_refinance type usage
  related_to qa.refinance_help type explanation
```

```text
entity.customer
  has_synonym -> cliente
  related_to entity.account type dependency
  related_to flow.customer_onboarding type usage
  related_to process.customer_onboarding type usage
  related_to qa.kyc_steps type explanation
```

```text
entity.document
  has_synonym -> documento
  related_to flow.customer_onboarding type usage
  related_to process.customer_onboarding type usage
  related_to user_task.collect_documents type usage
```

## What An Entity May Reference

- other entities
- flows that use the entity in routing
- processes that act on the entity
- rules that validate the entity's conditions
- user tasks that read or modify the entity
- tools that query or update the entity
- QA assets that explain the entity

## What Should Be Validated

- the target asset exists or is staged
- the relation type is allowed by the asset registry
- the entity stays owned by `business_model_kb`
- the relationship does not create a duplicate canonical meaning
- deletion or deprecation of the target asset surfaces impact to the entity

## Example With Multiple Connections

```text
CREATE ENTITY loan USING business_model_kb
  ATTRIBUTE loan_id TYPE string REQUIRED
  ATTRIBUTE principal_amount TYPE decimal REQUIRED
  ATTRIBUTE currency TYPE string REQUIRED
  ATTRIBUTE term_months TYPE integer REQUIRED
  ATTRIBUTE delinquency_days TYPE integer OPTIONAL
  SYNONYM 'prestamo'
  SYNONYM 'credito'
  RELATED_TO entity.customer TYPE dependency
  RELATED_TO entity.payment TYPE dependency
  RELATED_TO flow.loan_refinance TYPE usage
  RELATED_TO process.loan_refinance TYPE usage
  RELATED_TO qa.refinance_help TYPE explanation;
```

```text
CREATE ENTITY customer USING business_model_kb
  ATTRIBUTE customer_id TYPE string REQUIRED
  ATTRIBUTE full_name TYPE string REQUIRED
  ATTRIBUTE risk_level TYPE enum OPTIONAL
  ATTRIBUTE kyc_status TYPE enum OPTIONAL
  ATTRIBUTE segment TYPE string OPTIONAL
  SYNONYM 'cliente'
  RELATED_TO entity.account TYPE dependency
  RELATED_TO entity.document TYPE dependency
  RELATED_TO flow.customer_onboarding TYPE usage
  RELATED_TO process.customer_onboarding TYPE usage
  RELATED_TO qa.kyc_steps TYPE explanation;
```

```text
CREATE ENTITY payment USING business_model_kb
  ATTRIBUTE payment_id TYPE string REQUIRED
  ATTRIBUTE amount TYPE decimal REQUIRED
  ATTRIBUTE payment_date TYPE date REQUIRED
  ATTRIBUTE channel TYPE string OPTIONAL
  SYNONYM 'pago'
  RELATED_TO entity.loan TYPE dependency
  RELATED_TO flow.loan_payment TYPE usage
  RELATED_TO process.loan_payment TYPE usage
  RELATED_TO rule.payment_auto_debit_required TYPE obligation;
```

## More Typed Examples

```text
CREATE ENTITY transfer
  USING business_model_kb
  ATTRIBUTE transfer_id TYPE string REQUIRED
  ATTRIBUTE amount TYPE decimal REQUIRED
  ATTRIBUTE source_account_id TYPE string REQUIRED
  ATTRIBUTE target_account_id TYPE string REQUIRED
  ATTRIBUTE execution_date TYPE datetime OPTIONAL
  SYNONYM 'transferencia'
  SYNONYM 'transfer';
```

```text
CREATE ENTITY document
  USING business_model_kb
  ATTRIBUTE document_id TYPE string REQUIRED
  ATTRIBUTE document_type TYPE enum REQUIRED
  ATTRIBUTE issue_date TYPE date OPTIONAL
  ATTRIBUTE expiration_date TYPE date OPTIONAL
  ATTRIBUTE verified TYPE boolean OPTIONAL
  SYNONYM 'documento'
  SYNONYM 'evidence';
```

## Suggested Connection Keywords

For the DSL, these keywords are the most useful for entity modeling:

- `RELATED_TO`
- `TYPE`
- `dependency`
- `obligation`
- `optionality`
- `step`
- `transition`
- `usage`
- `explanation`
- `HAS_SYNONYM`

These should compile into the catalog relationships and the normalized payload
relations.

## More Examples

```text
CREATE ENTITY customer
  USING business_model_kb
  SYNONYM 'cliente'
  SYNONYM 'customer';
```

```text
CREATE ENTITY payment
  USING business_model_kb
  SYNONYM 'pago'
  SYNONYM 'payment';
```

```text
CREATE ENTITY transfer
  USING business_model_kb
  SYNONYM 'transferencia'
  SYNONYM 'transfer';
```

```text
CREATE ENTITY refinance
  USING business_model_kb
  SYNONYM 'refinanciamiento'
  SYNONYM 'refinance';
```

```text
CREATE ENTITY document
  USING business_model_kb
  SYNONYM 'documento'
  SYNONYM 'evidence';
```
