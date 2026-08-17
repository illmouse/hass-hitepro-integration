# Architecture

## Overview

The integration is a **discovery publisher only** — it does not create HA entities directly. Instead, it publishes MQTT Auto-Discovery payloads to the broker, and HA's built-in MQTT integration creates and manages all entities.

```
mDNS/Zeroconf → ConfigFlow → ConfigEntry
                                  │
                                  ▼
                          async_setup_entry()
                            ├── Register refresh_devices service
                            ├── First refresh
                            ├── Start periodic timer (default 5 min)
                            └── Register options listener
                                  │
                                  ▼
                       _async_refresh_entry()  ◄── timer / service call
                            │
                            ├── HTTP GET: {url}?key={api_key}
                            │     └── Returns JS with defineVirtualDevice()
                            │
                            ├── parse_hitepro_js() → cells dict
                            │
                            ├── build_entities(cells, light_devices)
                            │     ├── 1st pass: RGB+Brightness pairs → combined lights
                            │     ├── 2nd pass: Relay-Drive pairs → button entities
                            │     └── 3rd pass: remaining cells → mapped entities
                            │
                            ├── build_gateway_entity(url) → Reload button
                            │
                            ├── Diff old vs new entities
                            │     ├── Remove stale discovery configs
                            │     └── Publish new discovery configs
                            │
                            ├── Legacy cleanup (if cleanup_version < CLEANUP_VERSION)
                            │
                            └── async_trigger_reload() → MQTT "1" to Reload/on
                                  │
                                  ▼
                        MQTT Broker → Home Assistant entities
```

## Data Store

```python
hass.data[DOMAIN][entry.entry_id] = {
    "entities": list[HiteEntity],    # current entity set
    "unsub": Callable,               # timer unsubscribe callback
    "cleanup_version": int,          # last run cleanup version
}
```

Stored in `async_setup_entry`, updated on every refresh cycle.

## Refresh Cycle

1. HTTP GET to `{url}?key={api_key}` with 15s timeout, SSL verify disabled
2. Parse response with `parse_hitepro_js()` — extracts `defineVirtualDevice('hite-pro', {...})` from JS, converts to JSON
3. Build full entity set via `build_entities(cells, light_devices)`
4. Append gateway Reload button via `build_gateway_entity(url)`
5. Compute diff: entities present in old but not new → remove their MQTT discovery configs
6. If `cleanup_version < CLEANUP_VERSION`, run `build_legacy_cleanup_entities()` and remove those configs too
7. Publish all new entities via `async_publish_discovery()`
8. If entity set changed, send `async_trigger_reload()` to push gateway states
9. Store new entity list and update `cleanup_version`

## Singleton Pattern

Only one gateway instance is allowed. Enforced via:

- `async_set_unique_id("hitepro_gateway")` in config flow
- `_abort_if_unique_id_configured()` prevents second setup

## Timer Management

- `_start_refresh_timer()` uses `async_track_time_interval` with configurable `scan_interval` (default 300s, minimum 60s)
- Timer is cancelled on `async_unload_entry`
- Timer is restarted on options update via `_async_options_updated`

## Entity Diffing

Entities are compared using `(domain, object_id)` tuples. This correctly detects domain migrations (e.g., pushbutton: `binary_sensor` → `event`). When an entity's domain changes, the old domain's discovery config is removed and the new one is published.

## Gateway Reload

`async_trigger_reload()` publishes `"1"` to `/devices/hite-pro/controls/Reload/on`. This causes the gateway to push current states for all controls to MQTT, which HA then picks up. On first load (after HA restart), the Reload is **skipped** because states arrive before MQTT subscriptions are fully established. Subsequent periodic refreshes trigger Reload normally.