# NW-API 登录/退出链路修复

时间：2026-07-07
范围：源码 `public-sanitized` + 正式站 `https://of.ahner.cn`

## 用户反馈

- 一打开控制台就显示登录。
- 点击退出显示 404。
- 退出后点击其他选项仍是登录账号。
- 要求整体检查测试，并改 Git 源码。

## 复现结果

修复前正式站：

- 未登录 `/dashboard` -> `/login`：正常。
- `/logout` -> 404：异常。
- 登录后访问 `/login` 仍渲染登录页：异常，容易误判“控制台显示登录”。

## 根因

1. 正式 Caddy 没有代理 `/logout*` 到 `xapi-portal`。
   - 应用源码本身有 `/logout` 清 session + 清 cookie 逻辑。
   - 但请求被 Caddy 静态/兜底 404 截走，没进入应用。
   - 因此 server-side session 没删，cookie 没清，点其他菜单仍保持登录态。

2. `/login` GET 没有检查当前 session。
   - 已登录用户点击首页/导航里的“控制台”进入 `/login` 时仍显示登录表单。
   - 应改为已登录时重定向 `/dashboard`。

3. 发布包缺少正式 Caddy 模板。
   - 之前路由修复只能热修 `/etc/caddy/Caddyfile`。
   - 后续发布可能覆盖丢失。

## 源码修复

### `services/xapi-portal/xapi_portal.py`

- 在处理 `/login`、`/register`、`/forgot` 前先读取 `current(self)`。
- 如果已有有效 session：
  - `/login` -> `/dashboard`
  - `/register` -> `/dashboard`
  - `/forgot` -> `/dashboard`
- `/logout` 保持：删除 `SESS[sid]`、清 `sid` cookie、跳 `/home`。

### `systemd/Caddyfile.current`

新增并纳入 Git：

```caddy
handle /logout* {
    reverse_proxy 127.0.0.1:18180
}
```

### `scripts/build-release-package.py`

- 发布包加入 `systemd/Caddyfile.current`。
- 保证后续正式发布会安装正确 Caddy 路由。

### `tests/phase0/test_portal_auth_regression.py`

新增回归测试：

- 登录成功设置 sid。
- 已登录访问 `/login` 跳 `/dashboard`。
- `/logout` 清 server session 并跳 `/home`。
- 退出后访问 `/keys` 跳 `/login`。

## 验证

本地：

- `python3 -m py_compile services/xapi-portal/xapi_portal.py tests/phase0/test_portal_auth_regression.py scripts/build-release-package.py` 通过。
- `tests.phase0.test_portal_auth_regression`：1/1 通过。
- `tests.phase0.test_v1_wrapper_regression tests.phase0.test_release_versioning tests.phase1.test_gateway_core`：44/44 通过。
- 发布包检查包含：
  - `systemd/Caddyfile.current`
  - `services/xapi-portal/xapi_portal.py`
  - `scripts/deploy-aliyun.sh`

正式：

备份：

`/root/nwapi-backups/auth-flow-20260707-123526`

部署：

- `/opt/xapi-portal/xapi_portal.py`
- `/etc/caddy/Caddyfile`
- `caddy validate` 通过。
- `xapi-portal` 重启。
- `caddy` reload。

正式链路验证：

- `/login` 未登录：200。
- 登录 POST：302 `/dashboard`。
- 登录后访问 `/login`：302 `/dashboard`。
- 登录后访问 `/keys`：200。
- `/logout`：302 `/home`。
- 退出后 cookie 已清空。
- 退出后访问 `/keys`：302 `/login`。

服务状态：

- `xapi-portal` active
- `caddy` active
- `xapi-v1-wrapper` active
