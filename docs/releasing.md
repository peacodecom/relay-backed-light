# Release checklist

## Before the first public release

- Publish at <https://github.com/peacodecom/relay-backed-light> under the registered
  trademark **peacode**. Copyright holder and maintainer:
  [Norman Bauer](https://github.com/norman-bauer).
- Check that repository links are reachable and manifest `codeowners` contains
  `@norman-bauer`. Validate the completed manifest with hassfest and the
  HACS/Marketplace checks.
- Keep GitHub repository topics set under **About → Edit → Topics**, for example
  `home-assistant`, `home-assistant-custom-component`, `hacs`, `lighting`, and
  `relay`. Topics are GitHub repository settings, not manifest or HACS JSON
  fields. Keep manifest categories aligned with the integration's purpose:
  `helpers` and `lighting`.
- Ensure `custom_components/relay_backed_light` contains the complete integration,
  including its manifest, config/options flow, translations, and license handling
  as appropriate. Review the initial implementation before hardware testing.
- Ensure repository tests exist and pass. Empty test collection is not an
  acceptable release. Add no live `/config` access, private HA data, or secrets.
- Verify the UI accepts one `switch`/`light` relay, one source `light`, and a name;
  source and relay are immutable except by removing/re-adding the entry.
- Verify editable timing defaults, on-only parameter forwarding, immediate
  relay-off without transition, per-entity cancellation, and external relay
  off/unavailable cancellation. Test that startup/reconnect never powers relays.
- Test stale source state after power restoration, failure on startup timeout,
  three total cold-start attempts versus one powered attempt, and retry failure.
  Do not describe this as guaranteed readiness or Zigbee discovery.
- Test the minimum supported HA **2026.10.0** with Python **3.14.2** and current
  supported HA versions in disposable installations. The pinned test
  plugin **0.13.375** brings HA **2026.10.4**, not every supported version.
  Do not override that dependency with a conflicting direct HA requirement.
- Review the English and German documentation. Keep private installation data,
  site-specific instructions, and credentials out of the public repository.
  Do not migrate an installation or edit `.storage` automatically.

## Each release

1. Update the integration manifest version and release notes; check the version
   agrees with the intended tag. Document compatibility and known limitations.
2. Run the pinned Ruff checks and pytest suite. Require successful CI, hassfest,
   and HACS validation for the release commit. The release job repeats lint,
   formatting, and tests before packaging; it does not replace review of those
   validation jobs.
3. Inspect the complete repository for secrets and local configuration. Keep
   backups, `.storage`, tokens, logs, databases, and local installation data out.
4. Create and **publish a GitHub release** for the reviewed tag. A push to the
   default branch does not publish or upload an integration automatically.
5. The release job first installs pinned requirements and runs Ruff and pytest.
   Only after success does it archive the contents of
   `custom_components/relay_backed_light` as `relay_backed_light.zip` and upload
   that asset to the published release using `gh` and `GH_TOKEN`.
6. Inspect the uploaded archive: `manifest.json` must be at its root, with no
   enclosing `custom_components` directory, repository docs, tests, or private
    configuration. Confirm the asset filename matches the release workflow.
    HACS/Marketplace currently installs from the repository rather than requiring
    this optional ZIP asset.
7. Test manual extraction into the integration directory and installation through
   the actual HACS custom repository. Check a clean install and an upgrade with
   a backup; never assume the asset upload proves runtime compatibility.

Publishing the GitHub release triggers the build; the release may be visible
before its asset is uploaded. If validation fails, no archive is uploaded by
that run. Fix and validate the failure before deliberately rerunning/releasing.
The workflow uses `--clobber` when uploading, so an intentional rerun replaces
an asset of the same name on that release. No workflow needs the maintainer's
Home Assistant configuration directory or access to `/config`.
