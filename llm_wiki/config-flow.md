# Config Flow — Setup & Options

## Config Flow (`HiteProConfigFlow`)

- **VERSION**: 1, **MINOR_VERSION**: 2
- **Domain**: `hitepro`

### Steps

| Step | Method | Trigger | Description |
|---|---|---|---|
| `user` | `async_step_user` | Manual setup | Form with URL + API key |
| `zeroconf` | `async_step_zeroconf` | mDNS discovery | Auto-detected from `_hitepro._tcp.local.` service |
| `zeroconf_confirm` | `async_step_zeroconf_confirm` | After mDNS | Confirmation form with discovered URL + API key |

### Validation

Both manual and mDNS flows validate by:
1. HTTP GET to `{url}?key={api_key}` (15s timeout, SSL verify disabled)
2. Checking response contains `defineVirtualDevice`
3. Returns error codes: `cannot_connect` (network error) or `invalid_config` (missing `defineVirtualDevice`)

### Singleton Enforcement

`async_set_unique_id("hitepro_gateway")` + `_abort_if_unique_id_configured()` prevents configuring a second gateway.

### Config Entry Data

```python
entry.data = {
    "url": "http://192.168.x.x/mqtt/",  # Gateway URL
    "api_key": "xxxxx",                   # API key for authentication
}
entry.options = {
    "scan_interval": 300,                 # Refresh interval in seconds
    "light_devices": ["Relay-4S_9F4CAE93_1", ...],  # Switch IDs promoted to lights
}
```

## Options Flow (`HiteProOptionsFlow`)

Accessed via **Settings → Devices & Services → HiTE PRO → Configure**.

### Fields

| Field | Key | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| URL | `url` | string | Yes | — | Gateway URL |
| API Key | `api_key` | string | Yes | — | Gateway API key |
| Scan Interval | `scan_interval` | int | No | 300 | Min 60 seconds |
| Light Devices | `light_devices` | multi-select | No | [] | Dynamic dropdown of switch-type controls |

### Light Devices Selector

The `_async_get_switch_options()` method:
1. Fetches gateway config using current URL + API key
2. Parses response with `parse_hitepro_js()`
3. Filters for cells where `type == "switch"`
4. Excludes `"Reload"` control
5. Returns `[{value: control_id, label: "control_id (Title)"}]`

Uses `SelectSelector` with `custom_value=True` so users can type arbitrary IDs not in the dropdown.

### Options Update Flow

When options are saved:
1. `_async_options_updated` callback fires
2. Cancels old timer
3. Starts new timer with updated `scan_interval`
4. Triggers immediate refresh with new settings

## mDNS Discovery Details

The integration registers two Zeroconf service types in `manifest.json`:
- `_hitepro._tcp.local.` with `model: hitepro-gateway` property
- `_http._tcp.local.` with `name: hitepro*`

When a matching service is found:
1. `async_step_zeroconf` extracts host, port, and properties
2. Constructs URL: `http://{host}:{port}/mqtt/`
3. Pre-fills the form and redirects to `zeroconf_confirm`

## Error Handling

| Error | Condition | User Message |
|---|---|---|
| `cannot_connect` | Network/timeout error | "Cannot connect to gateway" |
| `invalid_config` | Response missing `defineVirtualDevice` | "Invalid gateway configuration" |