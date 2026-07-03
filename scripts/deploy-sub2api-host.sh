#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
install -d /opt/xapi-data /usr/local/sbin
install -m 0644 services/xapi-data/xapi_data_api.py /opt/xapi-data/xapi_data_api.py
python3 -m py_compile /opt/xapi-data/xapi_data_api.py
systemctl restart xapi-data
systemctl is-active --quiet xapi-data
if [ -f scripts/check-sub2api-aliyun-tunnel.sh ]; then
  install -m 0755 scripts/check-sub2api-aliyun-tunnel.sh /usr/local/sbin/check-sub2api-aliyun-tunnel.sh
fi
if [ -f systemd/hermes-sub2api-aliyun-tunnel-watchdog.service ] && [ -f systemd/hermes-sub2api-aliyun-tunnel-watchdog.timer ]; then
  install -m 0644 systemd/hermes-sub2api-aliyun-tunnel-watchdog.service /etc/systemd/system/hermes-sub2api-aliyun-tunnel-watchdog.service
  install -m 0644 systemd/hermes-sub2api-aliyun-tunnel-watchdog.timer /etc/systemd/system/hermes-sub2api-aliyun-tunnel-watchdog.timer
  systemctl daemon-reload
  systemctl enable --now hermes-sub2api-aliyun-tunnel-watchdog.timer
fi
