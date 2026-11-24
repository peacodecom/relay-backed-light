"""Real Home Assistant user and options flows."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.relay_backed_light.config_flow import timing_schema
from custom_components.relay_backed_light.const import (
    CONF_LIGHT,
    CONF_RELAY,
    DEFAULT_OPTIONS,
    DOMAIN,
)


@pytest.fixture
def physical_entities(hass):
    for entity_id in ("switch.power", "switch.other", "light.bulb", "light.other"):
        hass.states.async_set(entity_id, "off")
    return {"name": " Hall ", CONF_RELAY: "switch.power", CONF_LIGHT: "light.bulb"}


async def user_flow(hass, data):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def test_user_success_trims_name_and_creates_unique_id(hass, physical_entities):
    with patch(
        "custom_components.relay_backed_light.async_setup_entry",
        new=AsyncMock(return_value=True),
    ):
        result = await user_flow(hass, physical_entities)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hall"
    assert result["data"] == physical_entities | {"name": "Hall"}
    assert result["result"].unique_id == "switch.power|light.bulb"


@pytest.mark.parametrize(
    "changes", [{}, {CONF_RELAY: "switch.other"}, {CONF_LIGHT: "light.other"}]
)
async def test_duplicate_physical_devices_rejected(hass, physical_entities, changes):
    MockConfigEntry(domain=DOMAIN, data=physical_entities).add_to_hass(hass)
    result = await user_flow(hass, physical_entities | changes)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_same_entity_rejected(hass, physical_entities):
    result = await user_flow(hass, physical_entities | {CONF_RELAY: "light.bulb"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_entity"}


@pytest.mark.parametrize("field", [CONF_RELAY, CONF_LIGHT])
async def test_own_virtual_entity_rejected(hass, physical_entities, field):
    # Add the virtual entity after opening the form: this also exercises the
    # server-side recursion guard, not just the selector's exclusion list.
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    virtual = er.async_get(hass).async_get_or_create("light", DOMAIN, "existing")
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], physical_entities | {field: virtual.entity_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "recursive_entity"}


async def test_options_store_integer_retry_count_and_reload(hass, setup_light):
    entry, _ = await setup_light()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    options = DEFAULT_OPTIONS | {
        "boot_delay": 0.5,
        "relay_timeout": 9,
        "light_timeout": 45,
        "retry_count": 4.0,
        "retry_interval": 1.5,
    }
    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock(return_value=True)
    ) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], options
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(entry.options) == options
    assert type(entry.options["retry_count"]) is int
    reload.assert_awaited_once_with(entry.entry_id)


async def test_fractional_retries_rejected_without_reload(hass, setup_light):
    entry, _ = await setup_light()
    previous = dict(entry.options)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], DEFAULT_OPTIONS | {"retry_count": 1.5}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"retry_count": "whole_number"}
    assert dict(entry.options) == previous
    reload.assert_not_awaited()


@pytest.mark.parametrize(
    "key,value",
    [
        ("boot_delay", -0.5),
        ("boot_delay", 121),
        ("relay_timeout", 0),
        ("relay_timeout", 121),
        ("light_timeout", 0),
        ("light_timeout", 301),
        ("retry_count", 0),
        ("retry_count", 11),
        ("retry_interval", -0.5),
        ("retry_interval", 31),
    ],
)
def test_timing_bounds(key, value):
    with pytest.raises(vol.Invalid):
        timing_schema({})(DEFAULT_OPTIONS | {key: value})
