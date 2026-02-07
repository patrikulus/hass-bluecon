"""Binary sensor platform for Fermax Blue (BlueCon).

Currently provides a connection-status sensor per device.  The previous
call-status sensor (driven by FCM push notifications) has been removed
because the new API client does not include FCM support.
"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_MANUFACTURER, DOMAIN, HASS_BLUECON_VERSION
from .fermax_api import FermaxClient

_LOGGER = logging.getLogger(__name__)

STATE_CONNECTED = "Connected"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary-sensor entities from a config entry."""
    client: FermaxClient = hass.data[DOMAIN][entry.entry_id]

    pairings = await client.async_get_pairings()

    sensors: list[BlueConConnectionStatusBinarySensor] = []
    for pairing in pairings:
        device_info = await client.async_get_device_info(pairing.device_id)
        sensors.append(
            BlueConConnectionStatusBinarySensor(
                client=client,
                device_id=pairing.device_id,
                device_info=device_info,
            )
        )

    async_add_entities(sensors)


class BlueConConnectionStatusBinarySensor(BinarySensorEntity):
    """Binary sensor indicating whether the device is connected."""

    _attr_should_poll = True

    def __init__(self, client: FermaxClient, device_id: str, device_info) -> None:
        self._client = client
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_connection_status".lower()
        self.entity_id = f"{DOMAIN}.{self._attr_unique_id}".lower()
        self._attr_is_on = (
            device_info is not None
            and device_info.connection_state == STATE_CONNECTED
        )
        self._model = f"{device_info.type} {device_info.subtype} {device_info.family}"

    @property
    def unique_id(self) -> str | None:
        return self.entity_id

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"{self._model} {self._device_id}",
            manufacturer=DEVICE_MANUFACTURER,
            model=self._model,
            sw_version=HASS_BLUECON_VERSION,
        )

    async def async_update(self) -> None:
        """Poll the device connection state."""
        info = await self._client.async_get_device_info(self._device_id)
        self._attr_is_on = (
            info is not None and info.connection_state == STATE_CONNECTED
        )
