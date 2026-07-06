# Stage 4 formal update path validation

Date: 2026-07-07
Branch: public-sanitized
Formal production updated: no

## Scope

Stage 4 validates and hardens the formal online-update path without deploying the formal runtime.

## Findings fixed

- Added missing Release asset updater:
  - `scripts/preview_release_update.py`
  - Downloads GitHub Release assets through the asset API.
  - Verifies `checksums.txt` SHA256.
  - Extracts and checks `manifest.json` / `VERSION`.
  - Runs the provided deploy command only after verification.
- Added missing package deployer:
  - `scripts/deploy-preview-package.sh`
  - Supports `--force --runtime auto <asset>` and `--root/--activate` rollback activation.
  - Extracts package under a release root and runs deploy scripts from the activated release tree.
- Made Release mode fail fast if updater/deployer scripts are missing.
  - It no longer silently falls back to `deploy-aliyun.sh` for a tar asset.
- Fixed `/version-status` Release-mode default path.
  - Release mode now checks GitHub Release state instead of accidentally using local Git state on first open.
- Added formal update env example keys to `systemd/xapi-portal.env.example`.
- Added updater/deployer scripts to `scripts/build-release-package.py` `PACKAGE_FILES`, so release packages are self-contained.

## Verification

- Python compile:
  - `scripts/preview_release_update.py`
  - `scripts/build-release-package.py`
  - `services/xapi-portal/xapi_portal.py`
  - `services/xapi-v1-wrapper/gateway_core.py`
  - `services/xapi-v1-wrapper/xapi_v1_wrapper.py`
- Shell syntax:
  - `scripts/deploy-preview-package.sh`
  - `scripts/deploy-aliyun.sh`
  - `scripts/deploy-sub2api-host.sh`
- Regression:
  - phase1 gateway core: 22/22 OK
  - phase0 wrapper regression: 15/15 OK
  - release versioning: 2/2 OK
- Package dry-run:
  - Version: `V0.0.2-rc.2`
  - Artifact: `stage4-dist/nw-api-V0.0.2-rc.2-linux-amd64.tar.gz`
  - SHA256: `8741a9061c56759c343f7d3b623baa035978c2d51b961ef31926acde4a333c80`
  - Package contains:
    - `scripts/preview_release_update.py`
    - `scripts/deploy-preview-package.sh`
    - `manifest.json`
    - `manifest.sha256`
    - `VERSION`

## Status

Stage 4 is complete as a formal update-path hardening and dry-run validation.
No formal production update was performed.
