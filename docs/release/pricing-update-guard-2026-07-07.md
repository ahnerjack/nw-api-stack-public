# NW-API 价格页编辑权限修复

时间：2026-07-07
范围：正式站 `https://of.ahner.cn` 与源码 `public-sanitized`

## 用户问题

“为什么价格页面谁都能编辑”

## 根因

实测游客直接 `POST /pricing/update` 不能修改价格。正式 Caddy 在修前对 `/pricing/update` 返回静态 404，公网游客没有写入能力。

真正问题是管理界面设计和敏感操作保护不足：

- 登录后的 `/pricing` 页面在管理员视角直接显示“编辑价格”表单，容易看起来像普通价格页也能编辑。
- `/pricing/update` 只判断 `u['role']=='admin'`，未纳入敏感操作集合。
- 编辑价格表单缺少 CSRF、管理员密码、操作备注。
- 正式 Caddy 只代理 `/pricing` 与 `/pricing/`，没有代理 `/pricing/update`，导致管理员提交被 Caddy 静态 404 拦截；虽然更安全，但功能不可用且路由不一致。

## 修复

源码修复：

- 将 `/pricing/update` 加入 `sensitive_paths`。
- 管理员价格编辑表单加入 `sensitive_fields(u, '价格修改备注')`。
- `price_rows()` 对 `model_price_sync` 缺表做兼容，避免新库价格页 500。

正式热修：

- `/etc/caddy/Caddyfile` 中价格路由改为 `handle /pricing*` 代理到 portal。
- 已 `caddy validate` 并 reload。

## 验证

本地验证：

- py_compile 通过
- 回归 44/44 通过
- secret scan：0 real keys
- 游客 `POST /pricing/update`：跳登录，不写库
- 普通用户 `POST /pricing/update`：403，不写库
- 管理员页面：包含 CSRF、管理员密码、操作备注
- 管理员缺少二次确认提交：403，不写库

正式验证：

使用临时普通用户和临时管理员，验证后已删除：

- 游客 `POST /pricing/update`：跳登录
- 普通用户登录后 `POST /pricing/update`：403
- 临时管理员登录后 `/pricing`：表单含 CSRF / admin_password / admin_note
- 临时管理员缺少二次确认 `POST /pricing/update`：403
- `model_prices` 未产生测试脏数据
- `xapi-portal` active
- `xapi-v1-wrapper` active
- `caddy` active

正式备份：

- Portal 代码和 DB：`/root/nwapi-backups/pricing-guard-20260707-113703`
- Caddyfile：`/root/nwapi-backups/pricing-caddy-20260707-113825`

## 结论

不是游客真的能改价；问题是管理员价格页缺少敏感操作防护，且路由设计混乱。现在价格修改已改为管理员专用 + CSRF + 管理员密码 + 操作备注，普通用户和游客均不能修改。
