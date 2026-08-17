"""Discover Google Cast devices via Home Assistant and ping them over MQTT."""

from __future__ import annotations

import logging
import signal
import sys
import time

from .cast_resolve import CastResolver
from .config import PingTarget, Settings
from .discovery import build_discovery_configs
from .ha import HomeAssistantClient
from .mqtt_out import MqttPublisher
from .payload import build_device_payload, build_summary_payload
from .pinger import Pinger, ProbeResult, ProbeStats

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def publish_discovery(
    settings: Settings,
    mqtt: MqttPublisher,
    targets: list[PingTarget],
) -> None:
    if not settings.mqtt_discovery_enabled:
        logger.info("MQTT discovery disabled")
        return
    total = 0
    for target in targets:
        configs = build_discovery_configs(settings.mqtt_topic_prefix, target)
        mqtt.publish_discovery(
            configs,
            discovery_prefix=settings.mqtt_discovery_prefix,
        )
        total += len(configs)
        logger.info(
            "Published %s discovery configs for %s (%s)",
            len(configs),
            target.friendly_name,
            target.entity_id,
        )
    logger.info("Published %s MQTT discovery configs total", total)


def refresh_targets(
    settings: Settings,
    ha: HomeAssistantClient,
    resolver: CastResolver,
) -> list[PingTarget]:
    targets = ha.discover_cast_targets(settings)
    return resolver.resolve_targets(targets)


def refresh_failed_hosts(
    settings: Settings,
    resolver: CastResolver,
    targets: list[PingTarget],
    results: list[tuple[PingTarget, ProbeResult, ProbeStats]],
) -> list[PingTarget]:
    """Re-browse mDNS and update hosts only for targets that failed probing."""
    failed_entity_ids = {
        target.entity_id for target, result, _ in results if not result.reachable
    }
    if not failed_entity_ids:
        return targets

    resolver.refresh_cache()
    return resolver.reapply_failed_hosts(
        targets,
        failed_entity_ids,
        pinned_hosts=settings.ping_host_overrides,
    )


def probe_and_publish(
    settings: Settings,
    mqtt: MqttPublisher,
    pinger: Pinger,
    targets: list[PingTarget],
) -> list[tuple[PingTarget, ProbeResult, ProbeStats]]:
    results = pinger.probe_all(targets)
    for target, result, stats in results:
        payload = build_device_payload(
            target,
            result,
            stats,
            method=settings.ping_method,
        )
        mqtt.publish(f"{target.slug}/current", payload)

    summary = build_summary_payload(results, method=settings.ping_method)
    mqtt.publish("summary", summary)
    logger.info(
        "Published ping results for %s devices (%s reachable)",
        summary["device_count"],
        summary["reachable_count"],
    )
    return results


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    stop = False

    def _handle_signal(signum: int, _frame: object) -> None:
        nonlocal stop
        logger.info("Received signal %s, shutting down", signum)
        stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info(
        "Starting pinger-mqtt (interval=%ss, discovery_refresh=%ss, method=%s, mqtt=%s:%s, discovery=%s)",
        settings.ping_interval_seconds,
        settings.ping_discovery_refresh_seconds,
        settings.ping_method,
        settings.mqtt_host,
        settings.mqtt_port,
        settings.mqtt_discovery_enabled,
    )

    ha = HomeAssistantClient(settings.ha_url, settings.ha_token)
    resolver = CastResolver()
    pinger = Pinger(settings)
    targets: list[PingTarget] = []
    last_discovery = 0.0

    mqtt = MqttPublisher(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        client_id=settings.mqtt_client_id,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        topic_prefix=settings.mqtt_topic_prefix,
    )

    try:
        while not stop:
            now = time.monotonic()
            if not targets or now - last_discovery >= settings.ping_discovery_refresh_seconds:
                try:
                    targets = refresh_targets(settings, ha, resolver)
                    last_discovery = now
                    try:
                        publish_discovery(settings, mqtt, targets)
                    except Exception:
                        logger.exception("MQTT discovery publish failed")
                except Exception:
                    logger.exception("Target discovery failed")

            if targets:
                try:
                    results = probe_and_publish(settings, mqtt, pinger, targets)
                    targets = refresh_failed_hosts(
                        settings, resolver, targets, results
                    )
                except Exception:
                    logger.exception("Probe cycle failed")
            else:
                logger.warning("No ping targets available; waiting for discovery")

            deadline = time.monotonic() + settings.ping_interval_seconds
            while not stop and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
    finally:
        mqtt.close()
        ha.close()

    logger.info("Exited")


if __name__ == "__main__":
    main()
