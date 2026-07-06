# Versioning policy

NW-API uses explicit `V`-prefixed release versions.

## Version forms

- Formal release: `V0.0.X`
  - Example: `V0.0.2`
  - Use for versions that are intended to appear in the public update flow.
- Patch or small fix release: `V0.0.X.Y`
  - Example: `V0.0.1.2`
  - Use when a small production-compatible fix must be distinguishable from the prior release.
- Release candidate: `V0.0.X-rc.N`
  - Example: `V0.0.2-rc.1`
  - Use for pre-release validation before a formal release.
- Preview-only/internal changes:
  - Do not bump `APP_VERSION` by default.
  - Record the commit and validation result in `docs/phase0/` instead.

## Consistency rules

For a public release, these values must match exactly:

1. `APP_VERSION` in `services/xapi-portal/xapi_portal.py`
2. GitHub Release tag
3. Release package `VERSION`
4. Release asset name, for example `nw-api-V0.0.2-linux-amd64.tar.gz`

Do not publish a formal release where the tag and `APP_VERSION` differ. The online update checker compares versions and expects the public tag, release package, and portal display version to describe the same release.

## Build examples

Build a formal release package:

```bash
python3 scripts/build-release-package.py --version V0.0.2 --set-app-version
```

Build a release-candidate package:

```bash
python3 scripts/build-release-package.py --version V0.0.2-rc.1 --set-app-version
```

Preview-only performance or diagnostics commits should normally remain untagged and should not change `APP_VERSION`.
