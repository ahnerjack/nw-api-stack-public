# NW-API Stack

Private source backup and deployment repo for NW-API portal, xapi-data bridge, and dh navigation page.

## Components

- `services/xapi-portal/xapi_portal.py` — public white-label NW-API portal on Alibaba Cloud.
- `services/xapi-data/xapi_data_api.py` — local data bridge to Sub2API/Postgres/Redis.
- `services/dh-nav/index.html` — `dh.ahner.cn` navigation page.
- `systemd/*.service` — non-secret service unit templates/current units.
- `scripts/deploy-*.sh` — pull-from-git deployment helpers.

## Secrets policy

Do not commit databases, real `.env`, service drop-ins containing passwords, API keys, SSH keys, tokens, or generated backups.
Runtime secrets stay on the server in systemd drop-ins or `/etc/*.env` only.

## Deploy

On Alibaba Cloud:

```bash
cd /opt/nw-api-stack && git pull
sudo ./scripts/deploy-aliyun.sh
```

On Sub2API host:

```bash
cd /opt/nw-api-stack && git pull
sudo ./scripts/deploy-sub2api-host.sh
```
