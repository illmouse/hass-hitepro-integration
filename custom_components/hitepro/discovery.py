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
    "pushbutton": "binary_sensor",
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
    "движен": "motion",
    "motion": "motion",
    "протечк": "moisture",
    "leak": "moisture",
    "water": "moisture",
}


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
    config: dict[str, Any] = field(default_factory=dict)


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


def build_entities(cells: dict[str, Any]) -> list[HiteEntity]:
    entities: list[HiteEntity] = []

    for control_id, cell in cells.items():
        if control_id == "Reload":
            continue

        wb_type: str = cell.get("type", "switch")
        title: str = cell.get("title", control_id).strip()
        readonly: bool = cell.get("readonly", False)
        unit: str = cell.get("unit", SENSOR_UNITS.get(wb_type, ""))
        max_val: int | None = cell.get("max")

        zone, name = _parse_title(title)
        if not name:
            name = control_id

        zone_slug = _slugify(zone)
        device_id = f"hitepro_{zone_slug}" if zone_slug else "hitepro"
        ha_domain = WB_TYPE_MAP.get(wb_type, "switch")
        slug = _slugify(control_id)
        object_id = f"hitepro_{slug}"
        unique_id = f"hitepro_{slug}"

        state_topic = f"{WB_CTRL_TOPIC}/{control_id}"
        command_topic = None if readonly else f"{WB_CTRL_TOPIC}/{control_id}/on"

        payload: dict[str, Any] = {
            "name": name,
            "unique_id": unique_id,
            "object_id": object_id,
            "device": {
                "name": zone,
                "identifiers": [device_id],
                "manufacturer": "HiTE PRO",
                "model": "HiTE PRO Gateway",
            },
        }

        if ha_domain == "switch":
            payload["command_topic"] = command_topic
            payload["state_topic"] = state_topic
            payload["payload_on"] = "1"
            payload["payload_off"] = "0"
            payload["state_on"] = "1"
            payload["state_off"] = "0"
            payload["optimistic"] = False

        elif ha_domain == "light" and wb_type == "range":
            payload["command_topic"] = command_topic
            payload["state_topic"] = state_topic
            payload["brightness_command_topic"] = command_topic
            payload["brightness_state_topic"] = state_topic
            payload["brightness_scale"] = max_val if max_val is not None else 100
            payload["on_command_type"] = "brightness"

        elif ha_domain == "light" and wb_type == "rgb":
            payload["command_topic"] = command_topic
            payload["state_topic"] = state_topic
            payload["rgb_command_topic"] = command_topic
            payload["rgb_state_topic"] = state_topic

        elif ha_domain == "sensor":
            payload["state_topic"] = state_topic
            if unit:
                payload["unit_of_measurement"] = unit
            if wb_type == "temperature":
                payload["device_class"] = "temperature"
            elif wb_type == "rel_humidity":
                payload["device_class"] = "humidity"

        elif ha_domain == "binary_sensor":
            payload["state_topic"] = state_topic
            payload["payload_on"] = "1"
            payload["payload_off"] = "0"
            title_lower = title.lower()
            for keyword, dc in BINARY_SENSOR_DEVICE_CLASS_KEYWORDS.items():
                if keyword in title_lower:
                    payload["device_class"] = dc
                    break
            else:
                payload["device_class"] = "safety"

        entities.append(HiteEntity(
            control_id=control_id,
            domain=ha_domain,
            object_id=object_id,
            unique_id=unique_id,
            name=name,
            zone=zone,
            wb_type=wb_type,
            readonly=readonly,
            state_topic=state_topic,
            command_topic=command_topic,
            config=payload,
        ))

    return entities


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