# pinger-mqtt

Discover Google Cast / Google Home devices from Home Assistant, probe LAN
connectivity, and publish retained JSON metrics to Mosquitto. Optional Home
Assistant MQTT discovery creates latency and reachability sensors per device.

## How it works

1. **Discovery** — reads HA entity/device registry over WebSocket, filters to
   Cast `media_player` entities (default: manufacturer `Google Inc.`, excludes
   Cast groups).
2. **IP resolution** — browses `_googlecast._tcp.local.` via mDNS and matches
   Cast UUIDs from HA to LAN IPs.
3. **Probing** — TCP connect to port 8008 (default) or optional ICMP ping.
4. **MQTT** — publishes per-device metrics plus a summary topic.

## Topics

| Topic | Contents |
|-------|----------|
| `home/ping/<slug>/current` | Latest probe + rolling stats for one device |
| `home/ping/summary` | Snapshot of all devices |

All messages are retained JSON.

Example `home/ping/example_speaker/current`:

```json
{
  "entity_id": "media_player.example_speaker",
  "friendly_name": "Example speaker",
  "host": "192.0.2.10",
  "reachable": true,
  "latency_ms": 12.4,
  "method": "tcp8008",
  "stats": {
    "probes": 60,
    "success_rate": 0.983,
    "avg_latency_ms": 14.1,
    "consecutive_failures": 0
  },
  "probed_at": "2026-08-17T22:30:00+00:00",
  "published": "2026-08-17T22:30:00+00:00"
}
```

## MQTT discovery (Home Assistant)

On startup (and after each discovery refresh), the service publishes retained
configs for each device:

- `sensor.pinger_mqtt_<slug>_latency` (ms)
- `binary_sensor.pinger_mqtt_<slug>_reachable`

Set `MQTT_DISCOVERY_ENABLED=false` to skip discovery and only publish data topics.

## Quick start

```bash
cp .env.example .env
# Edit HA_URL, HA_TOKEN, MQTT_*

# With mise (recommended)
mise trust
mise run setup
mise run run

# Or manually
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

Create a long-lived access token in Home Assistant (Profile → Security).

## Docker

Use `network_mode: host` so mDNS and LAN probes work:

```yaml
pinger-mqtt:
  image: ghcr.io/resnostyle/pinger-mqtt:latest
  container_name: pinger-mqtt
  restart: unless-stopped
  network_mode: host
  env_file: .env
```

For `PING_METHOD=icmp`, also add `cap_add: [NET_RAW]`.

CI on `main` runs tests, then builds and pushes `linux/amd64` + `linux/arm64` images to GHCR (`ghcr.io/resnostyle/pinger-mqtt`).

## Environment

See [`.env.example`](.env.example). Required: `HA_URL`, `HA_TOKEN`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `PING_INTERVAL_SECONDS` | `60` | Probe cadence |
| `PING_DISCOVERY_REFRESH_SECONDS` | `300` | Re-scan HA + mDNS |
| `PING_METHOD` | `tcp8008` | `tcp8008` or `icmp` |
| `PING_TIMEOUT_MS` | `2000` | Probe timeout |
| `PING_TCP_PORT` | `8008` | Cast HTTP port |
| `PING_STATS_WINDOW` | `60` | Rolling window size |
| `PING_MANUFACTURER_FILTER` | `Google Inc.` | Comma-separated allowlist |
| `PING_EXCLUDE_MODELS` | `Google Cast Group` | Skip virtual groups |
| `PING_HOST_OVERRIDES` | *(empty)* | Manual `entity_id:host` map (e.g. `media_player.example_speaker:192.0.2.10`) |

## Tracking connection quality over time

Use HA history graphs on the latency sensors, or build automations on
`consecutive_failures` from the JSON payload (also exposed as attributes via
discovery). Lower `PING_INTERVAL_SECONDS` (e.g. `30`) for finer-grained data.
