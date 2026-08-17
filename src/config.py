"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _parse_csv(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _parse_host_overrides(raw: str) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise SystemExit(
                f"Invalid PING_HOST_OVERRIDES entry {part!r}; "
                "expected entity_id:host"
            )
        entity_id, host = part.split(":", 1)
        entity_id = entity_id.strip()
        host = host.strip()
        if not entity_id or not host:
            raise SystemExit(
                f"Invalid PING_HOST_OVERRIDES entry {part!r}; "
                "expected entity_id:host"
            )
        overrides[entity_id] = host
    return overrides


_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("_", value.strip().lower())
    slug = slug.strip("_")
    return slug or "device"


@dataclass(frozen=True)
class PingTarget:
    """One Google Cast device to monitor."""

    entity_id: str
    device_id: str
    slug: str
    friendly_name: str
    cast_uuid: str
    manufacturer: str
    model: str
    area_id: str | None
    host: str | None = None

    def with_host(self, host: str | None) -> PingTarget:
        return replace(self, host=host)


@dataclass(frozen=True)
class Settings:
    ha_url: str
    ha_token: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_topic_prefix: str
    mqtt_client_id: str
    mqtt_discovery_enabled: bool
    mqtt_discovery_prefix: str
    ping_interval_seconds: int
    ping_discovery_refresh_seconds: int
    ping_method: str
    ping_timeout_ms: int
    ping_tcp_port: int
    ping_stats_window: int
    ping_manufacturer_filter: frozenset[str]
    ping_exclude_models: frozenset[str]
    ping_host_overrides: dict[str, str]
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        username = os.environ.get("MQTT_USERNAME", "").strip() or None
        password = os.environ.get("MQTT_PASSWORD", "").strip() or None
        discovery_raw = os.environ.get("MQTT_DISCOVERY_ENABLED", "true").strip().lower()
        ping_method = os.environ.get("PING_METHOD", "tcp8008").strip().lower()
        if ping_method not in ("tcp8008", "icmp"):
            raise SystemExit(
                f"Invalid PING_METHOD {ping_method!r}; expected tcp8008 or icmp"
            )
        return cls(
            ha_url=_require("HA_URL").rstrip("/"),
            ha_token=_require("HA_TOKEN"),
            mqtt_host=os.environ.get("MQTT_HOST", "127.0.0.1").strip(),
            mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
            mqtt_username=username,
            mqtt_password=password,
            mqtt_topic_prefix=os.environ.get(
                "MQTT_TOPIC_PREFIX", "home/ping"
            ).strip().rstrip("/"),
            mqtt_client_id=os.environ.get("MQTT_CLIENT_ID", "pinger-mqtt").strip(),
            mqtt_discovery_enabled=discovery_raw in ("1", "true", "yes", "on"),
            mqtt_discovery_prefix=os.environ.get(
                "MQTT_DISCOVERY_PREFIX", "homeassistant"
            ).strip().rstrip("/"),
            ping_interval_seconds=int(os.environ.get("PING_INTERVAL_SECONDS", "60")),
            ping_discovery_refresh_seconds=int(
                os.environ.get("PING_DISCOVERY_REFRESH_SECONDS", "300")
            ),
            ping_method=ping_method,
            ping_timeout_ms=int(os.environ.get("PING_TIMEOUT_MS", "2000")),
            ping_tcp_port=int(os.environ.get("PING_TCP_PORT", "8008")),
            ping_stats_window=int(os.environ.get("PING_STATS_WINDOW", "60")),
            ping_manufacturer_filter=_parse_csv(
                os.environ.get("PING_MANUFACTURER_FILTER", "Google Inc.")
            ),
            ping_exclude_models=_parse_csv(
                os.environ.get("PING_EXCLUDE_MODELS", "Google Cast Group")
            ),
            ping_host_overrides=_parse_host_overrides(
                os.environ.get("PING_HOST_OVERRIDES", "")
            ),
            log_level=os.environ.get("LOG_LEVEL", "INFO").strip().upper(),
        )
