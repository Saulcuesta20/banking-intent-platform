from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AssetStatusChanged:
    asset_id: str
    asset_type: str
    old_status: str
    new_status: str
    version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, listener: Callable) -> None:
        self._listeners.setdefault(event_type, []).append(listener)

    def publish(self, event: Any) -> None:
        event_type = type(event).__name__
        for listener in self._listeners.get(event_type, []):
            listener(event)

    def clear(self) -> None:
        self._listeners.clear()


event_bus = EventBus()


def emit_asset_status_change(
    asset_id: str,
    asset_type: str,
    old_status: str,
    new_status: str,
    version: str = "",
    **metadata: Any,
) -> None:
    event = AssetStatusChanged(
        asset_id=asset_id,
        asset_type=asset_type,
        old_status=old_status,
        new_status=new_status,
        version=version,
        metadata=metadata,
    )
    event_bus.publish(event)
