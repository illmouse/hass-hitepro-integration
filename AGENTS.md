# AGENTS.md

## Project

HiTE PRO integration for Home Assistant. Discovers HiTE PRO gateways via mDNS, fetches their device config over HTTP, and publishes MQTT Auto-Discovery payloads so HA creates entities without any middleman.

- **Language**: Python 3 (Home Assistant custom integration)
- **Domain**: `hitepro`
- **HA dependency**: MQTT integration
- **Entity creation**: purely via MQTT discovery — `PLATFORMS = []`, no `async_forward_entry_setups`
- **Current version**: 1.2.0

## Key Files

| File | Role |
|---|---|
| `custom_components/hitepro/__init__.py` | Entry point, refresh timer, service handler |
| `custom_components/hitepro/discovery.py` | Config parser, entity builder, MQTT discovery publisher |
| `custom_components/hitepro/config_flow.py` | Config flow (manual + mDNS) and options flow |
| `custom_components/hitepro/const.py` | All constants |
| `custom_components/hitepro/manifest.json` | Integration metadata |

## Rules

1. All entity creation is MQTT discovery only — never add HA platforms or `async_forward_entry_setups`
2. Device grouping: control IDs follow `{Model}_{Serial}_{Channel}` — extract model+serial for HA device registry
3. Zone/area from title: `"Zone / Name"` → `(zone, name)`, default zone `"Дом"`
4. When entity domains change across versions, increment `CLEANUP_VERSION` in `discovery.py` and add cleanup logic in `build_legacy_cleanup_entities`
5. SSL verification is intentionally disabled — HiTE PRO gateways may use self-signed certs
6. Only one gateway instance allowed (`unique_id = "hitepro_gateway"`)
7. Keep `CHANGELOG.md` and `manifest.json` version in sync
8. Keep `README.md` strictly in English

## Detailed Docs

Fetch these when you need specifics:

- **`llm_wiki/architecture.md`** — data flow, refresh cycle, data store structure, singleton pattern
- **`llm_wiki/discovery.md`** — entity mapping, MQTT payload details, RGB pairing, drive buttons, legacy cleanup
- **`llm_wiki/config-flow.md`** — setup steps, validation, options flow, light devices selector