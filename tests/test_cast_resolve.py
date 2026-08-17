"""Tests for mDNS Cast UUID parsing."""

from unittest.mock import patch

from src.cast_resolve import CastResolver, normalize_cast_uuid, parse_cast_service, uuid_from_service_name
from src.config import PingTarget


def _target(**kwargs) -> PingTarget:
    defaults = {
        "entity_id": "media_player.living_speaker",
        "device_id": "dev1",
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


def test_normalize_cast_uuid_from_compact():
    assert (
        normalize_cast_uuid("f96863914fa1e713ae01efcb082fef87")
        == "f9686391-4fa1-e713-ae01-efcb082fef87"
    )


def test_uuid_from_service_name():
    name = "Living-speaker-f9686391-4fa1-e713-ae01-efcb082fef87._googlecast._tcp.local."
    assert uuid_from_service_name(name) == "f9686391-4fa1-e713-ae01-efcb082fef87"


def test_parse_cast_service_from_properties():
    with patch("src.cast_resolve.socket.gethostbyname", return_value="192.168.2.45"):
        parsed = parse_cast_service(
            "ignored._googlecast._tcp.local.",
            "living-speaker.local.",
            {b"id": b"f96863914fa1e713ae01efcb082fef87"},
        )
    assert parsed is not None
    uuid, host = parsed
    assert uuid == "f9686391-4fa1-e713-ae01-efcb082fef87"
    assert host == "192.168.2.45"


def test_reapply_failed_hosts_updates_only_failures():
    resolver = CastResolver()
    resolver._cache = {
        "f9686391-4fa1-e713-ae01-efcb082fef87": "192.168.2.99",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee": "192.168.2.50",
    }
    ok = _target(entity_id="media_player.kitchen", cast_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", host="192.168.2.50")
    failed = _target(host="192.168.2.45")

    updated = resolver.reapply_failed_hosts(
        [ok, failed],
        {"media_player.living_speaker"},
        pinned_hosts={},
    )
    assert updated[0].host == "192.168.2.50"
    assert updated[1].host == "192.168.2.99"


def test_reapply_failed_hosts_skips_pinned():
    resolver = CastResolver()
    resolver._cache = {"f9686391-4fa1-e713-ae01-efcb082fef87": "192.168.2.99"}
    failed = _target(host="192.168.2.45")

    updated = resolver.reapply_failed_hosts(
        [failed],
        {"media_player.living_speaker"},
        pinned_hosts={"media_player.living_speaker": "192.168.2.45"},
    )
    assert updated[0].host == "192.168.2.45"
