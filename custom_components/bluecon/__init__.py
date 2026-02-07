from .const import CONF_LOCK_STATE_RESET, CONF_PAIRINGS, DOMAIN
from .fermax_api import FermaxClient, FermaxAuthError
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

PLATFORMS: list[str] = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.CAMERA, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    if not username or not password:
        raise ConfigEntryAuthFailed("Missing Fermax credentials.")

    client = FermaxClient(hass, username, password, entry.entry_id)
    try:
        await client.async_login()
    except FermaxAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err

    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    if config_entry.version < 7:
        data = dict(config_entry.data)
        if CONF_USERNAME not in data and config_entry.unique_id:
            data[CONF_USERNAME] = config_entry.unique_id
        if CONF_PASSWORD not in data:
            data[CONF_PASSWORD] = ""
        options = dict(config_entry.options or {})
        options.setdefault(CONF_LOCK_STATE_RESET, 5)
        options.setdefault(CONF_PAIRINGS, [])
        config_entry.version = 7
        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
        )
    return True
