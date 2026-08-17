"""MQTT publisher for retained ping topics."""

from __future__ import annotations

import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MqttPublisher:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        client_id: str,
        username: str | None = None,
        password: str | None = None,
        topic_prefix: str = "home/ping",
    ) -> None:
        self._topic_prefix = topic_prefix.rstrip("/")
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        if username:
            self._client.username_pw_set(username, password)
        self._client.connect(host, port, keepalive=60)
        self._client.loop_start()
        logger.info("Connected to MQTT %s:%s (prefix=%s)", host, port, self._topic_prefix)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    @property
    def topic_prefix(self) -> str:
        return self._topic_prefix

    def publish_raw(self, topic: str, payload: dict[str, Any], *, retain: bool = True) -> None:
        body = json.dumps(payload, separators=(",", ":"), default=str)
        result = self._client.publish(topic, body, qos=1, retain=retain)
        result.wait_for_publish(timeout=10)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed for {topic}: rc={result.rc}")
        logger.info("Published %s (%s bytes, retain=%s)", topic, len(body), retain)

    def publish(self, suffix: str, payload: dict[str, Any], *, retain: bool = True) -> None:
        topic = f"{self._topic_prefix}/{suffix.lstrip('/')}"
        self.publish_raw(topic, payload, retain=retain)

    def publish_discovery(
        self,
        configs: list[tuple[str, dict[str, Any], str]],
        *,
        discovery_prefix: str = "homeassistant",
    ) -> None:
        prefix = discovery_prefix.rstrip("/")
        for object_id, config, component in configs:
            topic = f"{prefix}/{component}/{object_id}/config"
            self.publish_raw(topic, config, retain=True)
