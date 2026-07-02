#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
install -d /opt/nw-api-preview/xapi-portal /opt/nw-api-preview/xapi-data-mock
install -m 0644 services/xapi-portal/xapi_portal.py /opt/nw-api-preview/xapi-portal/xapi_portal.py
install -m 0644 services/xapi-data-mock/xapi_data_mock.py /opt/nw-api-preview/xapi-data-mock/xapi_data_mock.py
python3 -m py_compile /opt/nw-api-preview/xapi-portal/xapi_portal.py /opt/nw-api-preview/xapi-data-mock/xapi_data_mock.py
printf 'Preview files installed. Create your own systemd units from examples before enabling services.\n'
