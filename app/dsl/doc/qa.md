# QA DSL

## Purpose

Define approved direct-answer knowledge.

QA assets are the simplest readable knowledge objects in the system and can be
used when the answer does not need a process or a deep workflow.

## Example

```text
CREATE QA refinance_help
  USING qa_kb
  QUESTION 'Que necesito para refinanciar mi prestamo?'
  ANSWER 'Necesitas validar identidad, revisar elegibilidad y confirmar condiciones.'
  STATUS approved;
```

## Another Example

```text
CREATE QA account_opening_docs
  USING qa_kb
  QUESTION 'Que documentos necesito para abrir una cuenta?'
  ANSWER 'Identificacion oficial, comprobante de domicilio y datos de contacto.'
  STATUS approved;
```

## Design Notes

- QA assets should be concise and source-backed.
- QA assets should remain consultable during ask-time retrieval.
- QA assets should be authored through the same registry and validation path
  as the rest of the assets.

## Ingestion Role

QA entries are often extracted from curated corpus material, then normalized
and approved during ingestion.

## More Examples

```text
CREATE QA transfer_limits
  USING qa_kb
  QUESTION 'Cual es el limite diario de transferencias?'
  ANSWER 'Depende del perfil del cliente y de la politica vigente.'
  STATUS approved;
```

```text
CREATE QA kyc_steps
  USING qa_kb
  QUESTION 'Que pasos incluye KYC?'
  ANSWER 'Identidad, documentos, validacion y aprobacion.'
  STATUS approved;
```

```text
CREATE QA loan_payment_options
  USING qa_kb
  QUESTION 'Como puedo pagar mi prestamo?'
  ANSWER 'Pago en sucursal, cargo automatico o transferencia.'
  STATUS approved;
```

```text
CREATE QA refinance_rules
  USING qa_kb
  QUESTION 'Cuales son las reglas para refinanciar?'
  ANSWER 'Depende del historial, antiguedad y politica vigente.'
  STATUS approved;
```

```text
CREATE QA savings_opening_requirements
  USING qa_kb
  QUESTION 'Que necesito para abrir una cuenta de ahorro?'
  ANSWER 'Identificacion, domicilio y datos de contacto.'
  STATUS approved;
```
