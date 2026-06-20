from app.events import (
    AssetStatusChanged,
    EventBus,
    emit_asset_status_change,
    event_bus,
)


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("AssetStatusChanged", lambda e: received.append(e))

        event = AssetStatusChanged(
            asset_id="a1", asset_type="flow", old_status="draft", new_status="active"
        )
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    def test_multiple_listeners(self):
        bus = EventBus()
        results_a, results_b = [], []
        bus.subscribe("AssetStatusChanged", lambda e: results_a.append("a"))
        bus.subscribe("AssetStatusChanged", lambda e: results_b.append("b"))

        bus.publish(AssetStatusChanged(
            asset_id="a1", asset_type="flow", old_status="draft", new_status="active"
        ))

        assert results_a == ["a"]
        assert results_b == ["b"]

    def test_unrelated_event_type_not_delivered(self):
        bus = EventBus()
        received = []
        bus.subscribe("SomethingElse", lambda e: received.append(e))

        bus.publish(AssetStatusChanged(
            asset_id="a1", asset_type="flow", old_status="draft", new_status="active"
        ))

        assert received == []

    def test_clear_removes_all_listeners(self):
        bus = EventBus()
        received = []
        bus.subscribe("AssetStatusChanged", lambda e: received.append(e))

        bus.clear()
        bus.publish(AssetStatusChanged(
            asset_id="a1", asset_type="flow", old_status="draft", new_status="active"
        ))

        assert received == []


class TestEmitAssetStatusChange:
    def test_emits_event_on_global_bus(self):
        received = []
        event_bus.subscribe("AssetStatusChanged", lambda e: received.append(e))

        try:
            emit_asset_status_change(
                asset_id="a2",
                asset_type="ontology",
                old_status="active",
                new_status="deprecated",
                version="3",
                reason="superseded",
            )

            assert len(received) == 1
            evt = received[0]
            assert isinstance(evt, AssetStatusChanged)
            assert evt.asset_id == "a2"
            assert evt.asset_type == "ontology"
            assert evt.old_status == "active"
            assert evt.new_status == "deprecated"
            assert evt.version == "3"
            assert evt.metadata == {"reason": "superseded"}
        finally:
            event_bus.clear()
