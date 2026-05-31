from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
import ssl
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_API_KEY, CONF_LIGHT_DEVICES, CONF_URL, DEFAULT_SCAN_INTERVAL, DOMAIN, SERVICE_REFRESH
from .discovery import (
    HiteEntity,
    async_publish_discovery,
    async_remove_discovery,
    async_trigger_reload,
    build_entities,
    build_gateway_entity,
    build_legacy_cleanup_entities,
    parse_hitepro_js,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"entities": [], "unsub": None, "legacy_cleanup_done": False}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_refresh(call: ServiceCall) -> None:
        for entry_item in hass.config_entries.async_entries(DOMAIN):
            await _async_refresh_entry(hass, entry_item)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh)

    await _async_refresh_entry(hass, entry)
    _start_refresh_timer(hass, entry)

    entry.async_on_unload(
        hass.data[DOMAIN][entry.entry_id].get("unsub", lambda: None)
    )

    entry.async_on_unload(
        entry.add_update_listener(_async_options_updated)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    unsub = data.get("unsub")
    if unsub:
        unsub()

    entities: list[HiteEntity] = data.get("entities", [])
    await async_remove_discovery(hass, entities)

    hass.data[DOMAIN].pop(entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    _start_refresh_timer(hass, entry)


def _start_refresh_timer(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    unsub = data.get("unsub")
    if unsub:
        unsub()

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    unsub = async_track_time_interval(
        hass,
        lambda _: _async_refresh_entry(hass, entry),
        timedelta(seconds=scan_interval),
    )
    hass.data[DOMAIN][entry.entry_id]["unsub"] = unsub


async def _async_refresh_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    url: str = entry.data.get(CONF_URL, "")
    api_key: str = entry.data.get(CONF_API_KEY, "")
    full_url = f"{url}?key={api_key}" if api_key else url

    try:
        config_text = await _async_fetch_config(full_url)
    except Exception as err:
        _LOGGER.error("Failed to fetch HiTE PRO config: %s", err)
        return

    try:
        data = parse_hitepro_js(config_text)
    except Exception as err:
        _LOGGER.error("Failed to parse HiTE PRO config: %s", err)
        return

    cells = data.get("cells", {})
    url: str = entry.data.get(CONF_URL, "")
    light_devices: list[str] = entry.options.get(CONF_LIGHT_DEVICES, [])
    new_entities = build_entities(cells, light_devices=light_devices)
    gateway_entity = build_gateway_entity(url)
    new_entities.append(gateway_entity)

    data_store = hass.data[DOMAIN].get(entry.entry_id, {})
    old_entities: list[HiteEntity] = data_store.get("entities", [])
    old_ids = {(e.domain, e.object_id) for e in old_entities}
    new_ids = {(e.domain, e.object_id) for e in new_entities}

    removed = [e for e in old_entities if (e.domain, e.object_id) not in new_ids]
    cleanup_entities: list[HiteEntity] = []
    if not data_store.get("legacy_cleanup_done"):
        cleanup_entities = build_legacy_cleanup_entities(cells, light_devices=light_devices)
        cleanup_entities = [e for e in cleanup_entities if (e.domain, e.object_id) not in new_ids]

    if removed:
        await async_remove_discovery(hass, removed)

    if cleanup_entities:
        await async_remove_discovery(hass, cleanup_entities)

    await async_publish_discovery(hass, new_entities)

    if new_ids != old_ids:
        await async_trigger_reload(hass)

    hass.data[DOMAIN][entry.entry_id]["entities"] = new_entities
    if cleanup_entities:
        hass.data[DOMAIN][entry.entry_id]["legacy_cleanup_done"] = True
    _LOGGER.info(
        "HiTE PRO refreshed: %d entities (%d added, %d removed, %d legacy cleaned)",
        len(new_entities),
        len(new_ids - old_ids),
        len(removed),
        len(cleanup_entities),
    )


async def _async_fetch_config(url: str) -> str:
    if url.startswith("https://"):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    else:
        connector = aiohttp.TCPConnector()
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()
