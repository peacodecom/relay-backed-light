# Security policy

## Reporting

Do not post credentials, private Home Assistant configuration, `.storage`,
device identifiers, or unredacted logs in public issues.

Maintainer: [Norman Bauer](https://github.com/norman-bauer).
Use the repository's [Security page](https://github.com/peacodecom/relay-backed-light/security)
and **Report a vulnerability** if private reporting is enabled. If it is
unavailable, open a minimal [issue](https://github.com/peacodecom/relay-backed-light/issues)
requesting a private reporting channel, without exploit details or sensitive
data. Do not assume a private reporting address or a response-time commitment.

Include affected versions, a minimal reproduction in an isolated environment,
impact, and redacted diagnostics through the agreed private channel.

## Scope and safe operation

This integration can switch mains-powered equipment through an existing relay.
It is not a safety system, emergency disconnect, or electrical interlock. Do not
rely on successful delivery of a command or retries for personal or equipment
safety. Follow the device manufacturer's installation and load requirements.

Keep Home Assistant, source integrations, and relay firmware maintained. Review
changes before installation and back up before upgrades. No automatic
installation or migration is performed. An HA state is not proof that a powered
device is electrically disconnected or ready.

Security fixes target the latest published project release on supported Home
Assistant/Python versions. No release or historical backport commitment is
implied before the first publication. Current minimums are HA 2026.10.0 and
Python 3.14.2.
