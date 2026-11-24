"""Exercise the actual HA platform, states, registry, services and unload."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Context, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import async_mock_service


@pytest.mark.parametrize(
    "relay,source,expected",
    [
        ("off", "unavailable", "off"),
        ("off", None, "off"),
        ("off", "on", "off"),
        ("on", "off", "off"),
        ("on", "on", "on"),
        ("on", "unavailable", "unavailable"),
        ("on", "unknown", "unavailable"),
        ("on", None, "unavailable"),
        ("unavailable", "on", "unavailable"),
        ("unknown", "on", "unavailable"),
        (None, "on", "unavailable"),
    ],
)
async def test_availability_and_power_state(hass, setup_light, relay, source, expected):
    _, entity = await setup_light(relay_state=relay, source_state=source)
    assert hass.states.get(entity.entity_id).state == expected


async def test_setup_never_calls_physical_services(hass, setup_light):
    calls = []
    remove_listener = hass.bus.async_listen(EVENT_CALL_SERVICE, calls.append)
    try:
        await setup_light(relay_state="off", source_state="unavailable")
        assert not calls
    finally:
        remove_listener()


async def test_state_events_mirror_and_retain_capabilities(hass, setup_light):
    features = (
        LightEntityFeature.EFFECT
        | LightEntityFeature.FLASH
        | LightEntityFeature.TRANSITION
    )
    attrs = {
        "supported_color_modes": ["color_temp", "hs"],
        "color_mode": "hs",
        "brightness": 142,
        "hs_color": (120, 50),
        "color_temp_kelvin": 3200,
        "effect": "rainbow",
        "effect_list": ["rainbow", "solid"],
        "min_color_temp_kelvin": 2200,
        "max_color_temp_kelvin": 6500,
        "supported_features": int(features),
    }
    _, entity = await setup_light(relay_state="on", source_state="on", attributes=attrs)
    state = hass.states.get(entity.entity_id)
    assert state.state == "on"
    assert entity.supported_color_modes == {ColorMode.COLOR_TEMP, ColorMode.HS}
    assert entity.supported_features == features
    for key in (
        "brightness",
        "hs_color",
        "effect",
        "effect_list",
        "min_color_temp_kelvin",
        "max_color_temp_kelvin",
    ):
        assert state.attributes[key] == attrs[key]
    hass.states.async_set(
        "light.bulb", "on", attrs | {"brightness": 80, "effect": "solid"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).attributes["brightness"] == 80
    assert hass.states.get(entity.entity_id).attributes["effect"] == "solid"
    hass.states.async_set("switch.power", "off")
    hass.states.async_set("light.bulb", "unavailable")
    await hass.async_block_till_done()
    state = hass.states.get(entity.entity_id)
    assert state.state == "off"
    assert entity.supported_color_modes == {ColorMode.COLOR_TEMP, ColorMode.HS}
    assert entity.supported_features == features
    assert state.attributes["effect_list"] == attrs["effect_list"]
    assert state.attributes["min_color_temp_kelvin"] == 2200
    hass.states.async_set("switch.power", "on")
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).state == "unavailable"


@pytest.mark.parametrize(
    "modes",
    [
        ["onoff", "hs"],
        ["brightness", "color_temp"],
        ["unknown"],
        ["bogus"],
    ],
)
async def test_invalid_source_modes_do_not_prevent_setup(hass, setup_light, modes):
    # HA 2026.10's valid_supported_color_modes raises; it is not a bool predicate.
    _, entity = await setup_light(
        relay_state="off", attributes={"supported_color_modes": modes}
    )
    assert hass.states.get(entity.entity_id).state == "off"
    assert entity.supported_color_modes == {ColorMode.ONOFF}


@pytest.mark.parametrize("relay", ["switch.power", "light.power"])
async def test_service_arguments_context_and_relay_domain(hass, setup_light, relay):
    _, entity = await setup_light(relay=relay)
    calls = []

    @callback
    def record(call):
        calls.append(call)
        if call.data["entity_id"] == relay:
            hass.states.async_set(relay, "on" if call.service == "turn_on" else "off")

    # Physical entities use states and mock services; the virtual entity itself
    # was created by the real HA light platform, not constructed by the test.
    for domain in {"light", relay.split(".")[0]}:
        hass.services.async_register(domain, "turn_on", record)
        hass.services.async_register(domain, "turn_off", record)
    context = Context()
    entity.async_set_context(context)
    data = {
        "brightness": 128,
        "color_temp_kelvin": 3100,
        "transition": 0.5,
        "effect": "solid",
        "flash": "short",
    }
    await entity.async_turn_on(**data)
    assert calls[0].domain == relay.split(".")[0]
    assert calls[0].data == {"entity_id": relay}
    assert len(calls) == 4  # Relay plus three cold-start source commands.
    for call in calls[1:]:
        assert call.domain == "light"
        assert call.service == "turn_on"
        assert call.data == data | {"entity_id": "light.bulb"}
        assert call.context is context
    await entity.async_turn_off(transition=99)
    assert len(calls) == 5
    assert calls[-1].domain == relay.split(".")[0]
    assert calls[-1].service == "turn_off"
    assert calls[-1].data == {"entity_id": relay}
    assert calls[-1].context is context


async def test_actual_ha_light_service_dispatch(hass, setup_light):
    _, entity = await setup_light(
        relay_state="on",
        source_state="on",
        attributes={
            "supported_color_modes": ["brightness"],
            "color_mode": "brightness",
        },
    )
    calls = async_mock_service(hass, "switch", "turn_off")
    # Keep the real light.turn_off service so HA performs entity routing.
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity.entity_id}, blocking=True
    )
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "switch.power"}


async def test_source_service_error_is_wrapped(hass, setup_light):
    _, entity = await setup_light(relay_state="on")
    calls = async_mock_service(
        hass, "light", "turn_on", raise_exception=HomeAssistantError("offline")
    )
    with pytest.raises(HomeAssistantError, match="light.bulb.*offline"):
        await entity.async_turn_on(brightness=80)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "relay,source,expected",
    [
        ("off", "off", "relay"),
        ("on", "unavailable", "light"),
    ],
)
async def test_wait_timeout_error(hass, setup_light, relay, source, expected):
    _, entity = await setup_light(
        relay_state=relay,
        source_state=source,
        options={"relay_timeout": 0, "light_timeout": 0},
    )
    async_mock_service(hass, "switch", "turn_on")
    source_calls = async_mock_service(hass, "light", "turn_on")
    with pytest.raises(
        ServiceValidationError, match=f"Timed out waiting for {expected}"
    ):
        await entity.async_turn_on()
    assert not source_calls


async def test_unload_cancels_pending_work(hass, setup_light):
    entry, entity = await setup_light(relay_state="on", source_state="unavailable")
    waiting = asyncio.Event()
    never_ready = asyncio.Event()

    async def wait(predicate, timeout):
        if predicate():
            return True
        waiting.set()
        await never_ready.wait()
        return True

    source_calls = async_mock_service(hass, "light", "turn_on")
    with patch.object(
        entity._sequence, "_wait_for_state", new=AsyncMock(side_effect=wait)
    ):
        task = asyncio.create_task(entity.async_turn_on())
        async with asyncio.timeout(2):
            await waiting.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await task
    # HA keeps a registry-backed restored placeholder when a platform unloads.
    unloaded_state = hass.states.get(entity.entity_id)
    assert unloaded_state is not None
    assert unloaded_state.state == "unavailable"
    assert unloaded_state.attributes["restored"] is True
    hass.states.async_set("light.bulb", "on")
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id) is unloaded_state
    assert not source_calls
    await entity.async_turn_on()
    assert not source_calls


@pytest.mark.parametrize("new_state", ["off", "unavailable", "unknown", None])
async def test_external_relay_loss_cancels_wait(hass, setup_light, new_state):
    _, entity = await setup_light(relay_state="on", source_state="unavailable")
    waiting = asyncio.Event()
    original_wait = entity._async_wait_for_state

    async def wait(predicate, timeout):
        if not predicate():
            waiting.set()
        return await original_wait(predicate, timeout)

    source_calls = async_mock_service(hass, "light", "turn_on")
    relay_calls = async_mock_service(hass, "switch", "turn_on")
    with patch.object(entity._sequence, "_wait_for_state", side_effect=wait):
        task = asyncio.create_task(entity.async_turn_on())
        async with asyncio.timeout(2):
            await waiting.wait()
            if new_state is None:
                hass.states.async_remove("switch.power")
            else:
                hass.states.async_set("switch.power", new_state)
            await task
    hass.states.async_set("light.bulb", "on")
    await hass.async_block_till_done()
    assert not relay_calls
    assert not source_calls


async def test_source_reconnect_does_not_power_relay(hass, setup_light):
    await setup_light(relay_state="off", source_state="unavailable")
    relay_calls = async_mock_service(hass, "switch", "turn_on")
    source_calls = async_mock_service(hass, "light", "turn_on")
    hass.states.async_set("light.bulb", "on")
    await hass.async_block_till_done()
    assert not (relay_calls or source_calls)
