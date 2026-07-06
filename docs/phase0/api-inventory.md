# API / 路径清单

基线仓库：`/Users/ahner/projects/nw-api-stack-public`
当前分支：`public-sanitized`
当前公开版本：`V0.0.1.1`

## 1. Public / Portal 路径

来源：`services/xapi-portal/xapi_portal.py:H.do_GET`

| 路径 | 认证 | 说明 |
|---|---|---|
| `/` `/home` `/home/` | 否 | 公开首页 |
| `/login` | 否 | 登录页 |
| `/register` | 否 | 注册页 |
| `/forgot` | 否 | 找回密码 |
| `/plans` | 未登录公开 / 登录后台 | 套餐页 |
| `/risk` | 未登录公开 / 管理后台 | 风控说明或风控管理 |
| `/models` `/models/` | 未登录公开 / 登录后台 | 模型目录 |
| `/pricing` `/pricing/` | 未登录公开 / 登录后台 | 价格页 |
| `/docs` | 是 | 接入文档 |
| `/dashboard` | 是 | 控制台总览 |
| `/onboarding` | 是 | 新手引导 |
| `/profile` | 是 | 个人资料 |
| `/notifications` | 是 | 通知 |
| `/keys` | 是 | API Key 管理 |
| `/keys/view` | 是 | 查看完整 Key |
| `/usage` | 是 | 用量 |
| `/billing` | 是，重定向 | 当前重定向到 dashboard |
| `/users-admin` | 管理员 | 用户管理 |
| `/admin-console` | 管理员 | 管理控制台 |
| `/admin-usage` | 管理员 | 账号用量统计 |
| `/admin-update` | 管理员 | 在线更新 |
| `/version-status` | 登录 | 版本状态 JSON/HTML 片段 |
| `/user-detail` | 管理员 | 用户详情 |
| `/api-logs` | 管理员 | API 访问日志 |
| `/rollback` | 管理员 | 回滚记录 |
| `/mail-logs` | 管理员 | 邮件日志 |
| `/announcements` | 管理员 | 公告管理 |
| `/healthz` | 登录 | 健康检查页 |
| `/changelog` | 登录 | 更新日志 |
| `/export.csv` | 管理员 | CSV 导出 |
| `/health` | 否 | 简单健康检查，返回 `ok` |

## 2. Portal POST 路径

来源：`services/xapi-portal/xapi_portal.py:H.do_POST`

| 路径 | 认证 | 敏感确认 | 说明 |
|---|---|---|---|
| `/login` | 否 | 否 | 登录 |
| `/register` | 否 | 否 | 注册 |
| `/send-code` | 否 | 否 | 邮箱验证码 |
| `/forgot/send` `/forgot/reset` | 否 | 否 | 找回密码 |
| `/profile/password` | 是 | CSRF | 修改密码 |
| `/notifications/read` `/notifications/read-all` | 是 | 否 | 通知已读 |
| `/admin-update/apply` | 管理员 | CSRF | 执行在线更新 |
| `/admin-update/restart.json` `/admin-update/rollback.json` | 管理员 | 取决于实现 | 更新辅助操作 |
| `/announcements/update` | 管理员 | 否 | 公告 |
| `/notifications/send` | 管理员 | 是 | 发送通知 |
| `/risk/update` | 管理员 | 否 | 风控规则 |
| `/users-admin/payment-method` | 管理员 | 否 | 支付方式 |
| `/plans/update` | 管理员 | 否 | 套餐 |
| `/users-admin/plan` | 管理员 | 是 | 分配套餐 |
| `/pricing/update` | 管理员 | 否 | 价格 |
| `/users-admin/models` | 管理员 | 是 | 模型权限 |
| `/keys/create` `/keys/update` `/keys/rotate` `/keys/disable` `/keys/delete` | 是 | 部分无二次确认 | Key 管理 |
| `/users-admin/update` `/users-admin/delete` | 管理员 | 是 | 用户更新/删除 |

## 3. xapi-data API

来源：`services/xapi-data/xapi_data_api.py`
监听：`127.0.0.1:18181`

GET：
- `/xapi-data/health`
- `/xapi-data/dashboard?uid=...`
- `/xapi-data/summary?uid=...`
- `/xapi-data/keys?uid=...`
- `/xapi-data/usage?uid=...`
- `/xapi-data/stats?uid=...&start=...&end=...`
- `/xapi-data/models`
- `/xapi-data/pricing`

POST：
- `/xapi-data/users`
- `/xapi-data/users/auth`
- `/xapi-data/users/password`
- `/xapi-data/keys/verify`
- `/xapi-data/keys`
- `/xapi-data/keys/view`
- `/xapi-data/keys/rotate`
- `/xapi-data/keys/update`
- `/xapi-data/keys/disable`
- `/xapi-data/keys/delete`
- `/xapi-data/users/balance`
- `/xapi-data/users/update`
- `/xapi-data/users/delete`

## 4. /v1 wrapper 行为

来源：`services/xapi-v1-wrapper/xapi_v1_wrapper.py`
监听：默认 `127.0.0.1:18182`
上游：默认 `http://127.0.0.1:18066`
数据桥：默认 `http://127.0.0.1:18066/xapi-data`，运行环境可覆盖为独立 xapi-data。

| 路径 | 方法 | 行为 |
|---|---|---|
| `/v1/models` | GET | wrapper 自己合成 OpenAI-compatible model list，只展示该 portal 用户允许模型 |
| `/v1/*` | GET/POST/HEAD | 校验 Key、IP 风控、模型白名单后透传上游 |
| 任意路径 | OPTIONS | 返回 CORS 204 |

注意：wrapper 不是只代理 chat，它会代理任意 `/v1/*` 路径；当前阶段必须记录现状，不能贸然收窄。
