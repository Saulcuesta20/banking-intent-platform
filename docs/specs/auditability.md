# Auditability

## Purpose
Make AI decisions explainable and traceable.

## Responsibilities
- Capture input question, selected intent, confidence, evidence, provider name, and output.
- Record that no business execution occurred.
- Support review of human approval decisions later.

## Main Components
- Audit event model
- `AuditService`
- `app/audit/providers.py::AuditSink`
- `app/audit/local.py::NoopAuditSink`
- Future database audit adapter

## Data Flow
Use cases call `AuditService` after question answering. Sinks persist, emit, or ignore records according to configuration.

## Example Input/Output
Input event: question answered.

Output audit record: timestamp, intent, evidence, approval required, provider metadata.

## Interfaces
- `AuditService.record_intent_result(question, result)`
- `AuditSink.record(event)`

## Implementation Notes
The MVP keeps audit contracts simple and can run without external storage using `NoopAuditSink`. The component is wired in `app/factory.py`.

## Future Replacement Strategy
Audit storage can move to PostgreSQL, SIEM, or enterprise logging without changing use cases.
