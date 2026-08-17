"""Tests for config helpers."""

from src.config import slugify


def test_slugify():
    assert slugify("Living Speaker") == "living_speaker"
    assert slugify("media-player-2") == "media_player_2"
