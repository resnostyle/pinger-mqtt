"""Probe Cast device reachability and track rolling statistics."""

from __future__ import annotations

import logging
import socket
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import PingTarget, Settings

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    reachable: bool
    latency_ms: float | None
    error: str | None
    probed_at: str


@dataclass
class ProbeStats:
    probes: int = 0
    successes: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float | None = None
    consecutive_failures: int = 0
    last_success_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "probes": self.probes,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "consecutive_failures": self.consecutive_failures,
            "last_success_at": self.last_success_at,
        }


@dataclass
class TargetTracker:
    target: PingTarget
    history: deque[tuple[bool, float | None]] = field(default_factory=deque)
    consecutive_failures: int = 0
    last_success_at: str | None = None

    def record(self, result: ProbeResult, window: int) -> ProbeStats:
        self.history.append((result.reachable, result.latency_ms))
        while len(self.history) > window:
            self.history.popleft()

        if result.reachable:
            self.consecutive_failures = 0
            self.last_success_at = result.probed_at
        else:
            self.consecutive_failures += 1

        probes = len(self.history)
        successes = sum(1 for ok, _ in self.history if ok)
        latencies = [lat for ok, lat in self.history if ok and lat is not None]
        return ProbeStats(
            probes=probes,
            successes=successes,
            success_rate=round(successes / probes, 3) if probes else 0.0,
            avg_latency_ms=round(sum(latencies) / len(latencies), 1)
            if latencies
            else None,
            consecutive_failures=self.consecutive_failures,
            last_success_at=self.last_success_at,
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def probe_tcp(host: str, port: int, timeout_ms: int) -> ProbeResult:
    probed_at = _utc_now_iso()
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout_ms / 1000):
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return ProbeResult(True, latency_ms, None, probed_at)
    except socket.timeout:
        return ProbeResult(False, None, "timeout", probed_at)
    except ConnectionRefusedError:
        return ProbeResult(False, None, "refused", probed_at)
    except OSError as exc:
        return ProbeResult(False, None, str(exc), probed_at)


def probe_icmp(host: str, timeout_ms: int) -> ProbeResult:
    probed_at = _utc_now_iso()
    timeout_sec = max(1, int(round(timeout_ms / 1000)))
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_sec), host],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 2,
            check=False,
        )
        if result.returncode != 0:
            return ProbeResult(False, None, "unreachable", probed_at)
        for line in result.stdout.splitlines():
            if "time=" in line:
                part = line.split("time=")[1].split()[0]
                latency_ms = round(float(part), 1)
                return ProbeResult(True, latency_ms, None, probed_at)
        return ProbeResult(True, None, None, probed_at)
    except subprocess.TimeoutExpired:
        return ProbeResult(False, None, "timeout", probed_at)
    except FileNotFoundError:
        return ProbeResult(False, None, "ping_not_available", probed_at)
    except OSError as exc:
        return ProbeResult(False, None, str(exc), probed_at)


class Pinger:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._trackers: dict[str, TargetTracker] = {}

    def sync_trackers(self, targets: list[PingTarget]) -> None:
        active = {t.entity_id for t in targets}
        for entity_id in list(self._trackers):
            if entity_id not in active:
                del self._trackers[entity_id]
        for target in targets:
            if target.entity_id not in self._trackers:
                self._trackers[target.entity_id] = TargetTracker(target=target)
            else:
                self._trackers[target.entity_id].target = target

    def probe(self, target: PingTarget) -> tuple[ProbeResult, ProbeStats]:
        if not target.host:
            result = ProbeResult(False, None, "unresolved_host", _utc_now_iso())
        elif self._settings.ping_method == "icmp":
            result = probe_icmp(target.host, self._settings.ping_timeout_ms)
        else:
            result = probe_tcp(
                target.host,
                self._settings.ping_tcp_port,
                self._settings.ping_timeout_ms,
            )

        tracker = self._trackers.setdefault(target.entity_id, TargetTracker(target=target))
        stats = tracker.record(result, self._settings.ping_stats_window)
        return result, stats

    def probe_all(self, targets: list[PingTarget]) -> list[tuple[PingTarget, ProbeResult, ProbeStats]]:
        self.sync_trackers(targets)
        results: list[tuple[PingTarget, ProbeResult, ProbeStats]] = []
        for target in targets:
            result, stats = self.probe(target)
            results.append((target, result, stats))
            if result.reachable:
                logger.debug(
                    "Probe OK %s (%s): %.1f ms",
                    target.friendly_name,
                    target.host,
                    result.latency_ms,
                )
            else:
                logger.warning(
                    "Probe FAIL %s (%s): %s",
                    target.friendly_name,
                    target.host or "unresolved",
                    result.error,
                )
        return results
