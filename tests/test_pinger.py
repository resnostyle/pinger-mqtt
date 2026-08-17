"""Tests for probe logic."""

import socket
from unittest.mock import patch

from src.config import PingTarget, Settings
from src.pinger import Pinger, ProbeResult, probe_tcp

TEST_HOST = "192.0.2.10"
TEST_CAST_UUID = "11111111-2222-3333-4444-555555555555"


def _settings(**kwargs) -> Settings:
    defaults = {
        "ha_url": "http://ha.example.test",
        "ha_token": "token",
        "mqtt_host": "127.0.0.1",
        "mqtt_port": 1883,
        "mqtt_username": None,
        "mqtt_password": None,
        "mqtt_topic_prefix": "home/ping",
        "mqtt_client_id": "pinger-mqtt",
        "mqtt_discovery_enabled": True,
        "mqtt_discovery_prefix": "homeassistant",
        "ping_interval_seconds": 60,
        "ping_discovery_refresh_seconds": 300,
        "ping_method": "tcp8008",
        "ping_timeout_ms": 2000,
        "ping_tcp_port": 8008,
        "ping_stats_window": 5,
        "ping_manufacturer_filter": frozenset({"Google Inc."}),
        "ping_exclude_models": frozenset({"Google Cast Group"}),
        "ping_host_overrides": {},
        "log_level": "INFO",
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def _target(host: str | None = TEST_HOST) -> PingTarget:
    return PingTarget(
        entity_id="media_player.example_speaker",
        device_id="dev1",
        slug="example_speaker",
        friendly_name="Example speaker",
        cast_uuid=TEST_CAST_UUID,
        manufacturer="Google Inc.",
        model="Google Home",
        area_id=None,
        host=host,
    )


def test_probe_tcp_success():
    with patch("src.pinger.socket.create_connection") as mock_connect:
        mock_connect.return_value.__enter__ = lambda s: s
        mock_connect.return_value.__exit__ = lambda s, *a: None
        result = probe_tcp(TEST_HOST, 8008, 2000)
    assert result.reachable is True
    assert result.latency_ms is not None
    assert result.error is None


def test_probe_tcp_timeout():
    with patch("src.pinger.socket.create_connection", side_effect=socket.timeout):
        result = probe_tcp(TEST_HOST, 8008, 2000)
    assert result.reachable is False
    assert result.error == "timeout"


def test_pinger_rolling_stats():
    pinger = Pinger(_settings(ping_stats_window=3))
    target = _target()

    with patch("src.pinger.probe_tcp", return_value=ProbeResult(True, 10.0, None, "t1")):
        pinger.probe(target)
    with patch("src.pinger.probe_tcp", return_value=ProbeResult(True, 20.0, None, "t2")):
        pinger.probe(target)
    with patch(
        "src.pinger.probe_tcp",
        return_value=ProbeResult(False, None, "timeout", "t3"),
    ):
        _, stats = pinger.probe(target)

    assert stats.probes == 3
    assert stats.success_rate == round(2 / 3, 3)
    assert stats.avg_latency_ms == 15.0
    assert stats.consecutive_failures == 1


def test_unresolved_host():
    pinger = Pinger(_settings())
    result, stats = pinger.probe(_target(host=None))
    assert result.reachable is False
    assert result.error == "unresolved_host"
    assert stats.consecutive_failures == 1
