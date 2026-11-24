"""Deterministic sequencing tests: every asynchronous pause is event-driven."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from custom_components.relay_backed_light import sequence
from custom_components.relay_backed_light.sequence import (
    PowerSequence,
    SequenceTimeout,
    SourceCommandError,
    Timing,
)


@pytest.fixture
def rig(monkeypatch):
    """Expose observable sleep barriers, never advancing real wall-clock time."""
    pauses = asyncio.Queue()

    async def sleep(delay):
        release = asyncio.Event()
        await pauses.put((delay, release))
        await release.wait()

    proxy = SimpleNamespace(
        **{
            key: getattr(asyncio, key)
            for key in (
                "Lock",
                "create_task",
                "CancelledError",
                "current_task",
                "gather",
            )
        },
        sleep=sleep,
    )
    monkeypatch.setattr(sequence, "asyncio", proxy)
    state = SimpleNamespace(power=False, ready=True)

    async def relay(on):
        state.power = on

    async def wait(predicate, timeout):
        return predicate()

    set_relay = AsyncMock(side_effect=relay)
    source = AsyncMock()
    wait_for_state = AsyncMock(side_effect=wait)
    timing = Timing(
        boot_delay=11,
        relay_timeout=12,
        light_timeout=13,
        retry_count=3,
        retry_interval=14,
    )
    controller = PowerSequence(
        relay_is_on=lambda: state.power,
        source_is_ready=lambda: state.ready,
        set_relay=set_relay,
        turn_on_source=source,
        wait_for_state=wait_for_state,
        timing=timing,
    )
    return SimpleNamespace(
        controller=controller,
        state=state,
        relay=set_relay,
        source=source,
        wait=wait_for_state,
        pauses=pauses,
    )


async def pause(rig, expected):
    """Fail promptly rather than hanging if the expected barrier is absent."""
    async with asyncio.timeout(2):
        delay, release = await rig.pauses.get()
    assert delay == expected
    return release


async def finish_cold_start(rig, task):
    for delay in (11, 14, 14):
        (await pause(rig, delay)).set()
    await task


async def test_cold_boot_repeats_payload_and_warm_command_runs_once(rig):
    payload = {"brightness": 123, "transition": 0.5}
    task = asyncio.create_task(rig.controller.async_execute(True, payload))
    await finish_cold_start(rig, task)
    rig.relay.assert_awaited_once_with(True)
    assert rig.source.await_count == 3
    assert all(call.args == (payload,) for call in rig.source.await_args_list)
    assert [call.args[1] for call in rig.wait.await_args_list] == [12, 13]
    await rig.controller.async_execute(True, {"brightness": 20})
    assert rig.source.await_count == 4
    rig.source.assert_awaited_with({"brightness": 20})
    assert rig.pauses.empty()


async def test_already_powered_only_one_attempt_even_on_error(rig):
    rig.state.power = True
    rig.source.side_effect = SourceCommandError("offline")
    with pytest.raises(SourceCommandError, match="offline"):
        await rig.controller.async_execute(True)
    rig.source.assert_awaited_once_with({})
    rig.relay.assert_not_awaited()
    assert rig.pauses.empty()


@pytest.mark.parametrize("during_retry", [False, True])
async def test_last_off_cancels_startup_and_never_sends_later_on(rig, during_retry):
    task = asyncio.create_task(rig.controller.async_execute(True))
    boot = await pause(rig, 11)
    if during_retry:
        boot.set()
        await pause(rig, 14)
    calls = rig.source.await_count
    await rig.controller.async_execute(False)
    await task  # Superseded callers finish normally.
    assert not rig.state.power
    assert rig.source.await_count == calls
    assert [call.args for call in rig.relay.await_args_list] == [(True,), (False,)]


async def test_external_cancel_cannot_restore_power(rig):
    task = asyncio.create_task(rig.controller.async_execute(True))
    await pause(rig, 11)
    rig.state.power = False
    rig.controller.cancel_pending_turn_on()
    await task
    rig.source.assert_not_awaited()
    rig.relay.assert_awaited_once_with(True)


async def test_hardware_power_is_rechecked_between_retries(rig):
    task = asyncio.create_task(rig.controller.async_execute(True))
    (await pause(rig, 11)).set()
    retry = await pause(rig, 14)
    rig.state.power = False  # No cancel callback: exercise the hardware guard.
    retry.set()
    await task
    rig.source.assert_awaited_once_with({})
    rig.relay.assert_awaited_once_with(True)


@pytest.mark.parametrize("all_fail", [False, True])
async def test_source_failures_retry_and_raise_only_if_all_fail(rig, all_fail):
    error = SourceCommandError("rejected")
    rig.source.side_effect = [error, error if all_fail else None, error]
    task = asyncio.create_task(rig.controller.async_execute(True))
    if all_fail:
        with pytest.raises(SourceCommandError, match="rejected"):
            await finish_cold_start(rig, task)
    else:
        await finish_cold_start(rig, task)
    assert rig.source.await_count == 3


@pytest.mark.parametrize("failed_wait, expected", [(1, "relay"), (2, "light")])
async def test_timeout_never_sends_source_command(rig, failed_wait, expected):
    rig.wait.side_effect = [False] if failed_wait == 1 else [True, False]
    task = asyncio.create_task(rig.controller.async_execute(True))
    if failed_wait == 2:
        (await pause(rig, 11)).set()
    with pytest.raises(SequenceTimeout, match=expected):
        await task
    rig.source.assert_not_awaited()


async def test_superseding_on_preserves_cold_start_and_latest_payload(rig):
    first = asyncio.create_task(rig.controller.async_execute(True, {"brightness": 1}))
    await pause(rig, 11)
    second = asyncio.create_task(rig.controller.async_execute(True, {"brightness": 2}))
    await finish_cold_start(rig, second)
    await first
    rig.relay.assert_awaited_once_with(True)
    assert rig.source.await_count == 3
    assert all(call.args == ({"brightness": 2},) for call in rig.source.await_args_list)


async def test_caller_cancellation_propagates_and_stops_work(rig):
    task = asyncio.create_task(rig.controller.async_execute(True))
    await pause(rig, 11)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    rig.source.assert_not_awaited()


async def test_instances_have_independent_locks_tasks_and_power(rig):
    other_source = AsyncMock()
    other_relay = AsyncMock()
    other = PowerSequence(
        relay_is_on=lambda: True,
        source_is_ready=lambda: True,
        set_relay=other_relay,
        turn_on_source=other_source,
        wait_for_state=AsyncMock(return_value=True),
        timing=Timing(),
    )
    task = asyncio.create_task(rig.controller.async_execute(True))
    await pause(rig, 11)
    await other.async_execute(True, {"brightness": 99})
    await other.async_close()
    other_source.assert_awaited_once_with({"brightness": 99})
    rig.source.assert_not_awaited()
    await rig.controller.async_execute(False)
    await task


async def test_close_cancels_pending_and_prevents_all_future_work(rig):
    task = asyncio.create_task(rig.controller.async_execute(True))
    await pause(rig, 11)
    await rig.controller.async_close()
    await task
    await rig.controller.async_execute(True)
    await rig.controller.async_execute(False)
    rig.source.assert_not_awaited()
    rig.relay.assert_awaited_once_with(True)
