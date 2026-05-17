# HiTE PRO Home Assistant Integration

Automatically discovers HiTE PRO gateways on your network and creates all their devices as MQTT entities in Home Assistant.

## How It Works

1. **mDNS Discovery**: Automatically finds HiTE PRO gateways on your local network
2. Fetches device configuration from the gateway's HTTP API
3. Parses the `defineVirtualDevice()` config
4. Publishes MQTT Auto-Discovery payloads to HA's broker
5. HA's built-in MQTT integration creates switches, lights, sensors, and binary sensors
6. State flows directly: **Gateway → MQTT Broker → Home Assistant** (no middleman)

## Prerequisites

- Home Assistant with the **MQTT** integration configured
- The MQTT broker must be the same one your HiTE PRO gateway publishes to (192.168.2.143:1883)
- The **Zeroconf** integration enabled (included by default in HA)

## Installation

### HACS (Recommended)

Add this repository as a custom repository in HACS, then install "HiTE PRO".

### Manual

1. Copy the `custom_components/hitepro/` directory to your HA config:
   ```
   /config/custom_components/hitepro/
   ```
2. Restart Home Assistant

## Configuration

### Automatic (mDNS Discovery)

If your HiTE PRO gateway is on the same network, it will appear automatically:

1. Go to **Settings → Devices & Services**
2. A **"HiTE PRO Gateway"** discovery card will appear
3. Click **Configure** → review the auto-filled URL and API key → **Submit**

The gateway advertises itself via mDNS as `_hitepro._tcp` on port 80.

### Manual

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"HiTE PRO"**
3. Enter your gateway URL and API key:
   - **Gateway URL**: `http://192.168.2.91/mqtt/` (LAN) or `https://845176aba149.connect-profi.ru/mqtt/` (remote)
   - **API Key**: The `key` parameter (default: `dj75HFueb0Gh`)
4. Click Submit — the integration validates the connection before saving

## Auto-Refresh

- Devices are refreshed every **5 minutes** by default
- Change the interval in **Settings → Devices & Services → HiTE PRO → Configure**
- Manual refresh: call the `hitepro.refresh_devices` service

## Device Mapping

| HiTE PRO Type | Home Assistant Domain | Example |
|---|---|---|
| `switch` | `mqtt.switch` | Реле (Relay) |
| `range` | `mqtt.light` | Dimmer (brightness) |
| `temperature` | `mqtt.sensor` | Smart-Air temperature |
| `rel_humidity` | `mqtt.sensor` | Smart-Air humidity |
| `alarm` | `mqtt.binary_sensor` | Door checker, motion |
| `pushbutton` | `mqtt.binary_sensor` | Leak detector |
| `text` | `mqtt.sensor` | Illumination % |
| `rgb` | `mqtt.light` | RGBW controller |

## MQTT Topics

State and commands follow Wiren Board convention:

- **State**: `/devices/hite-pro/controls/{control_id}`
- **Command**: `/devices/hite-pro/controls/{control_id}/on`
- **Discovery**: `homeassistant/{domain}/hitepro/{entity_id}/config`

## Removing the Integration

1. Go to **Settings → Devices & Services**
2. Click the three-dot menu on the HiTE PRO card → **Delete**
3. All MQTT discovery entries are removed automatically

## Files

```
custom_components/hitepro/
├── __init__.py          # Setup, refresh, service handler
├── config_flow.py       # Config, zeroconf discovery & options flow
├── const.py             # Constants
├── discovery.py         # Config parser & MQTT discovery
├── manifest.json        # Integration metadata (zeroconf, dependencies)
├── services.yaml        # Service definitions
├── strings.json         # UI strings
└── translations/
    └── en.json           # English translations
```
# hass-hitepro-integration
