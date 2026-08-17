"""Tests for Home Assistant MQTT discovery configs."""

from src.config import PingTarget
from src.discovery import build_discovery_configs


def _target() -> PingTarget:
    return PingTarget(
        entity_id="media_player.living_speaker",
        device_id="abc123",
        slug="living_speaker",
        friendly_name="Living speaker",
        cast_uuid="f9686391-4fa1-e713-ae01-efcb082fef87",
        manufacturer="Google Inc.",
        model="Google Home",
        area_id=None,
        host="192.168.2.45",
    )


def test_discovery_includes_latency_and_reachable():
    configs = build_discovery_configs("home/ping", _target())
    by_id = {object_id: (cfg, component) for object_id, cfg, component in configs}

    latency_id, (latency_cfg, latency_component) = next(
        (k, v) for k, v in by_id.items() if v[1] == "sensor"
    )
    assert latency_id == "pinger_mqtt_living_speaker_latency"
    assert latency_cfg["state_topic"] == "home/ping/living_speaker/current"
    assert latency_cfg["value_template"] == "{{ value_json.latency_ms }}"
    assert latency_cfg["state_class"] == "measurement"
    assert latency_cfg["unit_of_measurement"] == "ms"
    assert latency_cfg["device"]["identifiers"] == ["pinger_mqtt_living_speaker"]
    assert latency_cfg["device"]["name"] == "Pinger MQTT (Living speaker)"

    reachable_id, (reachable_cfg, reachable_component) = next(
        (k, v) for k, v in by_id.items() if v[1] == "binary_sensor"
    )
    assert reachable_id == "pinger_mqtt_living_speaker_reachable"
    assert reachable_component == "binary_sensor"
    assert reachable_cfg["device_class"] == "connectivity"
    assert "value_json.reachable" in reachable_cfg["value_template"]

    assert len(configs) == 2
