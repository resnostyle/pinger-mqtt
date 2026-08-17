"""Tests for Home Assistant MQTT discovery configs."""

from src.config import PingTarget
from src.discovery import build_discovery_configs

TEST_HOST = "192.0.2.10"
TEST_CAST_UUID = "11111111-2222-3333-4444-555555555555"


def _target() -> PingTarget:
    return PingTarget(
        entity_id="media_player.example_speaker",
        device_id="abc123",
        slug="example_speaker",
        friendly_name="Example speaker",
        cast_uuid=TEST_CAST_UUID,
        manufacturer="Google Inc.",
        model="Google Home",
        area_id=None,
        host=TEST_HOST,
    )


def test_discovery_includes_latency_and_reachable():
    configs = build_discovery_configs("home/ping", _target())
    by_id = {object_id: (cfg, component) for object_id, cfg, component in configs}

    latency_id, (latency_cfg, latency_component) = next(
        (k, v) for k, v in by_id.items() if v[1] == "sensor"
    )
    assert latency_id == "pinger_mqtt_example_speaker_latency"
    assert latency_cfg["state_topic"] == "home/ping/example_speaker/current"
    assert latency_cfg["value_template"] == "{{ value_json.latency_ms }}"
    assert latency_cfg["state_class"] == "measurement"
    assert latency_cfg["unit_of_measurement"] == "ms"
    assert latency_cfg["device"]["identifiers"] == ["pinger_mqtt_example_speaker"]
    assert latency_cfg["device"]["name"] == "Pinger MQTT (Example speaker)"

    reachable_id, (reachable_cfg, reachable_component) = next(
        (k, v) for k, v in by_id.items() if v[1] == "binary_sensor"
    )
    assert reachable_id == "pinger_mqtt_example_speaker_reachable"
    assert reachable_component == "binary_sensor"
    assert reachable_cfg["device_class"] == "connectivity"
    assert "value_json.reachable" in reachable_cfg["value_template"]

    assert len(configs) == 2
