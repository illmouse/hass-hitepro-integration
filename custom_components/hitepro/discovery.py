from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

from .const import WB_CTRL_TOPIC, WB_DEVICE

_LOGGER = logging.getLogger(__name__)

WB_TYPE_MAP = {
    "switch": "switch",
    "range": "light",
    "temperature": "sensor",
    "rel_humidity": "sensor",
    "alarm": "binary_sensor",
    "pushbutton": "event",
    "text": "sensor",
    "rgb": "light",
}

SENSOR_UNITS: dict[str, str] = {
    "temperature": "°C",
    "rel_humidity": "%",
}

BINARY_SENSOR_DEVICE_CLASS_KEYWORDS: dict[str, str] = {
    "дверь": "door",
    "door": "door",
    "окно": "window",
    "window": "window",
    "движен": "motion",
    "motion": "motion",
    "протечк": "moisture",
    "leak": "moisture",
    "water": "moisture",
}

RGB_CONTROL_RE = re.compile(r"^(?P<prefix>.+)_(?P<channel>\d+)_rgb$")
BRIGHTNESS_CONTROL_RE = re.compile(r"^(?P<prefix>.+)_(?P<channel>\d+)_brightness$")
DRIVE_CONTROL_RE = re.compile(r"^(?P<prefix>Relay-Drive_[^_]+_\d+)_(?P<action>open|close)$")


@dataclass
class HiteEntity:
    control_id: str
    domain: str
    object_id: str
    unique_id: str
    name: str
    zone: str
    wb_type: str
    readonly: bool
    state_topic: str
    command_topic: str | None
    device_id: str = ""
    device_name: str = ""
    device_model: str = ""
    config: dict[str, Any] = field(default_factory=dict)


def _extract_device(control_id: str) -> tuple[str, str, str]:
    parts = control_id.split("_")
    model = parts[0] if len(parts) >= 1 else control_id
    serial = parts[1] if len(parts) >= 2 else ""
    device_id = f"{model}_{serial}" if serial else model
    device_model = model.replace("-", " ")
    return device_id, device_model, device_id


def parse_hitepro_js(text: str) -> dict[str, Any]:
    m = re.search(r"defineVirtualDevice\('hite-pro',\s*(\{.*\})\s*\)", text, re.DOTALL)
    if not m:
        raise ValueError("Could not parse defineVirtualDevice from config")
    json_str = m.group(1)
    json_str = json_str.replace("'", '"')
    json_str = re.sub(r'(\w+)\s*:', r'"\1":', json_str)
    data: dict[str, Any] = json.loads(json_str)
    return data


def _parse_title(title: str) -> tuple[str, str]:
    if "/" in title:
        zone, name = title.split("/", 1)
        return zone.strip() or "Дом", name.strip()
    return "Дом", title.strip()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text).strip("_")


def _state_topic(control_id: str) -> str:
    return f"{WB_CTRL_TOPIC}/{control_id}"


def _command_topic(control_id: str) -> str:
    return f"{WB_CTRL_TOPIC}/{control_id}/on"


def _device_payload(control_id: str, zone: str) -> tuple[str, str, str, dict[str, Any]]:
    device_id, device_model, device_name = _extract_device(control_id)
    payload: dict[str, Any] = {
        "name": device_name,
        "identifiers": [device_id],
        "manufacturer": "HiTE PRO",
        "model": device_model,
    }
    if zone and zone != "Дом":
        payload["suggested_area"] = zone
    return device_id, device_model, device_name, payload


def _binary_sensor_device_class(control_id: str, title: str) -> str:
    control_lower = control_id.lower()
    title_lower = title.lower()

    if control_lower.startswith("smart-motion_") or control_lower.endswith("_motion"):
        return "motion"
    if control_lower.startswith("smart-water_"):
        return "moisture"
    if control_lower.startswith("checker_"):
        return "opening"
    if "power" in control_lower:
        return "problem"

    for keyword, dc in BINARY_SENSOR_DEVICE_CLASS_KEYWORDS.items():
        if keyword in title_lower:
            return dc
    return "safety"


def _is_illumination_percent(control_id: str, cell: dict[str, Any], title: str) -> bool:
    text = f"{control_id} {title}".lower()
    value = str(cell.get("value", ""))
    return "illumination" in text or "освещ" in text or value.endswith("%")


