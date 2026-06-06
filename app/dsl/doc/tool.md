# Tool DSL

## Purpose

Define the lowest approved capability level.

Tools can be backend, frontend, or LLM tools depending on how they are
invoked.

## Example

```text
CREATE TOOL customer.read
  TYPE backend_tool
  PROTOCOL http
  ENDPOINT 'https://banking.example/api/customers/{id}'
  DESCRIPTION 'Read customer data';
```

## Frontend Tool Example

```text
CREATE TOOL ui.refinance.calculate
  TYPE frontend_tool
  FRONTEND_EVENT 'refinance.calculate.submit'
  DESCRIPTION 'Trigger refinance calculation from the UI';
```

## LLM Tool Example

```text
CREATE TOOL llm.corpus.extract
  TYPE llm_tool
  OPERATION json_completion
  MODEL 'gpt-4o-mini'
  DESCRIPTION 'Extract structured assets from corpus';
```

## Design Notes

- Tools are the final approved capability level.
- The DSL should forbid inventing new tools at runtime.
- A tool definition should compile into the canonical tool registry.

## Ingestion Role

Tools are created from approved source patterns and then validated into the
business model KB before downstream flows and tasks reference them.

## More Examples

```text
CREATE TOOL customer.identity.validate
  TYPE backend_tool
  PROTOCOL http
  ENDPOINT 'https://banking.example/api/identity/validate'
  DESCRIPTION 'Validate customer identity';
```

```text
CREATE TOOL loan.conditions.calculate
  TYPE backend_tool
  PROTOCOL http
  ENDPOINT 'https://banking.example/api/loan/conditions/calculate'
  DESCRIPTION 'Calculate refinance or loan conditions';
```

```text
CREATE TOOL account.create
  TYPE backend_tool
  PROTOCOL http
  ENDPOINT 'https://banking.example/api/accounts/create'
  DESCRIPTION 'Create a banking account';
```

```text
CREATE TOOL transfer.submit
  TYPE backend_tool
  PROTOCOL http
  ENDPOINT 'https://banking.example/api/transfers/submit'
  DESCRIPTION 'Submit a transfer request';
```

```text
CREATE TOOL ui.document.upload
  TYPE frontend_tool
  FRONTEND_EVENT 'document.upload.submit'
  DESCRIPTION 'Upload document from UI';
```
