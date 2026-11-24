"""Mirror a source light while controlling its upstream power relay."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import probatio
from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityFeature,
    valid_supported_color_modes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_LIGHT, CONF_RELAY, DEFAULT_OPTIONS
from .sequence import PowerSequence, SequenceTimeout, SourceCommandError, Timing

_LOGGER = logging.getLogger(__name__)
_MIRRORED_ATTRIBUTES = (
    "brightness",
    "color_mode",
    "color_temp_kelvin",
    "hs_color",
    "xy_color",
    "rgb_color",
    "rgbw_color",
    "rgbww_color",
    "effect",
)
_CAPABILITY_ATTRIBUTES = (
    "min_color_temp_kelvin",
    "max_color_temp_kelvin",
    "effect_list",
)
_FEATURE_MASK = (
    LightEntityFeature.EFFECT | LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add one virtual light, without touching either physical entity."""
    async_add_entities([RelayBackedLight(entry)])


class RelayBackedLight(LightEntity):
    """A virtual light whose source needs relay power before receiving commands."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Store immutable wiring and independent timing for this light."""
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.data[CONF_NAME]
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        self._relay = entry.data[CONF_RELAY]
        self._source = entry.data[CONF_LIGHT]
        self._timing = Timing(**(DEFAULT_OPTIONS | dict(entry.options)))
        self._changed = asyncio.Event()
        self._sequence: PowerSequence | None = None

    async def async_added_to_hass(self) -> None:
        """Observe both entities; never power on as a side effect of setup."""
        await super().async_added_to_hass()
        self._sequence = PowerSequence(
            relay_is_on=self._relay_is_on,
            source_is_ready=self._source_is_ready,
            set_relay=self._async_set_relay,
            turn_on_source=self._async_turn_on_source,
            wait_for_state=self._async_wait_for_state,
            timing=self._timing,
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._relay, self._source], self._async_state_changed
            )
        )
        self._refresh_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel and drain startup before unloading or reloading this entity."""
        if self._sequence is not None:
            await self._sequence.async_close()
        await super().async_will_remove_from_hass()

    def _relay_is_on(self) -> bool:
        return self.hass.states.is_state(self._relay, STATE_ON)

    def _source_is_ready(self) -> bool:
        state = self.hass.states.get(self._source)
        return state is not None and state.state in (STATE_ON, STATE_OFF)

    @callback
    def _async_state_changed(self, event: Event) -> None:
        """Refresh the mirror and invalidate commands when relay power is lost."""
        self._changed.set()
        if event.data[ATTR_ENTITY_ID] == self._relay:
            old = event.data.get("old_state")
            new = event.data.get("new_state")
            if (
                old is not None
                and old.state == STATE_ON
                and (new is None or new.state != STATE_ON)
                and self._sequence is not None
            ):
                self._sequence.cancel_pending_turn_on()
        self._refresh_state()
        self.async_write_ha_state()

    @callback
    def _refresh_state(self) -> None:
        """Treat relay-off as off even when the bulb's state is stale/missing."""
        relay = self.hass.states.get(self._relay)
        source = self.hass.states.get(self._source)
        relay_known = relay is not None and relay.state in (STATE_ON, STATE_OFF)
        self._attr_available = relay_known and (
            relay.state == STATE_OFF or self._source_is_ready()
        )
        self._attr_is_on = self._relay_is_on() and (
            source is not None and source.state == STATE_ON
        )
        if source is None:
            return
        attributes = source.attributes
        modes = attributes.get("supported_color_modes")
        if modes:
            try:
                parsed_modes = {ColorMode(mode) for mode in modes}
                valid_supported_color_modes(parsed_modes)
            except (ValueError, TypeError, probatio.Error):
                _LOGGER.debug(
                    "Ignoring invalid color modes from %s: %s", self._source, modes
                )
            else:
                self._attr_supported_color_modes = parsed_modes
        # Retain capabilities when a powered-off source loses its attributes.
        if "supported_features" in attributes:
            self._attr_supported_features = (
                LightEntityFeature(attributes["supported_features"]) & _FEATURE_MASK
            )
        for key in _CAPABILITY_ATTRIBUTES:
            if key in attributes:
                setattr(self, f"_attr_{key}", attributes[key])
        for key in _MIRRORED_ATTRIBUTES:
            setattr(self, f"_attr_{key}", attributes.get(key))
        if self._attr_color_mode is None:
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))

    async def _async_wait_for_state(
        self, predicate: Callable[[], bool], timeout: float
    ) -> bool:
        """Wait for state events, checking before and after clearing the signal."""
        try:
            async with asyncio.timeout(timeout):
                while not predicate():
                    self._changed.clear()
                    if predicate():
                        return True
                    await self._changed.wait()
        except TimeoutError:
            return False
        return True

    async def _async_set_relay(self, turn_on: bool) -> None:
        await self.hass.services.async_call(
            self._relay.split(".", 1)[0],
            SERVICE_TURN_ON if turn_on else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._relay},
            blocking=True,
            context=self._context,
        )

    async def _async_turn_on_source(self, data: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call(
                "light",
                SERVICE_TURN_ON,
                {**data, ATTR_ENTITY_ID: self._source},
                blocking=True,
                context=self._context,
            )
        except HomeAssistantError as err:
            _LOGGER.debug("Source command to %s failed: %s", self._source, err)
            raise SourceCommandError(str(err)) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Power up if necessary and forward source-supported light arguments."""
        if self._sequence is None:
            return
        try:
            await self._sequence.async_execute(True, kwargs)
        except SequenceTimeout as err:
            raise ServiceValidationError(
                f"Timed out waiting for {err} of {self.name}. "
                "Check the physical entities and timing options."
            ) from err
        except SourceCommandError as err:
            raise HomeAssistantError(
                f"Could not send a light command to {self._source}: {err}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Immediately cut relay power; off transitions cannot be honored."""
        if self._sequence is not None:
            await self._sequence.async_execute(False)
