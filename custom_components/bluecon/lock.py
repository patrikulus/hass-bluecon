import asyncio
from typing import Any, Dict
from homeassistant.components.lock import LockEntity

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DEVICE_MANUFACTURER, DOMAIN, CONF_LOCK_STATE_RESET, HASS_BLUECON_VERSION
from .fermax_api import FermaxClient

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities):
    client: FermaxClient = hass.data[DOMAIN][config.entry_id]
    lock_timeout = config.options.get(CONF_LOCK_STATE_RESET, 5)

    pairings = await client.async_get_pairings()

    locks = []

    for pairing in pairings:
        device_id = pairing["deviceId"]
        # We can get device info, but pairing has most of it.
        # Let's try to get more info if needed, but pairing has 'family', 'type', 'subtype' usually?
        # The script's Pairing class doesn't seem to have family/type.
        # But get_device_info does.
        
        device_info = await client.async_get_device_info(device_id)
        
        access_door_map = pairing.get("accessDoorMap", {})
        
        for access_door_name, access_door_data in access_door_map.items():
            if not access_door_data.get("visible", True):
                continue
                
            locks.append(
                BlueConLock(
                    client,
                    device_id,
                    access_door_name,
                    access_door_data,
                    device_info,
                    lock_timeout
                )
            )
    
    async_add_entities(locks)

class BlueConLock(LockEntity):
    _attr_should_poll = False
    
    # Define states locally if not available in const
    STATE_LOCKED = "locked"
    STATE_UNLOCKED = "unlocked"
    STATE_LOCKING = "locking"
    STATE_UNLOCKING = "unlocking"

    def __init__(self, client: FermaxClient, device_id: str, access_door_name: str, access_door_data: Dict[str, Any], device_info: Dict[str, Any], lock_timeout: int):
        self.client = client
        self.lock_id = f'{device_id}_{access_door_name}'
        self.device_id = device_id
        self.access_door_name = access_door_name
        self.access_door_data = access_door_data # Contains accessId dict
        self._attr_unique_id = f'{self.lock_id}_door_lock'.lower()
        self.entity_id = f'{DOMAIN}.{self._attr_unique_id}'.lower()
        self._state = self.STATE_LOCKED
        
        model = f"{device_info.get('type', '')} {device_info.get('subtype', '')} {device_info.get('family', '')}".strip()
        self._model = model if model else "Fermax Blue Device"
        
        self._lock_timeout = lock_timeout
    
    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return self._state == self.STATE_LOCKING

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._state == self.STATE_UNLOCKING

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return False

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state == self.STATE_LOCKED

    async def async_lock(self, **kwargs) -> None:
        pass

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        self._state = self.STATE_UNLOCKING
        self.async_write_ha_state()
        
        access_id = self.access_door_data["accessId"]
        await self.client.async_open_door(self.device_id, access_id)
        
        self._state = self.STATE_UNLOCKED
        self.async_write_ha_state()
        
        await asyncio.sleep(self._lock_timeout)
        self._state = self.STATE_LOCKED
        self.async_write_ha_state()

    async def async_open(self, **kwargs) -> None:
        await self.async_unlock(**kwargs)
    
    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers = {
                (DOMAIN, self.device_id)
            },
            name = f'{self._model} {self.device_id}',
            manufacturer = DEVICE_MANUFACTURER,
            model = self._model,
            sw_version = HASS_BLUECON_VERSION
        )
