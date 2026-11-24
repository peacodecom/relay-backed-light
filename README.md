# Relay-backed Light

A Home Assistant custom integration for a light whose power is controlled by a
separate relay. Integration domain: `relay_backed_light`.

Published by [peacode](https://peacode.com), a registered trademark.
Copyright and maintenance: [Norman Bauer](https://github.com/norman-bauer).
Source: [peacodecom/relay-backed-light](https://github.com/peacodecom/relay-backed-light).

[Deutsche Dokumentation](docs/README.de.md) ·
[Release checklist](docs/releasing.md)

## Requirements and status

- Home Assistant **2026.10.0 or later**, Python **3.14.2 or later**.
- One existing relay entity in the `switch` **or** `light` domain and one
  existing source entity in the `light` domain.
- The source integration must already be configured. This integration does not
  install integrations, discover Zigbee devices, or change device firmware or
  power-on behavior.

Version 0.1.0 is an initial development implementation, not yet validated on
physical hardware. The source code and automated tests are maintained in this
repository. Release assets are available only after a version has been
published and its packaging workflow has completed successfully. Checking out
the repository does not install the integration or change an existing setup.

## Installation and setup

Back up Home Assistant first.

### Marketplace: Home Assistant 2026.11 and later

HACS is built into Home Assistant as the **Marketplace** starting with 2026.11.
Do not install the old HACS custom integration on these versions.

1. As an administrator, open **Settings → Marketplace** and accept the
  community-content warning if prompted.
2. In the upper-right corner, select **Add from link**. Connect your GitHub
  account if the Marketplace asks you to do so.
3. Under **GitHub link**, enter
  **https://github.com/peacodecom/relay-backed-light** and select **Add**.
4. If asked for **Type**, choose **Integration**, then select **Add** again.
5. Open **Relay-backed Light**, select **Install**, review the version, and
  confirm. Follow any restart prompt before continuing with setup below.

See the official [Marketplace custom-repository instructions](https://www.home-assistant.io/integrations/marketplace/#custom-repositories).

### HACS: Home Assistant 2026.10

If HACS is not configured, follow its official [setup instructions](https://www.hacs.xyz/docs/use/).

1. Open **HACS** and select the three-dot menu in the upper-right corner.
2. Select **Custom repositories**.
3. Enter **https://github.com/peacodecom/relay-backed-light**.
4. Select type/category **Integration** and select **Add**.
5. Find **Relay-backed Light**, open it, and choose **Download** (or **Install**,
  depending on the HACS UI). Confirm the version.
6. Restart Home Assistant, then continue with setup below.

See the official [HACS custom-repository instructions](https://www.hacs.xyz/docs/faq/custom_repositories/).

### Manual installation

Download `relay_backed_light.zip` from the project's releases. Create
`custom_components/relay_backed_light` inside your Home Assistant configuration
directory and extract the archive there. Its `manifest.json` must be directly
inside that integration directory, not another nested directory. The ZIP
contains the integration's **contents**, not its enclosing directory. Do not
extract it into the configuration root. Restart Home Assistant.

Alternatively, copy only the source directory
`custom_components/relay_backed_light` into your configuration's
`custom_components` directory. Do not copy the whole repository.

### Configure the virtual light

In **Settings → Devices & services → Add integration → Relay-backed Light**,
choose exactly:

1. One relay (`switch.*` or `light.*`).
2. One source light (`light.*`).
3. A name for the new light.

The relay and source must be distinct entities; do not select the wrapper itself
or create wrapper dependency cycles, including through light groups. Each
physical relay or source may be used by only one entry. Configure through the UI only: **YAML
integration configuration is not supported**. Relay and source selections are
immutable after setup; remove the config entry and add it again to change them.
Timing settings are editable through the integration's options UI.

After a Marketplace/HACS update, restart Home Assistant to load the new
integration code. Review release notes and keep a backup before updating.

## Behavior and limits

- **On:** explicitly request relay power, wait for the relay within its timeout,
  allow the cold-start boot delay if power had been off, and wait for the source
  within its timeout. Forward source-supported brightness, color, effects,
  flash, and transition parameters to the source's `light.turn_on` action.
  Unsupported source capabilities are not added by the wrapper.
- **Off:** immediately request relay power off, without waiting for a source
  fade or graceful shutdown. An off transition is ignored. “Immediately” means
  no intentional software delay; relay hardware/network latency still applies.
  This is a power-cut request, not a safety-rated disconnection guarantee.
- A new command cancels the previous operation **for that wrapper entity**.
  External relay off or unavailable cancels a pending on operation; the pending
  operation must not turn the relay back on. Already dispatched commands cannot
  be recalled from the device or its network.
- Startup and source reconnection never automatically activate the relay.
  There is no background power-restoration or automatic migration behavior.
- A source state cached in Home Assistant is **not authoritative after power
  restoration**. An `on`/`off` state does not prove that the lamp is reachable or
  ready to receive commands. Boot delay and retries are heuristics, not a
  readiness handshake or delivery confirmation.
- Startup can fail on a relay/source timeout before any source command is sent.
  Repeated commands can also fail. Neither the first attempt nor retries
  guarantee the requested result. There is no Zigbee-specific readiness probe,
  discovery, interview, or re-pairing sequence.
- The lamp's configured hardware power-on behavior is unchanged. It may light
  up at its own restored settings before the requested parameters take effect.
  Repeated effects or flashes may restart those effects.

### Options and defaults

| Option | Default | Meaning |
| --- | --- | --- |
| `boot_delay` | 2 seconds | Additional settling delay after cold power restoration |
| `relay_timeout` | 5 seconds | Maximum wait for the relay to report on |
| `light_timeout` | 20 seconds | Maximum wait for a usable source state; not proof of readiness |
| `retry_count` | 3 | **Total** source on attempts after a cold start, not three extra retries |
| `retry_interval` | 2 seconds | Delay between source on attempts, not after the last attempt |

When the relay is already powered, send **one** source on attempt, rather than
the cold-start `retry_count`, unless a previous cold-start sequence has not yet
finished. Superseding an on command during startup retains the boot delay and
retry behavior. These timings are not an end-to-end service-level
guarantee: source integration calls and transport delays may add time. A newer
command or external relay cancellation takes precedence over pending waits and
retries.

Capabilities are cached in memory when the source reports them. If HA starts
while the source is unavailable and provides no capability attributes, the
wrapper initially offers basic on/off only. It learns the other capabilities
when the source reports them. Entity selections use entity IDs; changing the
physical entities' IDs requires removing and re-adding the wrapper.

## Development

Use an isolated Python 3.14 environment with Python 3.14.2 or later. Install the
pinned development requirements with pip. Run `ruff check .`,
`ruff format --check .`, and `pytest` from the repository root.

The test dependency `pytest-homeassistant-custom-component==0.13.375` brings
**Home Assistant 2026.10.4**. Do not add a conflicting direct Home Assistant pin.
This test baseline differs from the minimum supported HA version (2026.10.0).
Test the minimum and current supported HA versions separately before release;
the baseline alone does not establish compatibility with every later version.
Tests should cover cancellation, power cuts, stale state, startup timeouts,
capability forwarding, and no startup/reconnection relay activation.

CI uses only this repository. It needs no access to a live Home Assistant
installation, credentials, or `/config`. See [CONTRIBUTING.md](CONTRIBUTING.md)
and [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE), copyright © 2026 Norman Bauer.
See [ownership and maintenance](AUTHORS.md) for publisher and trademark details.
