from __future__ import annotations

import logging
from typing import Any

import aiohttp
import ssl
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectOptionDict
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_API_KEY, CONF_LIGHT_DEVICES, CONF_SCAN_INTERVAL, CONF_URL, DEFAULT_API_KEY, DEFAULT_SCAN_INTERVAL, DEFAULT_URL, DOMAIN
from .discovery import parse_hitepro_js

_LOGGER = logging.getLogger(__name__)

ZEROCONF_TYPE = "_hitepro._tcp.local."


class HiteProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            api_key = user_input[CONF_API_KEY]
            full_url = f"{url}?key={api_key}" if api_key else url

            try:
                text = await self._async_fetch(full_url)
                if text is None:
                    errors["base"] = "cannot_connect"
                elif "defineVirtualDevice" not in text:
                    errors["base"] = "invalid_config"
            except (aiohttp.ClientError, TimeoutError, ssl.SSLError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id("hitepro_gateway")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="HiTE PRO Gateway",
                    data=user_input,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL, CONF_LIGHT_DEVICES: []},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=DEFAULT_URL): str,
                vol.Required(CONF_API_KEY, default=DEFAULT_API_KEY): str,
            }),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        host = discovery_info.host
        port = discovery_info.port or 80
        properties = discovery_info.properties or {}
        path = properties.get("path", "/mqtt/").rstrip("/") if isinstance(properties, dict) else "/mqtt"
        url = f"http://{host}:{port}{path}"

        _LOGGER.info("Discovered HiTE PRO gateway at %s", url)

        await self.async_set_unique_id("hitepro_gateway")
        self._abort_if_unique_id_configured()

        self.context.update({"title_placeholders": {"name": "HiTE PRO Gateway"}})

        return await self.async_step_zeroconf_confirm(
            user_input={CONF_URL: url, CONF_API_KEY: DEFAULT_API_KEY}
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            api_key = user_input.get(CONF_API_KEY, DEFAULT_API_KEY)
            full_url = f"{url}?key={api_key}" if api_key else url

            try:
                text = await self._async_fetch(full_url)
                if text is None:
                    errors["base"] = "cannot_connect"
                elif "defineVirtualDevice" not in text:
                    errors["base"] = "invalid_config"
            except (aiohttp.ClientError, TimeoutError, ssl.SSLError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id("hitepro_gateway")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="HiTE PRO Gateway",
                    data={CONF_URL: url, CONF_API_KEY: api_key},
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL, CONF_LIGHT_DEVICES: []},
                )

        url = user_input.get(CONF_URL, DEFAULT_URL) if user_input else DEFAULT_URL
        api_key = user_input.get(CONF_API_KEY, DEFAULT_API_KEY) if user_input else DEFAULT_API_KEY

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"url": url},
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=url): str,
                vol.Required(CONF_API_KEY, default=api_key): str,
            }),
            errors=errors,
        )

    async def _async_fetch(self, url: str) -> str | None:
        try:
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
                    if resp.status != 200:
                        return None
                    return await resp.text()
        except (aiohttp.ClientError, TimeoutError, ssl.SSLError):
            return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HiteProOptionsFlow()


class HiteProOptionsFlow(config_entries.OptionsFlow):
    def __init__(self):
        self._switch_options: list[SelectOptionDict] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            api_key = user_input[CONF_API_KEY]
            full_url = f"{url}?key={api_key}" if api_key else url

            try:
                text = await self._async_fetch(full_url)
                if text is None:
                    errors["base"] = "cannot_connect"
                elif "defineVirtualDevice" not in text:
                    errors["base"] = "invalid_config"
            except (aiohttp.ClientError, TimeoutError, ssl.SSLError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                new_data = {**self.config_entry.data, CONF_URL: url, CONF_API_KEY: api_key}
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

                light_devices = user_input.get(CONF_LIGHT_DEVICES, []) or []
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        CONF_LIGHT_DEVICES: light_devices,
                    },
                )

        current_data = self.config_entry.data
        current_options = self.config_entry.options
        current_lights: list[str] = current_options.get(CONF_LIGHT_DEVICES, [])

        if not self._switch_options and not errors:
            self._switch_options = await self._async_get_switch_options()
            if not self._switch_options:
                self._switch_options = [
                    {"value": cid, "label": f"{cid}"}
                    for cid in current_lights
                ]

        schema = vol.Schema({
            vol.Required(
                CONF_URL,
                default=user_input.get(CONF_URL, current_data.get(CONF_URL, DEFAULT_URL)) if user_input else current_data.get(CONF_URL, DEFAULT_URL),
            ): str,
            vol.Required(
                CONF_API_KEY,
                default=user_input.get(CONF_API_KEY, current_data.get(CONF_API_KEY, DEFAULT_API_KEY)) if user_input else current_data.get(CONF_API_KEY, DEFAULT_API_KEY),
            ): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=user_input.get(CONF_SCAN_INTERVAL, current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)) if user_input else current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=60)),
            vol.Optional(
                CONF_LIGHT_DEVICES,
                default=current_lights,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=self._switch_options,
                    multiple=True,
                    custom_value=True,
                )
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def _async_get_switch_options(self) -> list[SelectOptionDict]:
        url: str = self.config_entry.data.get(CONF_URL, "")
        api_key: str = self.config_entry.data.get(CONF_API_KEY, "")
        full_url = f"{url}?key={api_key}" if api_key else url

        try:
            text = await self._async_fetch(full_url)
            if text is None:
                return []
            data = parse_hitepro_js(text)
        except Exception:
            _LOGGER.warning("Could not fetch device list for options flow")
            return []

        cells = data.get("cells", {})
        options: list[SelectOptionDict] = []
        for control_id, cell in cells.items():
            if control_id == "Reload":
                continue
            if cell.get("type") != "switch":
                continue
            title = cell.get("title", control_id).strip()
            label = f"{control_id} ({title})" if title else control_id
            options.append({"value": control_id, "label": label})

        return options

    async def _async_fetch(self, url: str) -> str | None:
        try:
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
                    if resp.status != 200:
                        return None
                    return await resp.text()
        except (aiohttp.ClientError, TimeoutError, ssl.SSLError):
            return None