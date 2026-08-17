"""Unit tests for MQTT payload shaping (no HA/MQTT required)."""

from src.config import PingTarget
from src.payload import build_device_payload, build_summary_payload
from src.pinger import ProbeResult, ProbeStats


def _target(**kwargs) -> PingTarget:
    defaults = {
        "entity_id": "media_player.living_speaker",
        "device_id": "abc123",
        "slug": "living_speaker",
        "friendly_name": "Living speaker",
        "cast_uuid": "f9686391-4fa1-e713-ae01-efcb082fef87",
        "manufacturer": "Google Inc.",
        "model": "Google Home",
        "area_id": None,
        "host": "192.168.2.45",
    }
    defaults.update(kwargs)
    return PingTarget(**defaults)


def test_build_device_payload():
    target = _target()
    result = ProbeResult(True, 12.4, None, "2026-08-17T22:30:00+00:00")
    stats = ProbeStats(
        probes=10,
        successes=9,
        success_rate=0.9,
        avg_latency_ms=14.1,
        consecutive_failures=0,
        last_success_at="2026-08-17T22:30:00+00:00",
    )
    payload = build_device_payload(target, result, stats, method="tcp8008")
    assert payload["entity_id"] == "media_player.living_speaker"
    assert payload["reachable"] is True
    assert payload["latency_ms"] == 12.4
    assert payload["method"] == "tcp8008"
    assert payload["stats"]["success_rate"] == 0.9
    assert "published" in payload


def test_build_summary_payload():
    target = _target()
    ok = ProbeResult(True, 10.0, None, "2026-08-17T22:30:00+00:00")
    fail = ProbeResult(False, None, "timeout", "2026-08-17T22:31:00+00:00")
    stats_ok = ProbeStats(1, 1, 1.0, 10.0, 0, "2026-08-17T22:30:00+00:00")
    stats_fail = ProbeStats(1, 0, 0.0, None, 1, None)
    summary = build_summary_payload(
        [
            (target, ok, stats_ok),
            (target.with_host("192.168.2.46"), fail, stats_fail),
        ],
        method="tcp8008",
    )
    assert summary["device_count"] == 2
    assert summary["reachable_count"] == 1
    assert summary["unreachable_count"] == 1
    assert len(summary["devices"]) == 2
