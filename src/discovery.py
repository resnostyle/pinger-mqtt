"""Home Assistant MQTT discovery configs for pinger-mqtt sensors."""

from __future__ import annotations

from typing import Any

from .config import PingTarget

DEVICE_MANUFACTURER = "pinger-mqtt"


def device_block(target: PingTarget) -> dict[str, Any]:
    return {
        "identifiers": [f"pinger_mqtt_{target.slug}"],
        "name": f"Pinger MQTT ({target.friendly_name})",
        "manufacturer": DEVICE_MANUFACTURER,
        "model": target.model or "Google Cast",
    }


def _base_config(
    *,
    object_id: str,
    name: str,
    state_topic: str,
    value_template: str,
    unique_id: str,
    device: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "unique_id": unique_id,
        "state_topic": state_topic,
        "value_template": value_template,
        "device": device,
        "object_id": object_id,
    }


def build_discovery_configs(
    topic_prefix: str,
    target: PingTarget,
) -> list[tuple[str, dict[str, Any], str]]:
    """Return (object_id, config, component) tuples for one ping target."""
    current = f"{topic_prefix}/{target.slug}/current"
    device = device_block(target)
    uid = f"pinger_mqtt_{target.slug}"

    latency = _base_config(
        object_id=f"{uid}_latency",
        name="Latency",
        state_topic=current,
        value_template="{{ value_json.latency_ms }}",
        unique_id=f"{uid}_latency",
        device=device,
    )
    latency["state_class"] = "measurement"
    latency["unit_of_measurement"] = "ms"
    latency["icon"] = "mdi:speedometer"
    latency["json_attributes_topic"] = current

    reachable = _base_config(
        object_id=f"{uid}_reachable",
        name="Reachable",
        state_topic=current,
        value_template="{{ 'true' if value_json.reachable else 'false' }}",
        unique_id=f"{uid}_reachable",
        device=device,
    )
    reachable["device_class"] = "connectivity"
    reachable["payload_on"] = "true"
    reachable["payload_off"] = "false"
    reachable["icon"] = "mdi:lan-connect"
    reachable["json_attributes_topic"] = current

    return [
        (f"{uid}_latency", latency, "sensor"),
        (f"{uid}_reachable", reachable, "binary_sensor"),
    ]
