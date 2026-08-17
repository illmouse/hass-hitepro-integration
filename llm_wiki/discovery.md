# Discovery — Entity Mapping & MQTT Details

## WB_TYPE_MAP (Control Type → HA Domain)

| Wiren Board Type | HA Domain | Notes |
|---|---|---|
| `switch` | `switch` | On/off relay control |
| `range` | `light` | Dimmer with brightness |
| `temperature` | `sensor` | °C, `state_class: measurement` |
| `rel_humidity` | `sensor` | %, `state_class: measurement` |
| `alarm` | `binary_sensor` | Device class inferred from ID/title |
| `pushbutton` | `event` | Event types: `press`, `release` |
| `text` | `sensor` | Special case: illumination % if values match `^\d+%$` |
| `rgb` | `light` | Paired with `*_brightness` when available |

## Special Mappings

### RGB + Brightness Pairing

Controls matching `{prefix}_{channel}_rgb` and `{prefix}_{channel}_brightness` are detected by `_find_rgb_brightness_pairs()` and merged into a single combined light entity.

Combined entity gets:
- `rgb_command_topic` + `rgb_state_topic` (for color)
- `brightness_command_topic` + `brightness_state_topic` (for brightness)
- `rgb_command_template`: `{{red}};{{green}};{{blue}}` — converts HA comma format to HiTE PRO semicolon format
- `rgb_value_template`: converts semicolon-separated `R;G;B` to comma-separated `R,G,B`
- `brightness_scale`: set to the `max` value of the brightness control
- `on_command_type: brightness`
- `payload_on`: string of max value, `payload_off: "0"`

### Relay-Drive → Button Entities

`_find_drive_pairs()` detects `Relay-Drive_{id}_open` and `Relay-Drive_{id}_close` controls. Each pair produces:
- **Open button**: command_topic = `{control_id}/on`, `payload_press: "1"`
- **Close button**: command_topic = `{control_id}/on`, `payload_press: "1"`
- **Stop button** (synthetic): command_topic = `/devices/hite-pro/controls/Relay-Drive_{id}_open/on`, `payload_press: "0"` — sends `"0"` to the open channel to halt motion

### Switch-as-Light Override

Users can select specific `switch`-type controls in the options flow to be created as `mqtt.light` entities instead. These get simple on/off payload (1/0) without brightness control.

### Illumination Sensors

Text controls where `_is_illumination_percent()` returns true get:
- `icon: mdi:brightness-percent`
- `unit_of_measurement: "%"`
- `state_class: measurement`
- `value_template`: strips `%` suffix, converts to number

Detection criteria: control ID or title contains illumination keywords (`освещ`, `illum`, `light`, `ярк`) AND cell values match `^\d+%$`.

### Binary Sensor Device Classes

`_binary_sensor_device_class()` infers device class from:
- **Control ID prefixes**: `smart-motion_` → `motion`, `smart-water_` → `moisture`, `checker_` → `opening`, `power` → `problem`
- **Title keywords** (Russian + English): `дверь`/`door` → `door`, `окно`/`window` → `window`, `движен`/`motion` → `motion`, `протечк`/`leak`/`water` → `moisture`
- Default: `None` (no device class) — changed from always-`safety` in v1.2.0

## MQTT Topic Structure

All topics follow Wiren Board convention:

| Topic | Pattern |
|---|---|
| State | `/devices/hite-pro/controls/{control_id}` |
| Command | `/devices/hite-pro/controls/{control_id}/on` |
| Discovery | `homeassistant/{domain}/{object_id}/config` |

Discovery payloads are published as **retained** messages.

## Entity Dataclass

```python
@dataclass
class HiteEntity:
    control_id: str
    domain: str           # HA domain (switch, light, sensor, etc.)
    object_id: str        # Slug for MQTT discovery topic
    unique_id: str        # HA unique_id
    name: str             # Human-readable name
    zone: str             # Room/zone from title parsing
    wb_type: str          # Wiren Board type (switch, range, etc.)
    readonly: bool
    state_topic: str
    command_topic: str | None
    device_id: str = ""
    device_name: str = ""
    device_model: str = ""
    config: dict[str, Any] = field(default_factory=dict)  # Full MQTT discovery payload
```

## Device Grouping

Control IDs follow `{Model}_{Serial}_{Channel}`. `_extract_device()` splits on `_` to extract:
- `device_id`: `{Model}_{Serial}` (used as HA device identifier)
- `device_model`: Model name
- `device_name`: Zone name from title parsing

Each device gets a `device` payload with identifiers, manufacturer (`"HiTE PRO"`), model, and `suggested_area` from the zone.

## Zone/Title Parsing

`_parse_title()` splits on `" / "` (slash with spaces). Examples:
- `"Kitchen / Main Light"` → zone=`"Kitchen"`, name=`"Main Light"`
- `"Main Light"` → zone=`"Дом"`, name=`"Main Light"`

## Legacy Cleanup

`CLEANUP_VERSION` (currently `1`) gates one-time cleanup of stale retained MQTT configs. When the integration detects `cleanup_version < CLEANUP_VERSION`, it calls `build_legacy_cleanup_entities()` which returns entities for old domain mappings that need removal.

Current cleanup (v1):
- Old split RGB lights (separate `*_rgb` and `*_brightness` entities)
- Old pushbutton binary sensors (now events)
- Old Relay-Drive switches (now buttons)

When adding new domain migrations, increment `CLEANUP_VERSION` and add the old domain mappings to `build_legacy_cleanup_entities`.

## Slug Generation

`_slugify()` converts control IDs and titles to ASCII-safe slugs for `object_id`. Falls back to `"entity"` for non-Latin text that produces empty strings.