"""Unit tests for MQTT payload shaping (no HA/MQTT required)."""

from src.config import PingTarget
from src.payload import build_device_payload, build_summary_payload
from src.pinger import ProbeResult, ProbeStats

TEST_HOST = "192.0.2.10"
TEST_HOST_OTHER = "192.0.2.20"
TEST_CAST_UUID = "11111111-2222-3333-4444-555555555555"


def _target(**kwargs) -> PingTarget:
    defaults = {
        "entity_id": "media_player.example_speaker",
        "device_id": "abc123",
        "slug": "example_speaker",
        "friendly_name": "Example speaker",
        "cast_uuid": TEST_CAST_UUID,
        "manufacturer": "Google Inc.",
        "model": "Google Home",
        "area_id": None,
        "host": TEST_HOST,
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
    assert payload["entity_id"] == "media_player.example_speaker"
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
            (target.with_host(TEST_HOST_OTHER), fail, stats_fail),
        ],
        method="tcp8008",
    )
    assert summary["device_count"] == 2
    assert summary["reachable_count"] == 1
    assert summary["unreachable_count"] == 1
    assert len(summary["devices"]) == 2
