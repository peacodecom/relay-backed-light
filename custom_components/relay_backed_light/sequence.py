"""Power sequencing, independent of Home Assistant for deterministic tests."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


class SequenceTimeout(Exception):
    """A relay or source did not reach a usable HA state in time."""


class SourceCommandError(Exception):
    """The source light rejected a command."""


@dataclass(frozen=True, slots=True)
class Timing:
    """Timing parameters in seconds; retries count total cold-start attempts."""

    boot_delay: float = 2.0
    relay_timeout: float = 5.0
    light_timeout: float = 20.0
    retry_count: int = 3
    retry_interval: float = 2.0


class PowerSequence:
    """Latest-command-wins sequencing, isolated for each virtual light."""

    def __init__(
        self,
        *,
        relay_is_on: Callable[[], bool],
        source_is_ready: Callable[[], bool],
        set_relay: Callable[[bool], Awaitable[None]],
        turn_on_source: Callable[[dict[str, Any]], Awaitable[None]],
        wait_for_state: Callable[[Callable[[], bool], float], Awaitable[bool]],
        timing: Timing,
    ) -> None:
        """Accept state and service adapters, not entity-specific HA objects."""
        self._relay_is_on = relay_is_on
        self._source_is_ready = source_is_ready
        self._set_relay = set_relay
        self._turn_on_source = turn_on_source
        self._wait_for_state = wait_for_state
        self._timing = timing
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._turning_on = False
        self._closed = False
        self._needs_startup = False

    async def async_execute(
        self, turn_on: bool, data: dict[str, Any] | None = None
    ) -> None:
        """Replace the previous operation and wait for this one to finish.

        A superseded caller finishes normally. Cancellation of the caller itself
        still propagates. Keep cold-start status across superseding commands:
        an already-on relay does not mean the bulb has finished booting.
        """
        async with self._lock:
            if self._closed:
                return
            await self._async_cancel()
            self._turning_on = turn_on
            task = self._task = asyncio.create_task(
                self._async_turn_on(dict(data or {}))
                if turn_on
                else self._async_turn_off(),
                name="relay_backed_light_sequence",
            )
        try:
            await task
        except asyncio.CancelledError:
            caller = asyncio.current_task()
            if caller is not None and caller.cancelling():
                raise
        finally:
            if self._task is task:
                self._task = None
                self._turning_on = False

    def cancel_pending_turn_on(self) -> None:
        """Immediately cancel startup after an external loss of relay power."""
        if self._turning_on and self._task is not None:
            self._needs_startup = True
            self._task.cancel()

    async def async_close(self) -> None:
        """Stop pending work, preventing new work after entity removal."""
        async with self._lock:
            self._closed = True
            await self._async_cancel()

    async def _async_cancel(self) -> None:
        """Drain the previous task before another service sequence starts."""
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _async_turn_off(self) -> None:
        """Cut power immediately; do not send a separate bulb command."""
        self._needs_startup = True
        await self._set_relay(False)

    async def _async_turn_on(self, data: dict[str, Any]) -> None:
        """Power up, wait, and repeat source commands after a cold start."""
        if not self._relay_is_on():
            self._needs_startup = True
            await self._set_relay(True)
        cold_start = self._needs_startup
        if not await self._wait_for_state(
            self._relay_is_on, self._timing.relay_timeout
        ):
            raise SequenceTimeout("relay")
        if cold_start:
            await asyncio.sleep(self._timing.boot_delay)
        if not await self._wait_for_state(
            self._source_is_ready, self._timing.light_timeout
        ):
            raise SequenceTimeout("light")
        attempts = self._timing.retry_count if cold_start else 1
        last_error: SourceCommandError | None = None
        succeeded = False
        for attempt in range(attempts):
            # A queued light command must never restore externally cut power.
            if not self._relay_is_on():
                return
            try:
                await self._turn_on_source(data)
            except SourceCommandError as err:
                last_error = err
            else:
                succeeded = True
            if attempt + 1 < attempts:
                await asyncio.sleep(self._timing.retry_interval)
        if not succeeded and last_error is not None:
            raise last_error
        self._needs_startup = False
