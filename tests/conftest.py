"""Use real Home Assistant fixtures and enable the local integration."""

import pytest
from homeassistant.components.light.const import DATA_COMPONENT
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.relay_backed_light.const import (
    CONF_LIGHT,
    CONF_RELAY,
    DEFAULT_OPTIONS,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Discover the integration without replacing Home Assistant modules."""


@pytest.fixture
def setup_light(hass):
    """Set up the real config entry and platform with physical state entities."""

    async def setup(
        *,
        relay="switch.power",
        relay_state="off",
        source_state="off",
        attributes=None,
        options=None,
    ):
        if relay_state is not None:
            hass.states.async_set(relay, relay_state)
        if source_state is not None:
            hass.states.async_set("light.bulb", source_state, attributes or {})
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Virtual",
            data={"name": "Virtual", CONF_RELAY: relay, CONF_LIGHT: "light.bulb"},
            options=DEFAULT_OPTIONS
            | {"boot_delay": 0, "retry_interval": 0}
            | (options or {}),
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = er.async_get(hass).async_get_entity_id(
            "light", DOMAIN, entry.entry_id
        )
        assert entity_id is not None, "The real light platform did not add its entity"
        entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
        assert entity is not None
        return entry, entity

    return setup
