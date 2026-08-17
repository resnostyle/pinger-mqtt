"""Tests for Cast target discovery from HA registry fixtures."""

from src.config import Settings
from src.ha import HomeAssistantClient

TEST_CAST_UUID = "11111111-2222-3333-4444-555555555555"
TEST_CAST_GROUP_UUID = "22222222-3333-4444-5555-666666666666"
TEST_TV_CAST_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TEST_DISABLED_CAST_UUID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

ENTITY_REGISTRY = [
    {
        "entity_id": "media_player.example_speaker",
        "platform": "cast",
        "device_id": "dev1",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "Example speaker",
        "area_id": None,
    },
    {
        "entity_id": "media_player.example_speaker_2",
        "platform": "cast",
        "device_id": "dev1",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "Example speaker",
        "area_id": None,
    },
    {
        "entity_id": "media_player.cast_group",
        "platform": "cast",
        "device_id": "dev2",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "Example group",
        "area_id": None,
    },
    {
        "entity_id": "media_player.example_tv",
        "platform": "cast",
        "device_id": "dev3",
        "disabled_by": None,
        "hidden_by": None,
        "name": None,
        "original_name": "Example TV",
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
        "name": "Example speaker",
        "manufacturer": "Google Inc.",
        "model": "Google Home",
        "identifiers": [["cast", TEST_CAST_UUID]],
        "area_id": None,
    },
    {
        "id": "dev2",
        "name": "Example group",
        "manufacturer": "Google Inc.",
        "model": "Google Cast Group",
        "identifiers": [["cast", TEST_CAST_GROUP_UUID]],
        "area_id": None,
    },
    {
        "id": "dev3",
        "name": "Example TV",
        "manufacturer": "Example Corp",
        "model": "Example Streamer",
        "identifiers": [["cast", TEST_TV_CAST_UUID]],
        "area_id": None,
    },
    {
        "id": "dev4",
        "name": "Disabled",
        "manufacturer": "Google Inc.",
        "model": "Google Home Mini",
        "identifiers": [["cast", TEST_DISABLED_CAST_UUID]],
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
        ha_url="http://ha.example.test",
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
    ha = FakeHA("http://ha.example.test", "token")
    targets = ha.discover_cast_targets(settings)
    assert len(targets) == 1
    assert targets[0].entity_id == "media_player.example_speaker"
    assert targets[0].cast_uuid == TEST_CAST_UUID
