"""Lock platform for Fermax Blue (BlueCon)."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_LOCK_STATE_RESET, DEVICE_MANUFACTURER, DOMAIN, HASS_BLUECON_VERSION
from .fermax_api import AccessId, FermaxClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lock entities from a config entry."""
    client: FermaxClient = hass.data[DOMAIN][config.entry_id]
    lock_timeout: int = config.options.get(CONF_LOCK_STATE_RESET, 5)

    pairings = await client.async_get_pairings()

    locks: list[BlueConLock] = []
    for pairing in pairings:
        device_info = await client.async_get_device_info(pairing.device_id)
        for door_name, door in pairing.access_door_map.items():
            locks.append(
                BlueConLock(
                    client=client,
                    device_id=pairing.device_id,
                    door_name=door_name,
                    access_id=door.access_id,
                    device_info=device_info,
                    lock_timeout=lock_timeout,
                )
            )

    async_add_entities(locks)


class BlueConLock(LockEntity):
    """A lock entity representing a Fermax Blue door."""

    _attr_should_poll = False

    def __init__(
        self,
        client: FermaxClient,
        device_id: str,
        door_name: str,
        access_id: AccessId,
        device_info,
        lock_timeout: int,
    ) -> None:
        self._client = client
        self._device_id = device_id
        self._door_name = door_name
        self._access_id = access_id
        self._lock_timeout = lock_timeout
        self._state = STATE_LOCKED

        # Preserve existing entity-id format for backward-compat
        lock_id = f"{device_id}_{door_name}"
        self._attr_unique_id = f"{lock_id}_door_lock".lower()
        self.entity_id = f"{DOMAIN}.{self._attr_unique_id}".lower()

        self._model = f"{device_info.type} {device_info.subtype} {device_info.family}"

    # -- State properties --------------------------------------------------

    @property
    def is_locking(self) -> bool:
        return self._state == STATE_LOCKING

    @property
    def is_unlocking(self) -> bool:
        return self._state == STATE_UNLOCKING

    @property
    def is_jammed(self) -> bool:
        return self._state == STATE_JAMMED

    @property
    def is_locked(self) -> bool:
        return self._state == STATE_LOCKED

    # -- Actions -----------------------------------------------------------

    async def async_lock(self) -> None:
        """Lock is not supported (door latches automatically)."""

    async def async_unlock(self) -> None:
        """Open the door via directed-opendoor API."""
        self._state = STATE_UNLOCKING
        self.async_schedule_update_ha_state(True)

        await self._client.async_open_door(self._device_id, self._access_id)

        self._state = STATE_UNLOCKED
        self.async_schedule_update_ha_state(True)

        await asyncio.sleep(self._lock_timeout)

        self._state = STATE_LOCKED
        self.async_schedule_update_ha_state(True)

    async def async_open(self) -> None:
        """Open is an alias for unlock on this hardware."""

    # -- Device info -------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"{self._model} {self._device_id}",
            manufacturer=DEVICE_MANUFACTURER,
            model=self._model,
            sw_version=HASS_BLUECON_VERSION,
        )
