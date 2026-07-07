# NW-API 导航顺序与 Logo 回主页统一

时间：2026-07-07
范围：静态公开页、动态公开页、控制台侧栏 Logo

## 检查结论

发现不一致：

1. 首页右上角顺序为：价格、套餐、风控、文档、模型、隐私、条款、控制台。
2. `/privacy`、`/terms` 顶部顺序同首页旧顺序。
3. 动态公开页 `/pricing`、`/plans`、`/models`、`/risk` 缺少 `模型` 顶部入口。
4. `/docs` 左侧站点菜单缺 `套餐`，顺序和首页不一致。
5. 控制台左侧 Logo 点击指向 `/dashboard`，不是主页。
6. 动态公开页 Logo 小字仍是 `AI API Gateway`，和静态页 `统一 API 网关` 不一致。

## 统一规则

公开导航顺序统一为：

价格 → 套餐 → 模型 → 风控 → 文档 → 隐私 → 条款 → 控制台

`/docs` 左侧站点菜单统一为：

首页 → 价格 → 套餐 → 模型 → 风控 → 文档

Logo：

- 静态公开页 Logo：`/home`
- 动态公开页 Logo：`/home`
- 控制台左侧 Logo：`/home`

## 修改文件

- `services/hermes-portal/index.html`
- `services/hermes-portal/docs.html`
- `services/hermes-portal/privacy.html`
- `services/hermes-portal/terms.html`
- `services/xapi-portal/xapi_portal.py`

## 验证

- 静态 HTML 可解析。
- `xapi_portal.py` 编译通过。
- 回归测试：45/45 通过。
- 发布包构建成功，包含静态公开页。

