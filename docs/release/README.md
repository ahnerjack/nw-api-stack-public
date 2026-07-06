# Release operations

This directory contains the release rules and production update gate for NW-API.

## Documents

- `versioning.md`
  - Defines allowed version formats.
  - Formal releases use `V0.0.X`.
  - Patch/small fix releases use `V0.0.X.Y`.
  - Release candidates use `V0.0.X-rc.N`.
- `production-update-gate.md`
  - Mandatory checklist before publishing or applying a formal production update.
  - Covers version consistency, secret scanning, tests, package inspection, smoke checks, backup, rollback, and stop conditions.

## Current policy

- Preview-only work does not bump `APP_VERSION` by default.
- A dry-run package is not a release.
- Production must not be updated without an explicit production-update request from the operator.
- GitHub Release tag, `APP_VERSION`, package `VERSION`, and asset name must match for formal releases.

## Typical safe flow

1. Finish and push code changes.
2. Review `docs/release/versioning.md`.
3. Complete `docs/release/production-update-gate.md`.
4. Build a release candidate with a compliant version, for example:

```bash
python3 scripts/build-release-package.py --version V0.0.2-rc.1 --set-app-version --dist dist
```

5. Inspect package manifest and run smoke checks.
6. Only after explicit approval, publish a GitHub Release or apply production update.

## Latest dry-run artifact

The latest local RC dry-run from 2026-07-06 was archived on NAS:

`/volume1/hermes/projects/nw-api-stack-public/release-dryruns/2026-07-06`

It was not published and was not applied to production.
