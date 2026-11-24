# Contributing

Use English for code, issues, and the main documentation. Keep the German
documentation consistent with behavior changes.

## Local checks

Use an isolated Python environment, version **3.14.2 or later** in the 3.14
series. Install the dependencies from `requirements-dev.txt` with pip, then run
`ruff check .`, `ruff format --check .`, and `pytest` at the repository root.
No Home Assistant instance, `/config` directory, or credentials are required.

The pinned pytest plugin supplies HA **2026.10.4**. Do not add a conflicting
direct Home Assistant requirement. Minimum support is HA **2026.10.0**.
Verify compatibility with the minimum and current supported versions separately
when behavior depends on an HA version. No strict coverage threshold is imposed;
meaningful behavioral tests are still required.

## Behavioral contract

- Keep the domain `relay_backed_light` and UI-only configuration.
- Exactly one relay (`switch` or `light`), one distinct source `light`, and a name.
  Relay/source changes require removing and re-adding the entry; timings use options.
- Forward only supported source brightness, color, effects, flash, and on
  transition. Off always requests immediate relay power-off, ignoring transition.
- New commands cancel previous work per entity. Relay off/unavailable cancels
  pending on work; never resurrect power for a cancelled command.
- Do not power relays on startup or source reconnection. No automatic migration,
  installation, Zigbee discovery, or changes to device power-on behavior.
- Treat cached source state as non-authoritative after restored power. Test
  timeout failure and unsuccessful retries, not just successful cold starts.
- Defaults: boot delay 2 s, relay timeout 5 s, light timeout 20 s, three total
  cold-start attempts, retry interval 2 s; one attempt when already powered.

Add regression tests for races, cancellation, capability filtering, options,
and error paths. Never use real relay hardware in automated tests.

## Pull requests and publication

Describe the problem, behavioral changes, tests, and migration impact. Do not
include local HA data, `.storage`, credentials, logs, or backups. Contributors
must have the right to submit code under the project's MIT license.

CI runs Ruff, pytest, hassfest, and HACS validation. Complete real maintainer and
repository metadata before expecting publication validators to pass; do not
invent public URLs. See the [release checklist](docs/releasing.md). Publication
is deliberate through a GitHub release, never automatic on a default-branch push.