def _make_entity(
    control_id: str,
    cell: dict[str, Any],
    *,
    forced_domain: str | None = None,
    object_id: str | None = None,
    unique_id: str | None = None,
    name_suffix: str | None = None,
    payload_override: dict[str, Any] | None = None,
    command_topic_override: str | None = None,
) -> HiteEntity:
    wb_type: str = cell.get("type", "switch")
    title: str = cell.get("title", control_id).strip()
    readonly: bool = cell.get("readonly", False)
    unit: str = cell.get("unit", SENSOR_UNITS.get(wb_type, ""))
    max_val: int | None = cell.get("max")

    zone, name = _parse_title(title)
    if not name:
        name = control_id
    if name_suffix:
        name = f"{name} {name_suffix}"

    device_id, device_model, device_name, device_payload = _device_payload(control_id, zone)
    ha_domain = forced_domain or WB_TYPE_MAP.get(wb_type, "switch")

    slug = _slugify(object_id or control_id)
    entity_unique_id = _slugify(unique_id or object_id or control_id)

    state_topic = _state_topic(control_id)
    command_topic = None if readonly else _command_topic(control_id)
    if command_topic_override is not None:
        command_topic = command_topic_override

    payload: dict[str, Any] = {
        "name": name,
        "unique_id": entity_unique_id,
        "object_id": slug,
        "device": device_payload,
    }

    if ha_domain == "switch":
        payload["command_topic"] = command_topic
        payload["state_topic"] = state_topic
        payload["payload_on"] = "1"
        payload["payload_off"] = "0"
        payload["state_on"] = "1"
        payload["state_off"] = "0"
        payload["optimistic"] = False

    elif ha_domain == "button":
        payload["command_topic"] = command_topic
        payload["payload_press"] = "1"
        payload["qos"] = 0
        payload["retain"] = False

    elif ha_domain == "event":
        payload["state_topic"] = state_topic
        payload["event_types"] = ["press", "release"]
        payload["device_class"] = "button"
        payload["value_template"] = (
            "{% if value|string in ['1', 'true', 'True', 'ON', 'on'] %}"
            "press"
            "{% else %}release{% endif %}"
        )

    elif ha_domain == "light" and wb_type == "range":
        payload["command_topic"] = command_topic
        payload["state_topic"] = state_topic
        payload["state_value_template"] = "{{ 'ON' if value|int(0) > 0 else 'OFF' }}"
        payload["payload_on"] = str(max_val if max_val is not None else 100)
        payload["payload_off"] = "0"
        payload["brightness_command_topic"] = command_topic
        payload["brightness_state_topic"] = state_topic
        payload["brightness_value_template"] = "{{ value|int(0) }}"
        payload["brightness_scale"] = max_val if max_val is not None else 100
        payload["on_command_type"] = "brightness"
        payload["optimistic"] = False

    elif ha_domain == "light" and wb_type == "rgb":
        payload["command_topic"] = command_topic
        payload["state_topic"] = state_topic
        payload["rgb_command_topic"] = command_topic
        payload["rgb_state_topic"] = state_topic
        payload["rgb_command_template"] = "{{ red }};{{ green }};{{ blue }}"
        payload["rgb_value_template"] = "{{ value.replace(';', ',') }}"
        payload["optimistic"] = False

    elif ha_domain == "light":
        payload["command_topic"] = command_topic
        payload["state_topic"] = state_topic
        payload["payload_on"] = "1"
        payload["payload_off"] = "0"
        payload["state_on"] = "1"
        payload["state_off"] = "0"
        payload["optimistic"] = False

    elif ha_domain == "sensor":
        payload["state_topic"] = state_topic
        if unit:
            payload["unit_of_measurement"] = unit
        if wb_type == "temperature":
            payload["device_class"] = "temperature"
            payload["state_class"] = "measurement"
        elif wb_type == "rel_humidity":
            payload["device_class"] = "humidity"
            payload["state_class"] = "measurement"
        elif wb_type == "text" and _is_illumination_percent(control_id, cell, title):
            payload["unit_of_measurement"] = "%"
            payload["state_class"] = "measurement"
            payload["value_template"] = "{{ value | replace('%', '') | float(0) }}"
            payload["icon"] = "mdi:brightness-percent"

    elif ha_domain == "binary_sensor":
        payload["state_topic"] = state_topic
        payload["payload_on"] = "1"
        payload["payload_off"] = "0"
        payload["device_class"] = _binary_sensor_device_class(control_id, title)

    if payload_override:
        payload.update(payload_override)

    return HiteEntity(
        control_id=control_id,
        domain=ha_domain,
        object_id=slug,
        unique_id=entity_unique_id,
        name=name,
        zone=zone,
        wb_type=wb_type,
        readonly=readonly,
        state_topic=state_topic,
        command_topic=command_topic,
        device_id=device_id,
        device_name=device_name,
        device_model=device_model,
        config=payload,
    )


