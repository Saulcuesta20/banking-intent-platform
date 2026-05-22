# Repository Structure

## Purpose
Define the project layout for a small but extensible MVP.

## Responsibilities
- Keep modules aligned to business capabilities.
- Make infrastructure replaceable.
- Separate data, docs, tests, and application code.

## Main Components
- `app/cli`
- `app/ingestion`
- `app/ontology`
- `app/graph`
- `app/intent`
- `app/planning`
- `app/decomposition`
- `app/capability`
- `app/events`
- `app/approval`
- `app/audit`
- `app/config`

## Data Flow
CLI modules call application services, services use component-local ports, ports are implemented by component-local providers, and output is serialized as JSON.

## Example Input/Output
Command: `python -m app.cli.ask "Quiero refinanciar mi prestamo"`

Output: JSON intent response.

## Interfaces
Each component package exposes simple Python classes or protocols. Provider contracts live beside the component they serve, for example `app/planning/providers.py`, `app/capability/providers.py`, and `app/ontology/providers.py`.

## Implementation Notes
The first implementation is intentionally small and avoids hidden framework coupling. Component logic belongs in the component folder, while `app/factory.py` only composes services and adapters.

## Future Replacement Strategy
New adapters can be added inside the owning component package, such as `app/planning/ai.py` or `app/retrieval/ai.py`, while keeping the public CLI stable.
