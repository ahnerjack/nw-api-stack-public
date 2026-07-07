# NW-API 正式站更新：V0.0.3-rc.2

时间：2026-07-07
目标：`https://of.ahner.cn`
范围：正式站 RC 更新；GitHub Release 已发布。

## Release

GitHub Release：

`https://github.com/ahnerjack/nw-api-stack-public/releases/tag/V0.0.3-rc.2`

Asset：

`nw-api-V0.0.3-rc.2-linux-amd64.tar.gz`

SHA256：

`e7e229d2d01250f75b554c7e45fb7e53250a0a3820b30af34757384552def8a9`

说明：正式发布前发现 `deploy-aliyun.sh` 漏装 `provider_adapter.py` 与 `usage_wallet.py`，已修复并重新打包/发布 RC2。

## 正式更新前状态

- `xapi-portal` active
- `xapi-v1-wrapper` active
- `caddy` active
- `xapi-data` inactive
- APP_VERSION：`V0.0.2`
- `/v1` Caddy 路由：`127.0.0.1:18182`

## 备份

正式更新前备份目录：

`/root/nwapi-backups/20260707-112159`

包含：

- `/opt/xapi-portal`
- `/opt/xapi-v1-wrapper`
- systemd unit/drop-in
- `/etc/xapi-portal.env`

注意：服务器缺少 `sqlite3` CLI，`.backup` 未执行；但 `/opt/xapi-portal` 目录整体已备份，包含 SQLite DB 文件。

## 正式环境配置

写入 `/etc/xapi-portal.env`：

- `XAPI_UPSTREAM_API_KEY=***`
- `XAPI_UPSTREAM_MAX_CONCURRENCY=12`
- `XAPI_UPSTREAM_MAX_CONCURRENCY_PER_KEY=10`
- `NW_API_BASE_URL=https://of.ahner.cn/v1`
- `NW_API_UPDATE_REPO=ahnerjack/nw-api-stack-public`
- `NW_API_UPDATE_ASSET_REPO=ahnerjack/nw-api-stack-public`

## 部署结果

部署后：

- APP_VERSION：`V0.0.3-rc.2`
- `xapi-portal` active
- `xapi-v1-wrapper` active
- `caddy` active
- helper modules py_compile 通过
- warning 日志：无

## 验证

公共入口：

- `/login`：HTTP 200
- `/v1/models` with legacy sk：HTTP 200

真实上游 legacy sk 路径：

- 3 并发：3/3 成功，P50 2379ms
- 10 并发：10/10 成功，P50 2302ms，P95 3653ms

正式 nwk 自有 Key 路径：

首次测试前 wrapper 未重启加载 `/etc/xapi-portal.env`，`nwk_` 返回 401。重启 `xapi-v1-wrapper` 后恢复：

- `/v1/models` with `nwk_`：HTTP 200
- 1 并发 chat：1/1 成功
- 5 并发 chat：5/5 成功
- 10 并发 chat：9/10 成功，1 个 `NW_UPSTREAM_BUSY`

DB 核验：

- `nw_usage_events`：15 条
- `nw_wallet_ledger`：15 条
- 成功项均为：`200 / billed_shadow / reported`
- 429：`NW_UPSTREAM_BUSY:key`，未写入 usage/wallet

正式测试 `nwk_` Key 已禁用：

- `disabled_test_keys 1`

## 当前状态

- 正式站已更新到 `V0.0.3-rc.2`
- GitHub Release 已发布
- `/v1` 正常
- 自有 Key 路径可用
- shadow usage/wallet 正常
- 并发保护生效
- 测试 Key 已禁用

## 后续建议

- 安装 `sqlite3` CLI 或改备份脚本使用 Python backup API，避免下次 `.backup` 缺失。
- 正式站可保留 `V0.0.3-rc.2` 观察一段时间，再决定是否发布正式 `V0.0.3`。
- 若想减少 10 并发下偶发 `NW_UPSTREAM_BUSY`，可把单 Key 阈值从 10 调到 12；但当前设置更保守。