def _legacy_entity(control_id: str, domain: str) -> HiteEntity:
    slug = _slugify(control_id)
    return HiteEntity(
        control_id=control_id,
        domain=domain,
        object_id=slug,
        unique_id=slug,
        name=slug,
        zone="",
        wb_type="",
        readonly=True,
        state_topic=_state_topic(control_id),
        command_topic=None,
        config={},
    )


def _find_rgb_brightness_pairs(cells: dict[str, Any]) -> dict[str, tuple[str, str]]:
    pairs: dict[str, tuple[str, str]] = {}
    for control_id in cells:
        m = RGB_CONTROL_RE.match(control_id)
        if not m:
            continue
        prefix = m.group("prefix")
        channel = m.group("channel")
        brightness_id = f"{prefix}_{channel}_brightness"
        if brightness_id in cells:
            pairs[f"{prefix}_{channel}"] = (control_id, brightness_id)
    return pairs


def _find_drive_pairs(cells: dict[str, Any]) -> dict[str, dict[str, str]]:
    pairs: dict[str, dict[str, str]] = {}
    for control_id in cells:
        m = DRIVE_CONTROL_RE.match(control_id)
        if not m:
            continue
        pairs.setdefault(m.group("prefix"), {})[m.group("action")] = control_id
    return pairs


def build_entities(cells: dict[str, Any], light_devices: list[str] | None = None) -> list[HiteEntity]:
    entities: list[HiteEntity] = []
    light_set = set(light_devices or [])
    skip: set[str] = {"Reload"}

    rgb_pairs = _find_rgb_brightness_pairs(cells)
    for combined_id, (rgb_id, brightness_id) in rgb_pairs.items():
        rgb_cell = cells[rgb_id]
        brightness_cell = cells[brightness_id]
        title = brightness_cell.get("title") or rgb_cell.get("title") or combined_id
        zone, name = _parse_title(str(title).strip())
        if not name:
            name = combined_id

        device_id, device_model, device_name, device_payload = _device_payload(combined_id, zone)
        max_val: int = int(brightness_cell.get("max", 100))
        slug = _slugify(combined_id)

        payload: dict[str, Any] = {
            "name": name,
            "unique_id": slug,
            "object_id": slug,
            "device": device_payload,
            "command_topic": _command_topic(brightness_id),
            "state_topic": _state_topic(brightness_id),
            "state_value_template": "{{ 'ON' if value|int(0) > 0 else 'OFF' }}",
            "payload_on": str(max_val),
            "payload_off": "0",
            "brightness_command_topic": _command_topic(brightness_id),
            "brightness_state_topic": _state_topic(brightness_id),
            "brightness_value_template": "{{ value|int(0) }}",
            "brightness_scale": max_val,
            "rgb_command_topic": _command_topic(rgb_id),
            "rgb_state_topic": _state_topic(rgb_id),
            "rgb_command_template": "{{ red }};{{ green }};{{ blue }}",
            "rgb_value_template": "{{ value.replace(';', ',') }}",
            "on_command_type": "brightness",
            "optimistic": False,
        }

        entities.append(HiteEntity(
            control_id=combined_id,
            domain="light",
            object_id=slug,
            unique_id=slug,
            name=name,
            zone=zone,
            wb_type="rgb_range",
            readonly=False,
            state_topic=_state_topic(brightness_id),
            command_topic=_command_topic(brightness_id),
            device_id=device_id,
            device_name=device_name,
            device_model=device_model,
            config=payload,
        ))
        skip.update({rgb_id, brightness_id})

    drive_pairs = _find_drive_pairs(cells)
    for drive_id, actions in drive_pairs.items():
        for action, suffix, icon in (
            ("open", "Открыть", "mdi:arrow-up-bold"),
            ("close", "Закрыть", "mdi:arrow-down-bold"),
        ):
            control_id = actions.get(action)
            if not control_id:
                continue
            entities.append(_make_entity(
                control_id,
                cells[control_id],
                forced_domain="button",
                object_id=control_id,
                unique_id=control_id,
                name_suffix=suffix,
                payload_override={"icon": icon, "payload_press": "1"},
            ))
            skip.add(control_id)

        stop_control_id = actions.get("open") or actions.get("close")
        if stop_control_id:
            stop_id = f"{drive_id}_stop"
            entities.append(_make_entity(
                stop_control_id,
                cells[stop_control_id],
                forced_domain="button",
                object_id=stop_id,
                unique_id=stop_id,
                name_suffix="Стоп",
                payload_override={"icon": "mdi:stop", "payload_press": "0"},
            ))

    for control_id, cell in cells.items():
        if control_id in skip:
            continue

        forced_domain = "light" if control_id in light_set else None
        entities.append(_make_entity(control_id, cell, forced_domain=forced_domain))

    return entities


