# Production update gate

This checklist must be completed before publishing or applying a formal NW-API production update.

## Hard rules

- Do not update production unless the operator explicitly asks to update/deploy/sync/fix production.
- Preview-only validation does not imply production approval.
- The web "立即更新" flow should only be used after this checklist is complete.
- If secrets, private keys, `.env`, auth caches, or real customer data appear in the diff or package, stop and remove them before publishing.

## Version gate

For a formal release, these must match exactly:

- `APP_VERSION` in `services/xapi-portal/xapi_portal.py`
- GitHub Release tag
- packaged `VERSION`
- asset name, for example `nw-api-V0.0.2-linux-amd64.tar.gz`

Allowed version forms are documented in `docs/release/versioning.md`:

- `V0.0.X`
- `V0.0.X.Y`
- `V0.0.X-rc.N`

Preview-only commits should normally remain untagged and should not bump `APP_VERSION`.

## Source risk gate

Before building a formal package, inspect the diff since the previous release:

```bash
git diff --stat <previous-release-tag>..HEAD
git diff <previous-release-tag>..HEAD -- \
  services/xapi-portal/xapi_portal.py \
  services/xapi-v1-wrapper/xapi_v1_wrapper.py \
  services/xapi-data/xapi_data_api.py \
  systemd/xapi-portal.service \
  systemd/xapi-v1-wrapper.service \
  systemd/xapi-data.service
```

Confirm which changes affect production and which are preview-only. Changes to shared source files under `services/xapi-portal/`, `services/xapi-v1-wrapper/`, or `services/xapi-data/` can affect production even if the work was validated in preview first.

## Secret/leak gate

Run a local staged/full diff scan before packaging:

```bash
python3 - <<'PY'
import re, subprocess
text = subprocess.check_output(['git', 'diff', '<previous-release-tag>..HEAD'], text=True, errors='ignore')
patterns = {
    'private_key': r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    'api_key': r'(?<!redacted:)(sk-[A-Za-z0-9]{20,}|xai-[A-Za-z0-9_-]{20,}|DASHSCOPE_API_KEY\s*=\s*[^\s]+|DEEPSEEK_API_KEY\s*=\s*[^\s]+)',
    'bearer_long': r'Bearer\s+(?!\*\*\*)[A-Za-z0-9._-]{30,}',
}
for name, pat in patterns.items():
    hits = re.findall(pat, text)
    print(name, len(hits))
PY
```

Expected result: all counts are `0` except intentional redacted examples in tests/docs.

## Required local tests

Run from the repository root:

```bash
python3 -m py_compile \
  services/xapi-portal/xapi_portal.py \
  services/xapi-v1-wrapper/xapi_v1_wrapper.py \
  services/xapi-data/xapi_data_api.py \
  scripts/build-release-package.py

python3 tests/phase1/test_gateway_core.py
python3 tests/phase0/test_v1_wrapper_regression.py
python3 tests/phase0/test_release_versioning.py
```

If any test fails, do not build a formal release.

## Package gate

Build only with a policy-compliant version:

```bash
python3 scripts/build-release-package.py --version V0.0.X --set-app-version --dist dist
```

Then inspect the generated package manifest:

```bash
tar -tzf dist/nw-api-V0.0.X-linux-amd64.tar.gz | sort | sed -n '1,120p'
tar -xOf dist/nw-api-V0.0.X-linux-amd64.tar.gz nw-api-V0.0.X-linux-amd64/manifest.json | python3 -m json.tool
```

Confirm the package includes only intended production files. Preview-only services, mock data services, preview gateway, temporary reports, and local test scripts should not be included unless intentionally added to the formal package.

## Pre-production smoke gate

Before using the web updater, test the candidate package in a non-production or preview-equivalent environment. Minimum smoke matrix:

- portal `/health`
- admin login
- version status/update card
- key create/view/disable
- valid `/v1/models`
- invalid `/v1/models`
- non-stream `/v1/chat/completions`
- stream `/v1/chat/completions`
- upstream 429/5xx pass-through
- API access log write/read if access logging is enabled

For preview stack latency comparisons, use:

```bash
python3 scripts/phase0_preview_perf.py --host 10.0.1.66 --total 100 --concurrency 30
```

For localhost-only internal preview services, run on the preview host:

```bash
python3 /opt/nw-api-phase0-preview/repo/scripts/phase0_preview_perf.py --host 127.0.0.1 --total 100 --concurrency 30 --include-internal
```

## Backup and rollback gate

Before production update:

- Snapshot/copy the current release directory.
- Save current `APP_VERSION`, service unit files, and environment file paths.
- Confirm the previous release package and checksum are available.
- Confirm rollback command/path is known from `docs/phase0/rollback-runbook.md` or the production runbook.

If smoke fails after update:

1. Stop the affected service(s).
2. Restore the previous release directory or package.
3. Restore service unit/env files if changed.
4. Restart services.
5. Re-run the smoke matrix.

## Stop conditions

Do not proceed with production update if any of these are true:

- No explicit production-update request from the operator.
- Version/tag/package mismatch.
- Secret scan has non-zero unreviewed hits.
- Tests fail.
- Package manifest contains unintended files.
- Pre-production smoke fails.
- Rollback artifact is missing.
- The update includes database migrations without a backup and rollback plan.
