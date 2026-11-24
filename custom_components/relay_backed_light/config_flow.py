"""UI configuration for a relay-backed light."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_BOOT_DELAY,
    CONF_LIGHT,
    CONF_LIGHT_TIMEOUT,
    CONF_RELAY,
    CONF_RELAY_TIMEOUT,
    CONF_RETRY_COUNT,
    CONF_RETRY_INTERVAL,
    DEFAULT_OPTIONS,
    DOMAIN,
)


def timing_schema(options: dict[str, Any]) -> vol.Schema:
    """Build bounded timing selectors shared by the options UI."""
    limits = {
        CONF_BOOT_DELAY: (0, 120, 0.5),
        CONF_RELAY_TIMEOUT: (1, 120, 1),
        CONF_LIGHT_TIMEOUT: (1, 300, 1),
        CONF_RETRY_COUNT: (1, 10, 1),
        CONF_RETRY_INTERVAL: (0, 30, 0.5),
    }
    return vol.Schema(
        {
            vol.Required(key, default=options.get(key, default)): NumberSelector(
                NumberSelectorConfig(
                    min=limits[key][0],
                    max=limits[key][1],
                    step=limits[key][2],
                    mode=NumberSelectorMode.BOX,
                )
            )
            for key, default in DEFAULT_OPTIONS.items()
        }
    )


class RelayBackedLightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one independent virtual light per config entry."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Offer timing options; HA automatically reloads changed entries."""
        return RelayBackedLightOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a physical relay and its downstream light."""
        registry = er.async_get(self.hass)
        excluded = [
            entity.entity_id
            for entity in registry.entities.values()
            if entity.platform == DOMAIN
        ]
        errors: dict[str, str] = {}
        if user_input is not None:
            relay = user_input[CONF_RELAY]
            light = user_input[CONF_LIGHT]
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "empty_name"
            elif relay == light:
                errors["base"] = "same_entity"
            elif relay in excluded or light in excluded:
                errors["base"] = "recursive_entity"
            elif relay.split(".")[0] not in {"light", "switch"} or not light.startswith(
                "light."
            ):
                errors["base"] = "invalid_entity"
            elif any(
                self.hass.states.get(entity_id) is None
                and registry.async_get(entity_id) is None
                for entity_id in (relay, light)
            ):
                errors["base"] = "entity_not_found"
            else:
                # A physical relay/source must not be controlled by two wrappers.
                for entry in self._async_current_entries():
                    if {relay, light} & {
                        entry.data[CONF_RELAY],
                        entry.data[CONF_LIGHT],
                    }:
                        return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(f"{relay}|{light}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={**user_input, CONF_NAME: name},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Relay-backed Light"): str,
                vol.Required(CONF_RELAY): EntitySelector(
                    EntitySelectorConfig(
                        domain=["switch", "light"], exclude_entities=excluded
                    )
                ),
                vol.Required(CONF_LIGHT): EntitySelector(
                    EntitySelectorConfig(domain="light", exclude_entities=excluded)
                ),
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class RelayBackedLightOptionsFlow(OptionsFlowWithReload):
    """Edit timing without altering the identity or wiring of the light."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Apply bounded timing options."""
        schema = timing_schema(dict(self.config_entry.options))
        if user_input is not None:
            validated = schema(user_input)
            if int(validated[CONF_RETRY_COUNT]) != validated[CONF_RETRY_COUNT]:
                return self.async_show_form(
                    step_id="init",
                    data_schema=schema,
                    errors={CONF_RETRY_COUNT: "whole_number"},
                )
            validated[CONF_RETRY_COUNT] = int(validated[CONF_RETRY_COUNT])
            return self.async_create_entry(title="", data=validated)
        return self.async_show_form(step_id="init", data_schema=schema)
