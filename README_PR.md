# HiTE PRO smart MQTT discovery patch

This patch improves MQTT discovery generation without requiring any server-side changes.

## Changes

- Combine paired `*_rgb` + `*_brightness` controls into a single MQTT light.
- Convert HiTE RGB command/state format from `R;G;B` to Home Assistant MQTT RGB format.
- Map pushbutton controls to MQTT event entities instead of binary sensors.
- Map Relay-Drive open/close controls to MQTT button entities and add a synthetic stop button.
- Improve binary sensor device classes for Smart Motion, Smart Water, Checker and power/problem controls.
- Parse illumination text values like `0%` as numeric measurement sensors.
- Remove stale retained discovery configs once after upgrade for old split RGB, old pushbutton binary sensors and old Relay-Drive switches.
- Compare entities by `(domain, object_id)` so domain migrations are handled correctly.

## Local validation

Validated with the archived `hite-pro.js` fixture:

- `python3 -m py_compile discovery.py __init__.py`
- Parsed 22 HiTE cells.
- Built 20 HA entities: 10 events, 7 switches, 1 light, 1 binary sensor, 1 sensor.
- Verified JSON serialization of all generated discovery payloads.
- Verified combined RGBW light replaces separate RGB and brightness entities.
- Verified legacy cleanup entries for old retained MQTT discovery configs.

## Scope

No server code changes are required. The patch only changes the Home Assistant custom integration.
