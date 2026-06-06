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
- `app/knowledge_base`
- `app/ask`
- `app/capability`
- `app/approval`
- `app/audit`
- `app/config`

## Data Flow
CLI modules call application services, services use component-local ports, ports are implemented by component-local providers, and output is serialized as JSON.

## Example Input/Output
Command: `python -m app.cli.ask "Quiero refinanciar mi prestamo"`

Output: JSON intent response.

## Interfaces
Each component package exposes simple Python classes or protocols. Provider
contracts live beside the component they serve, for example
`app/ask/providers.py`, `app/capability/providers.py`, and
`app/knowledge_base/ports.py`.

Enterprise asset configuration and approved asset examples live under:

```text
config/asset_registry/asset_types.yaml
```

## Implementation Notes
The first implementation is intentionally small and avoids hidden framework coupling. Component logic belongs in the component folder, while `app/factory.py` only composes services and adapters.

## Future Replacement Strategy
New adapters can be added inside the owning component package, such as
`app/ask/ai.py` or `app/knowledge_base/adapters/graph/neo4j.py`, while keeping
the public CLI stable.

`app/knowledge_base/source_router.py` owns source selection for retrieval. It
is separate from the ask/goal router, which remains in `app/ask` and
`app/planning`.
