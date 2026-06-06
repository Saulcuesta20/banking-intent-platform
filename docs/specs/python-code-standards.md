# Python Code Standards

## Purpose
Keep Python code easy to read at a glance while preserving validation,
runtime safety, and clear component boundaries.

## Core Rule
Use the simplest class shape that still communicates the role of the object.

```text
Pydantic BaseModel
  -> payloads, YAML/JSON contracts, API bodies, validated domain schemas

@dataclass(frozen=True)
  -> immutable value objects, configuration objects, simple dependency wrappers

@dataclass
  -> small stateful services, registries, in-memory repositories

Protocol
  -> ports/interfaces implemented by providers or adapters

regular class with __init__
  -> external clients, complex adapters, optional imports, runtime setup,
     caching, network configuration, or non-trivial initialization
```

## Style Decisions
- Keep `self`. It is standard Python and makes instance state explicit.
- Avoid manual `__init__` when the class only stores constructor arguments.
- Prefer declarative fields over constructor boilerplate.
- Keep Pydantic for asset definitions, process definitions, tools, answers,
  planning traces, and API contracts.
- Keep service methods small and named after business steps.
- Keep adapters isolated under the component they serve.

## Documentation Standards
- Every public class should have a one- or two-line docstring explaining its
  role in business/runtime language.
- Every public method should have a one-line docstring when its behavior is not
  obvious from the method name.
- Private helpers may skip docstrings when their name and local context are
  enough; add one only for tricky routing, validation, or orchestration logic.
- Pydantic models can be documented at class level or grouped by module when
  the fields already describe the payload.
- Avoid comments that repeat the code. Prefer comments that explain why a
  decision exists.

Example:

```python
class AgentRegistry:
    """In-memory lookup for coordinator, delegator, and worker agents."""

    def get(self, agent_id: str) -> Agent:
        """Return one registered agent or raise a missing-agent error."""
```

## Agent Classes
Agents should read like metadata plus behavior:

```python
@dataclass(frozen=True)
class FlowAgent(AssetSpecialistAgent):
    agent_id: str = "agent.asset.flow"
    name: str = "Flow Agent"
    role: str = "Evaluate user-facing flow candidates."
    asset_type: str = "flow"
```

The base agent exposes `definition` and run helpers. Specialist agents should
not hide their purpose inside constructor code.

## Service Classes
Simple wrapper services should use dataclasses:

```python
@dataclass(frozen=True)
class ApprovalService:
    provider: ApprovalProvider
```

Use a regular class only when initialization contains meaningful setup, such
as HTTP clients, optional LangGraph imports, LLM configuration, file loading,
or driver connections.

## Repository And Registry Classes
Use dataclasses with `__post_init__` when a derived index is built from input
data:

```python
@dataclass
class EnterpriseAssetRepository:
    assets: list[EnterpriseAsset] = field(default_factory=list)

    def __post_init__(self):
        self._assets = {asset.asset_id: asset for asset in self.assets}
```

## Readability Recommendations
- Rename technical variables when the business meaning is known.
- Keep route names stable and visible in one place.
- Prefer `tools` over legacy `actions` in new code.
- Prefer `entity` in new concepts; keep `concept` only for compatibility.
- Keep orchestration steps traceable with names that match documentation.
- Put diagrams and decision rules in `docs/specs` when behavior spans
  multiple components.
