"""Tests for Cast target discovery from HA registry fixtures."""

from src.config import Settings
from src.ha import HomeAssistantClient


ENTITY_REGISTRY = [
    {
        "entity_id": "media_player.living_speaker",
        "platform": "cast",
        "device_id": "dev1",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "Living speaker",
        "area_id": None,
    },
    {
        "entity_id": "media_player.living_speaker_2",
        "platform": "cast",
        "device_id": "dev1",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "Living speaker",
        "area_id": None,
    },
    {
        "entity_id": "media_player.everything",
        "platform": "cast",
        "device_id": "dev2",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "everything",
        "area_id": None,
    },
    {
        "entity_id": "media_player.shield_tv",
        "platform": "cast",
        "device_id": "dev3",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "Living Room TV",
        "area_id": None,
    },
    {
        "entity_id": "media_player.disabled_speaker",
        "platform": "cast",
        "device_id": "dev4",
        "disabled_by": "user",
        "hidden_by": None,
        "name": None,
        "original_name": "Disabled",
        "area_id": None,
    },
]

DEVICE_REGISTRY = [
    {
        "id": "dev1",
        "name": "Living speaker",
        "manufacturer": "Google Inc.",
        "model": "Google Home",
        "identifiers": [["cast", "f9686391-4fa1-e713-ae01-efcb082fef87"]],
        "area_id": None,
    },
    {
        "id": "dev2",
        "name": "everything",
        "manufacturer": "Google Inc.",
        "model": "Google Cast Group",
        "identifiers": [["cast", "f20e4562-80d7-4765-9c39-54555d5a9ef9"]],
        "area_id": None,
    },
    {
        "id": "dev3",
        "name": "Living Room TV",
        "manufacturer": "NVIDIA",
        "model": "SHIELD Android TV",
        "identifiers": [["cast", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]],
        "area_id": None,
    },
    {
        "id": "dev4",
        "name": "Disabled",
        "manufacturer": "Google Inc.",
        "model": "Google Home Mini",
        "identifiers": [["cast", "11111111-2222-3333-4444-555555555555"]],
        "area_id": None,
    },
]


class FakeHA(HomeAssistantClient):
    def list_entity_registry(self):
        return ENTITY_REGISTRY

    def list_device_registry(self):
        return DEVICE_REGISTRY


def test_discover_cast_targets_filters_and_dedupes(monkeypatch):
    settings = Settings(
        ha_url="http://ha.local",
        ha_token="token",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        mqtt_topic_prefix="home/ping",
        mqtt_client_id="pinger-mqtt",
        mqtt_discovery_enabled=True,
        mqtt_discovery_prefix="homeassistant",
        ping_interval_seconds=60,
        ping_discovery_refresh_seconds=300,
        ping_method="tcp8008",
        ping_timeout_ms=2000,
        ping_tcp_port=8008,
        ping_stats_window=60,
        ping_manufacturer_filter=frozenset({"Google Inc."}),
        ping_exclude_models=frozenset({"Google Cast Group"}),
        ping_host_overrides={},
        log_level="INFO",
    )
    ha = FakeHA("http://ha.local", "token")
    targets = ha.discover_cast_targets(settings)
    assert len(targets) == 1
    assert targets[0].entity_id == "media_player.living_speaker"
    assert targets[0].cast_uuid == "f9686391-4fa1-e713-ae01-efcb082fef87"
