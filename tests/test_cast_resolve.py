"""Tests for mDNS Cast UUID parsing."""

from unittest.mock import patch

from src.cast_resolve import CastResolver, normalize_cast_uuid, parse_cast_service, uuid_from_service_name
from src.config import PingTarget

# RFC 5737 documentation addresses and synthetic device identifiers only.
TEST_HOST = "192.0.2.10"
TEST_HOST_ALT = "192.0.2.20"
TEST_HOST_UPDATED = "192.0.2.30"
TEST_CAST_UUID = "11111111-2222-3333-4444-555555555555"
TEST_CAST_UUID_COMPACT = "11111111222233334444555555555555"
TEST_CAST_UUID_OTHER = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _target(**kwargs) -> PingTarget:
    defaults = {
        "entity_id": "media_player.example_speaker",
        "device_id": "dev1",
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


def test_normalize_cast_uuid_from_compact():
    assert normalize_cast_uuid(TEST_CAST_UUID_COMPACT) == TEST_CAST_UUID


def test_uuid_from_service_name():
    name = f"Example-speaker-{TEST_CAST_UUID}._googlecast._tcp.local."
    assert uuid_from_service_name(name) == TEST_CAST_UUID


def test_parse_cast_service_from_properties():
    with patch("src.cast_resolve.socket.gethostbyname", return_value=TEST_HOST):
        parsed = parse_cast_service(
            "ignored._googlecast._tcp.local.",
            "example-speaker.local.",
            {b"id": TEST_CAST_UUID_COMPACT.encode("ascii")},
        )
    assert parsed is not None
    uuid, host = parsed
    assert uuid == TEST_CAST_UUID
    assert host == TEST_HOST


def test_parse_cast_service_prefers_parsed_addresses():
    parsed = parse_cast_service(
        "ignored._googlecast._tcp.local.",
        "example-speaker.local.",
        {b"id": TEST_CAST_UUID_COMPACT.encode("ascii")},
        addresses=[TEST_HOST_ALT, "2001:db8::1"],
    )
    assert parsed == (TEST_CAST_UUID, TEST_HOST_ALT)


def test_reapply_failed_hosts_updates_only_failures():
    resolver = CastResolver()
    resolver._cache = {
        TEST_CAST_UUID: TEST_HOST_UPDATED,
        TEST_CAST_UUID_OTHER: TEST_HOST_ALT,
    }
    ok = _target(
        entity_id="media_player.kitchen",
        cast_uuid=TEST_CAST_UUID_OTHER,
        host=TEST_HOST_ALT,
    )
    failed = _target(host=TEST_HOST)

    updated = resolver.reapply_failed_hosts(
        [ok, failed],
        {"media_player.example_speaker"},
        pinned_hosts={},
    )
    assert updated[0].host == TEST_HOST_ALT
    assert updated[1].host == TEST_HOST_UPDATED


def test_reapply_failed_hosts_skips_pinned():
    resolver = CastResolver()
    resolver._cache = {TEST_CAST_UUID: TEST_HOST_UPDATED}
    failed = _target(host=TEST_HOST)

    updated = resolver.reapply_failed_hosts(
        [failed],
        {"media_player.example_speaker"},
        pinned_hosts={"media_player.example_speaker": TEST_HOST},
    )
    assert updated[0].host == TEST_HOST