def build_legacy_cleanup_entities(cells: dict[str, Any], light_devices: list[str] | None = None) -> list[HiteEntity]:
    """Return retained MQTT discovery configs that should be removed after smart remapping.

    This is needed because old versions created e.g. RGB and brightness as two separate
    light entities, pushbuttons as binary_sensors, and Relay-Drive actions as switches.
    MQTT discovery configs are retained, so without explicit cleanup HA can keep stale
    entities after an integration upgrade or Home Assistant restart.
    """
    cleanup: list[HiteEntity] = []

    for _combined_id, (rgb_id, brightness_id) in _find_rgb_brightness_pairs(cells).items():
        cleanup.append(_legacy_entity(rgb_id, "light"))
        cleanup.append(_legacy_entity(brightness_id, "light"))

    for _drive_id, actions in _find_drive_pairs(cells).items():
        for control_id in actions.values():
            cleanup.append(_legacy_entity(control_id, "switch"))

    for control_id, cell in cells.items():
        if control_id == "Reload":
            continue
        if cell.get("type") == "pushbutton":
            cleanup.append(_legacy_entity(control_id, "binary_sensor"))

    return cleanup


async def _async_ensure_mqtt(hass: HomeAssistant) -> None:
    from homeassistant.components.mqtt import async_wait_for_mqtt_client
    await async_wait_for_mqtt_client(hass)


async def async_publish_discovery(
    hass: HomeAssistant,
    entities: list[HiteEntity],
    discovery_prefix: str = "homeassistant",
) -> None:
    from homeassistant.components.mqtt import async_publish

    await _async_ensure_mqtt(hass)

    for ent in entities:
        topic = f"{discovery_prefix}/{ent.domain}/{ent.object_id}/config"
        payload = json.dumps(ent.config, ensure_ascii=False)
        await async_publish(hass, topic, payload, qos=1, retain=True)
        _LOGGER.debug("Published discovery: %s/%s", ent.domain, ent.object_id)

    _LOGGER.info("Published %d discovery configs", len(entities))


async def async_remove_discovery(
    hass: HomeAssistant,
    entities: list[HiteEntity],
    discovery_prefix: str = "homeassistant",
) -> None:
    from homeassistant.components.mqtt import async_publish

    await _async_ensure_mqtt(hass)

    for ent in entities:
        topic = f"{discovery_prefix}/{ent.domain}/{ent.object_id}/config"
        await async_publish(hass, topic, "", qos=1, retain=True)
        _LOGGER.debug("Removed discovery: %s/%s", ent.domain, ent.object_id)

    _LOGGER.info("Removed %d discovery configs", len(entities))


def build_gateway_entity(gateway_url: str) -> HiteEntity:
    device_id = "HP-Gateway"
    slug = "Reload"

    payload: dict[str, Any] = {
        "name": "Reload",
        "unique_id": slug,
        "object_id": slug,
        "command_topic": f"{WB_CTRL_TOPIC}/Reload/on",
        "payload_press": "1",
        "device_class": "update",
        "entity_category": "config",
        "qos": 0,
        "retain": False,
        "device": {
            "name": "Gateway",
            "identifiers": [device_id],
            "manufacturer": "HiTE PRO",
            "model": "Gateway",
            "configuration_url": gateway_url,
        },
    }

    return HiteEntity(
        control_id="Reload",
        domain="button",
        object_id=slug,
        unique_id=slug,
        name="Reload",
        zone="",
        wb_type="pushbutton",
        readonly=False,
        state_topic=f"{WB_CTRL_TOPIC}/Reload",
        command_topic=f"{WB_CTRL_TOPIC}/Reload/on",
        device_id=device_id,
        device_name="Gateway",
        device_model="Gateway",
        config=payload,
    )


async def async_trigger_reload(hass: HomeAssistant) -> None:
    from homeassistant.components.mqtt import async_publish

    await _async_ensure_mqtt(hass)
    reload_topic = f"{WB_CTRL_TOPIC}/Reload/on"
    await async_publish(hass, reload_topic, "1", qos=0, retain=False)
    _LOGGER.info("Triggered gateway Reload to sync device states")
