# Changelog

## Unreleased

### Fixed

- **Dimmable light state**: `state_value_template` returned `ON`/`OFF`
  while `payload_on`/`payload_off` held the numeric device values, so the
  rendered state never matched and dimmers stayed `unknown`. The template
  now emits the exact payload strings. Affects `range` controls and
  combined RGB+brightness lights.

## 1.2.0 (2026-08-17)

### Added

- **Smart RGBW light discovery**: Paired `*_rgb` and `*_brightness` controls are now combined into a single MQTT light entity with both color and brightness control. RGB format is translated between HiTE PRO (`R;G;B`) and Home Assistant (`R,G,B`) automatically.
- **Pushbutton → event entities**: Pushbutton controls are now mapped to MQTT event entities (device class: `button`) with `press`/`release` event types, replacing the previous binary sensor mapping.
- **Relay-Drive → button entities**: `Relay-Drive_*_open` and `Relay-Drive_*_close` controls are now mapped to button entities (Открыть/Закрыть) with a synthetic Stop button that sends `0` to halt motion.
- **Window/окно binary sensor device class**: Windows are now recognized alongside doors.
- **Smart Motion, Smart Water, Checker, power device classes**: Binary sensors now get correct device classes (`motion`, `moisture`, `opening`, `problem`) based on control ID prefix.
- **Illumination percentage sensors**: Text controls with values like `0%` matching illumination keywords are now mapped as numeric measurement sensors with `%` unit.
- **`state_class: measurement`** added to temperature and humidity sensors for long-term statistics.
- **Versioned legacy cleanup**: On upgrade, stale retained MQTT discovery configs for old split RGB lights, old pushbutton binary sensors, and old Relay-Drive switches are automatically removed once. Uses integer `CLEANUP_VERSION` for future-proof migration.

### Changed

- **Entity comparison** now uses `(domain, object_id)` tuples, correctly detecting domain migrations (e.g. pushbutton: binary_sensor → event).
- **Binary sensor default device class** changed from always-`safety` to `None` — only set `device_class` when a keyword match is found.
- **`_slugify`** now falls back to `"entity"` instead of returning empty strings for non-Latin titles.
- **Illumination detection** uses strict `^\d+%$` regex to avoid creating spurious sensors from non-numeric text values.

### Fixed

- **Post-startup state**: Skip gateway Reload on first load (states arrive before MQTT is ready). Periodic refreshes trigger Reload correctly, so states populate within one refresh cycle after HA restart.

## 1.1.0 (2026-05-27)

- Add light_devices option to override switch→light

## 1.0.1 (2026-05-17)

- Only trigger gateway reload when entities change

## 1.0.0 (2026-05-17)

- Initial public release