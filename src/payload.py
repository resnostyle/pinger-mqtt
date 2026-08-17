"""Shape ping probe results into MQTT JSON payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import PingTarget
from .pinger import ProbeResult, ProbeStats


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_device_payload(
    target: PingTarget,
    result: ProbeResult,
    stats: ProbeStats,
    *,
    method: str,
) -> dict[str, Any]:
    return {
        "entity_id": target.entity_id,
        "friendly_name": target.friendly_name,
        "slug": target.slug,
        "host": target.host,
        "cast_uuid": target.cast_uuid,
        "manufacturer": target.manufacturer,
        "model": target.model,
        "area_id": target.area_id,
        "reachable": result.reachable,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "method": method,
        "stats": stats.to_dict(),
        "probed_at": result.probed_at,
        "published": _utc_now_iso(),
    }


def build_summary_payload(
    results: list[tuple[PingTarget, ProbeResult, ProbeStats]],
    *,
    method: str,
) -> dict[str, Any]:
    devices: list[dict[str, Any]] = []
    reachable_count = 0
    for target, result, stats in results:
        if result.reachable:
            reachable_count += 1
        devices.append(
            {
                "slug": target.slug,
                "entity_id": target.entity_id,
                "friendly_name": target.friendly_name,
                "host": target.host,
                "reachable": result.reachable,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "stats": stats.to_dict(),
            }
        )
    return {
        "method": method,
        "device_count": len(results),
        "reachable_count": reachable_count,
        "unreachable_count": len(results) - reachable_count,
        "devices": devices,
        "published": _utc_now_iso(),
    }
