"""Sensor platform for Fermax Blue (BlueCon)."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_MANUFACTURER, DOMAIN, HASS_BLUECON_VERSION
from .fermax_api import FermaxClient

_LOGGER = logging.getLogger(__name__)

SIGNAL_TERRIBLE = "terrible"
SIGNAL_BAD = "bad"
SIGNAL_WEAK = "weak"
SIGNAL_GOOD = "good"
SIGNAL_EXCELENT = "excelent"
SIGNAL_UNKNOWN = "unknown"


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    client: FermaxClient = hass.data[DOMAIN][config.entry_id]

    pairings = await client.async_get_pairings()

    sensors: list[BlueConWifiStrengthSensor] = []
    for pairing in pairings:
        device_info = await client.async_get_device_info(pairing.device_id)
        sensors.append(
            BlueConWifiStrengthSensor(
                client=client,
                device_id=pairing.device_id,
                device_info=device_info,
            )
        )

    async_add_entities(sensors)


class BlueConWifiStrengthSensor(SensorEntity):
    """Sensor reporting the device Wi-Fi signal strength category."""

    _attr_should_poll = True

    def __init__(self, client: FermaxClient, device_id: str, device_info) -> None:
        self._client = client
        self._device_id = device_id
        # NOTE: legacy unique-id was also *_connection_status – kept for compat
        self._attr_unique_id = f"{device_id}_wifi_strength".lower()
        self.entity_id = f"{DOMAIN}.{self._attr_unique_id}".lower()
        self._attr_options = [
            SIGNAL_TERRIBLE,
            SIGNAL_BAD,
            SIGNAL_WEAK,
            SIGNAL_GOOD,
            SIGNAL_EXCELENT,
            SIGNAL_UNKNOWN,
        ]
        self._attr_native_value = _wireless_signal_text(device_info.wireless_signal)
        self._model = f"{device_info.type} {device_info.subtype} {device_info.family}"
        self._attr_translation_key = "wifi-state"

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return SensorDeviceClass.ENUM

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
        """Poll the device Wi-Fi signal level."""
        info = await self._client.async_get_device_info(self._device_id)
        self._attr_native_value = _wireless_signal_text(info.wireless_signal)


def _wireless_signal_text(signal: int) -> str:
    """Map numeric wireless signal level to a human-readable category."""
    mapping = {
        0: SIGNAL_TERRIBLE,
        1: SIGNAL_BAD,
        2: SIGNAL_WEAK,
        3: SIGNAL_GOOD,
        4: SIGNAL_EXCELENT,
    }
    return mapping.get(signal, SIGNAL_UNKNOWN)
