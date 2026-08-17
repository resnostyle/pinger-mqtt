"""Home Assistant client for Cast device discovery via WebSocket registry."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import websocket

from .config import PingTarget, Settings, slugify

logger = logging.getLogger(__name__)

_SUFFIX_RE = re.compile(r"_(\d+)$")


def _ws_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc or parsed.path
    return f"{scheme}://{host}/api/websocket"


def _extract_cast_uuid(identifiers: list[list[str]] | None) -> str | None:
    if not identifiers:
        return None
    for domain, value in identifiers:
        if domain == "cast" and value:
            return value
    return None


def _entity_score(entity_id: str) -> tuple[int, int]:
    """Prefer canonical entity ids without numeric suffixes."""
    match = _SUFFIX_RE.search(entity_id)
    if match:
        return (1, int(match.group(1)))
    return (0, 0)


class HomeAssistantClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def close(self) -> None:
        return None

    def __enter__(self) -> HomeAssistantClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _ws_request(self, msg_type: str) -> Any:
        ws = websocket.create_connection(
            _ws_url(self._base_url),
            timeout=self._timeout,
        )
        try:
            hello = json.loads(ws.recv())
            if hello.get("type") != "auth_required":
                raise RuntimeError(f"Unexpected HA websocket hello: {hello!r}")

            ws.send(json.dumps({"type": "auth", "access_token": self._token}))
            auth = json.loads(ws.recv())
            if auth.get("type") != "auth_ok":
                raise RuntimeError(f"HA websocket auth failed: {auth!r}")

            ws.send(json.dumps({"id": 1, "type": msg_type}))
            while True:
                raw = ws.recv()
                message = json.loads(raw)
                if message.get("id") == 1:
                    if not message.get("success", False):
                        raise RuntimeError(
                            f"HA websocket {msg_type} failed: {message!r}"
                        )
                    return message.get("result")
        finally:
            ws.close()

    def list_entity_registry(self) -> list[dict[str, Any]]:
        return self._ws_request("config/entity_registry/list")

    def list_device_registry(self) -> list[dict[str, Any]]:
        return self._ws_request("config/device_registry/list")

    def discover_cast_targets(self, settings: Settings) -> list[PingTarget]:
        entities = self.list_entity_registry()
        devices = self.list_device_registry()
        devices_by_id = {d["id"]: d for d in devices}

        candidates: dict[str, list[PingTarget]] = {}
        for entry in entities:
            entity_id = entry.get("entity_id", "")
            if not entity_id.startswith("media_player."):
                continue
            if entry.get("platform") != "cast":
                continue
            if entry.get("disabled_by") is not None:
                continue
            if entry.get("hidden_by") is not None:
                continue

            device_id = entry.get("device_id")
            if not device_id:
                continue

            device = devices_by_id.get(device_id)
            if not device:
                continue

            manufacturer = device.get("manufacturer") or ""
            model = device.get("model") or ""
            if settings.ping_manufacturer_filter and manufacturer not in settings.ping_manufacturer_filter:
                continue
            if model in settings.ping_exclude_models:
                continue

            cast_uuid = _extract_cast_uuid(device.get("identifiers"))
            if not cast_uuid:
                logger.debug("Skipping %s: no cast UUID", entity_id)
                continue

            friendly_name = (
                entry.get("name")
                or entry.get("original_name")
                or device.get("name_by_user")
                or device.get("name")
                or entity_id
            )
            slug_base = entity_id.removeprefix("media_player.")
            target = PingTarget(
                entity_id=entity_id,
                device_id=device_id,
                slug=slugify(slug_base),
                friendly_name=friendly_name,
                cast_uuid=cast_uuid,
                manufacturer=manufacturer,
                model=model,
                area_id=entry.get("area_id") or device.get("area_id"),
                host=settings.ping_host_overrides.get(entity_id),
            )
            candidates.setdefault(device_id, []).append(target)

        selected: list[PingTarget] = []
        for device_id, group in candidates.items():
            group.sort(key=lambda t: (_entity_score(t.entity_id), t.entity_id))
            chosen = group[0]
            if len(group) > 1:
                logger.debug(
                    "Deduped device %s: chose %s over %s",
                    device_id,
                    chosen.entity_id,
                    [t.entity_id for t in group[1:]],
                )
            selected.append(chosen)

        selected.sort(key=lambda t: t.friendly_name.lower())
        logger.info("Discovered %s Cast targets from Home Assistant", len(selected))
        return selected
