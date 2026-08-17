# HiTE PRO Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![Project Maintenance][maintenance-shield]][user_profile]

> **Note:** The maintainer does not have access to all varieties of HiTE PRO devices. Only some device types have been tested and confirmed working. If your device is not supported, please share your gateway configuration and report bugs via [Issues](https://github.com/illmouse/hass-hitepro-integration/issues) — I will review them and test when time permits. Pull requests are also welcome and will be reviewed.

Automatically discovers HiTE PRO gateways on your network and creates all their devices as MQTT entities in Home Assistant.

## How It Works

1. **mDNS Discovery**: Automatically finds HiTE PRO gateways on your local network
2. Fetches device configuration from the gateway's HTTP API
3. Parses the `defineVirtualDevice()` config
4. Publishes MQTT Auto-Discovery payloads to HA's broker
5. HA's built-in MQTT integration creates switches, lights, sensors, and binary sensors
6. State flows directly: **Gateway → MQTT Broker → Home Assistant** (no middleman)

## Prerequisites

- Home Assistant **2024.1** or newer
- The **MQTT** integration configured — the broker must be shared with your HiTE PRO gateway
- The **Zeroconf** integration enabled (included by default in HA)

## Installation

### HACS (Custom Repository)

1. Install [HACS][hacs-download] if you don't have it yet
2. In HACS, go to **Integrations → ⋮ → Custom Repositories**
3. Add `https://github.com/illmouse/hass-hitepro-integration` as an **Integration** repository
4. Search for `HiTE PRO` in HACS and click **Download**
5. Restart Home Assistant

### Manual

1. Download or clone this repository
2. Copy the `custom_components/hitepro/` directory to your HA config:
   ```
   /config/custom_components/hitepro/
   ```
3. Restart Home Assistant

## Configuration

### Automatic (mDNS Discovery)

If your HiTE PRO gateway is on the same network, it will appear automatically:

1. Go to **Settings → Devices & Services**
2. A **"HiTE PRO Gateway"** discovery card will appear
3. Click **Configure** → review the auto-filled URL and API key → **Submit**

The gateway advertises itself via mDNS as `_hitepro._tcp` on port 80.

### Manual

[![Add Integration][add-integration-badge]][add-integration]

1. Click the button above, or go to **Settings → Devices & Services → Add Integration**
2. Search for **"HiTE PRO"**
3. Enter your gateway URL and API key:
   - **Gateway URL**: `http://192.168.x.x/mqtt/` (LAN) or your remote URL
   - **API Key**: The `key` parameter from your gateway
4. Click **Submit** — the integration validates the connection before saving

## Switches vs Lights

By default, all relay channels are created as **switches** in Home Assistant. You can configure specific channels to appear as **lights** instead:

1. Go to **Settings → Devices & Services → HiTE PRO → Configure**
2. The **Light devices** dropdown lists all switch-type channels fetched from your gateway
3. Select the channels that control lights (e.g. `Relay-4S_9F4CAE93_1`)
4. Click **Submit** — the integration will recreate those entities as MQTT lights

Lights created this way support on/off commands. For brightness and color control, use `range` (dimmer) and `rgb` (RGBW) controls which are automatically discovered as lights. To revert a light back to a switch, simply deselect it from the list.

## Auto-Refresh

- Devices are refreshed every **5 minutes** by default (minimum 60 seconds)
- Change the interval in **Settings → Devices & Services → HiTE PRO → Configure**
- Manual refresh: call the `hitepro.refresh_devices` service

## Device Mapping

| HiTE PRO Type | Home Assistant Domain | Example |
|---|---|---|
| `switch` | `mqtt.switch` | Реле (Relay) |
| `range` | `mqtt.light` | Dimmer (brightness) |
| `temperature` | `mqtt.sensor` | Smart-Air temperature |
| `rel_humidity` | `mqtt.sensor` | Smart-Air humidity |
| `alarm` | `mqtt.binary_sensor` | Door, window, motion, leak |
| `pushbutton` | `mqtt.event` | Button press/release events |
| `text` | `mqtt.sensor` | Illumination % |
| `rgb` | `mqtt.light` | RGBW controller (paired with `*_brightness`) |
| `Relay-Drive` | `mqtt.button` | Открыть / Закрыть / Стоп |

## MQTT Topics

State and commands follow Wiren Board convention:

- **State**: `/devices/hite-pro/controls/{control_id}`
- **Command**: `/devices/hite-pro/controls/{control_id}/on`
- **Discovery**: `homeassistant/{domain}/{entity_id}/config`

## Known Limitations

### States show "Unknown" after Home Assistant restart

After an HA restart, all HiTE PRO entities may display **"Unknown"** state until the next scheduled refresh cycle (default: 5 minutes). This happens because:

1. HA creates MQTT entities from retained discovery configs before this integration starts
2. The HiTE PRO gateway does not retain state messages on the MQTT broker
3. The integration skips the initial Reload to avoid publishing states before MQTT subscriptions are ready

States populate automatically once the first periodic refresh runs. You can also manually trigger **Settings → Devices & Services → HiTE PRO → ⋮ → Reload** or call the `hitepro.refresh_devices` service to restore states immediately.

## Troubleshooting

Enable debug logging:

[![Logging service][ha-service-badge]][ha-service]

On the entry page, paste:

```yaml
service: logger.set_level
data:
  custom_components.hitepro: debug
```

Then check the logs:

[![Home Assistant Logs][ha-logs-badge]][ha-logs]

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
├── brand/
│   └── icon.png         # Integration icon
├── manifest.json        # Integration metadata (zeroconf, dependencies)
├── services.yaml        # Service definitions
├── strings.json         # UI strings
└── translations/
    ├── en.json           # English translations
    └── ru.json           # Russian translations
```

[add-integration]: https://my.home-assistant.io/redirect/config_flow_start/?domain=hitepro
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[hacs-download]: https://hacs.xyz/docs/setup/download
[ha-logs]: https://my.home-assistant.io/redirect/logs
[ha-logs-badge]: https://my.home-assistant.io/badges/logs.svg
[ha-service]: https://my.home-assistant.io/redirect/developer_call_service/?service=logger.set_level
[ha-service-badge]: https://my.home-assistant.io/badges/developer_call_service.svg
[maintenance-shield]: https://img.shields.io/badge/maintained-yes-green.svg?style=flat
[releases-shield]: https://img.shields.io/github/release/illmouse/hass-hitepro-integration.svg?style=flat
[releases]: https://github.com/illmouse/hass-hitepro-integration/releases
[user_profile]: https://github.com/illmouse