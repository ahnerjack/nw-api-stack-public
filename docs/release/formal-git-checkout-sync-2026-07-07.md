# NW-API 正式项目 Git checkout 同步

时间：2026-07-07
范围：正式服务器 `/opt/nw-api-stack`

## 目标

正式运行文件已经和当前 Git 源码一致，但正式项目 Git checkout 停在旧提交 `94a58c0`，存在后续部署覆盖风险。

本次只同步 Git checkout，不部署、不重启、不修改运行文件。

## 执行方式

由于正式服务器访问 GitHub 不稳定，采用本机 Git bundle：

- 本机分支：`public-sanitized`
- 目标提交：`9b5d03c`
- bundle：`nw-api-public-sanitized-9b5d03c.bundle`
- SHA256：`5e313184441e8f0e83570473ebc1e8877a827c6bcfe7558552f381e2cc98b648`

正式服务器：

- bundle 校验通过
- `git bundle verify` 通过
- `git fetch /tmp/nw-api-public-sanitized.bundle public-sanitized:refs/remotes/bundle/public-sanitized`
- `git reset --hard refs/remotes/bundle/public-sanitized`

## 备份

`/root/nwapi-backups/git-checkout-sync-20260707-134051`

包含：

- `before-head.txt`
- `before-status.txt`
- `before-log.txt`
- `nw-api-stack-checkout-no-objects.tar.gz`

## 同步前

- 正式分支：`public-sanitized`
- 正式 HEAD：`94a58c0`
- 工作区：clean

## 同步后

- 正式分支：`public-sanitized`
- 正式 HEAD：`9b5d03c`
- 工作区：clean

## 运行文件一致性

以下源码与正式运行文件 hash 一致：

- `services/xapi-portal/xapi_portal.py` = `/opt/xapi-portal/xapi_portal.py`
- `services/xapi-v1-wrapper/xapi_v1_wrapper.py` = `/opt/xapi-v1-wrapper/xapi_v1_wrapper.py`
- `services/xapi-v1-wrapper/gateway_core.py` = `/opt/xapi-v1-wrapper/gateway_core.py`
- `services/hermes-portal/index.html` = `/srv/hermes-portal/index.html`
- `services/hermes-portal/docs.html` = `/srv/hermes-portal/docs.html`
- `systemd/Caddyfile.current` = `/etc/caddy/Caddyfile`

## 服务状态

未执行重启或 reload。

验证时服务均 active：

- `xapi-portal`
- `xapi-v1-wrapper`
- `caddy`

## HTTP 验证

- `/home`：200，title `NW-API`
- `/docs`：200，title `接入文档 · NW-API`
- `/pricing`：200，title `NW-API`
- `/login`：200，title `NW-API`
- `/logout`：跳转 `/home`
- `/v1/models` 无 Key：401 `INVALID_API_KEY`

## 日志

同步后近 5 分钟：

- `xapi-portal` 无新日志异常
- `xapi-v1-wrapper` 无新日志异常
- `caddy` 无新日志异常
