# NW-API Stack

Open-source template for a white-label AI API console, data bridge, and deployment scripts.

## Components

- `services/xapi-portal/xapi_portal.py` — web console and admin UI.
- `services/xapi-data/xapi_data_api.py` — local data bridge example for a backend API gateway database.
- `services/xapi-data-mock/xapi_data_mock.py` — preview/mock data service.
- `systemd/*.service` — example service units.
- `systemd/Caddyfile.example` — example reverse proxy config.
- `scripts/deploy-*.sh` — deployment helpers.

## Secrets policy

Do not commit databases, real `.env`, service drop-ins containing passwords, API keys, SSH keys, tokens, or generated backups.
Runtime secrets should stay on each server in `/etc/*.env` or systemd drop-ins.

## Configure

Copy `systemd/xapi-portal.env.example` to `/etc/xapi-portal.env` and set real values locally.

```bash
sudo install -m 600 systemd/xapi-portal.env.example /etc/xapi-portal.env
sudo editor /etc/xapi-portal.env
```

Set your public API base URL with `NW_API_BASE_URL`.


## Release notes

- V0.0.002: docs/changelog/V0.0.002.md
