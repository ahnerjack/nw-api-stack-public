#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
install -d /opt/xapi-data
install -m 0644 services/xapi-data/xapi_data_api.py /opt/xapi-data/xapi_data_api.py
python3 -m py_compile /opt/xapi-data/xapi_data_api.py
systemctl restart xapi-data
systemctl is-active --quiet xapi-data
