"""Resolve Cast device UUIDs to LAN IPs via mDNS."""

from __future__ import annotations

import logging
import re
import socket
import time
from typing import Any

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

from .config import PingTarget

logger = logging.getLogger(__name__)

CAST_SERVICE = "_googlecast._tcp.local."
UUID_RE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def normalize_cast_uuid(value: str) -> str:
    """Normalize Cast UUID to lowercase hyphenated form."""
    cleaned = value.strip().lower().replace("-", "")
    if len(cleaned) != 32 or not re.fullmatch(r"[0-9a-f]+", cleaned):
        return value.strip().lower()
    return (
        f"{cleaned[0:8]}-{cleaned[8:12]}-{cleaned[12:16]}-"
        f"{cleaned[16:20]}-{cleaned[20:32]}"
    )


def uuid_from_service_name(name: str) -> str | None:
    match = UUID_RE.search(name)
    if not match:
        return None
    return normalize_cast_uuid(match.group(1))


def parse_cast_service(
    name: str,
    host: str,
    properties: dict[str, Any] | None,
    addresses: list[str] | None = None,
) -> tuple[str, str] | None:
    """Return (uuid, host_ip) from an mDNS service record."""
    props = properties or {}
    raw_id = props.get(b"id") or props.get("id")
    if raw_id is not None:
        if isinstance(raw_id, bytes):
            raw_id = raw_id.decode("utf-8", errors="replace")
        uuid = normalize_cast_uuid(str(raw_id))
    else:
        parsed = uuid_from_service_name(name)
        if not parsed:
            return None
        uuid = parsed

    if addresses:
        host_ip = addresses[0]
    else:
        try:
            host_ip = socket.gethostbyname(host.rstrip("."))
        except socket.gaierror:
            logger.debug("Could not resolve mDNS host %s for %s", host, name)
            return None
    return uuid, host_ip


class CastResolver:
    def __init__(self, browse_seconds: float = 3.0) -> None:
        self._browse_seconds = browse_seconds
        self._cache: dict[str, str] = {}

    @property
    def cache(self) -> dict[str, str]:
        return dict(self._cache)

    def browse(self) -> dict[str, str]:
        found: dict[str, str] = {}
        zc = Zeroconf()

        def on_service_change(
            zeroconf: Zeroconf,
            service_type: str,
            name: str,
            state_change: ServiceStateChange,
        ) -> None:
            if state_change is ServiceStateChange.Removed:
                return
            info = zeroconf.get_service_info(service_type, name)
            if not info:
                return
            host = info.server or ""
            if not host:
                return
            parsed = parse_cast_service(
                name, host, info.properties, info.parsed_addresses()
            )
            if parsed:
                uuid, host_ip = parsed
                found[uuid] = host_ip

        browser = ServiceBrowser(zc, CAST_SERVICE, handlers=[on_service_change])
        try:
            time.sleep(self._browse_seconds)
        finally:
            browser.cancel()
            zc.close()

        self._cache.update(found)
        logger.info("mDNS browse found %s Cast hosts", len(found))
        return dict(self._cache)

    def refresh_cache(self) -> dict[str, str]:
        """Force a new mDNS browse and merge results into the cache."""
        logger.info("Refreshing mDNS host cache")
        return self.browse()

    def lookup_host(self, cast_uuid: str) -> str | None:
        return self._cache.get(normalize_cast_uuid(cast_uuid))

    def resolve_targets(self, targets: list[PingTarget]) -> list[PingTarget]:
        if not self._cache:
            self.browse()

        resolved: list[PingTarget] = []
        for target in targets:
            if target.host:
                resolved.append(target)
                continue
            host = self.lookup_host(target.cast_uuid)
            if host:
                resolved.append(target.with_host(host))
            else:
                logger.warning(
                    "No mDNS host for %s (%s, uuid=%s)",
                    target.friendly_name,
                    target.entity_id,
                    target.cast_uuid,
                )
                resolved.append(target)
        return resolved

    def reapply_failed_hosts(
        self,
        targets: list[PingTarget],
        failed_entity_ids: set[str],
        *,
        pinned_hosts: dict[str, str],
    ) -> list[PingTarget]:
        """Re-resolve hosts from cache for failed targets only."""
        if not failed_entity_ids:
            return targets

        updated: list[PingTarget] = []
        for target in targets:
            if target.entity_id not in failed_entity_ids:
                updated.append(target)
                continue
            if target.entity_id in pinned_hosts:
                updated.append(target)
                continue
            host = self.lookup_host(target.cast_uuid)
            if host and host != target.host:
                logger.info(
                    "Updated host for %s after failure: %s -> %s",
                    target.friendly_name,
                    target.host,
                    host,
                )
                updated.append(target.with_host(host))
            else:
                updated.append(target)
        return updated
