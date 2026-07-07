# NW-API 导航顺序与 Logo 回主页最终验证

时间：2026-07-07

## 已统一

公开导航统一为：

价格 → 套餐 → 模型 → 风控 → 文档 → 隐私 → 条款 → 控制台

覆盖页面：

- `/home`
- `/privacy`
- `/terms`
- `/pricing`
- `/models`
- `/plans`
- `/risk`

`/docs` 左侧菜单统一为：

首页 → 价格 → 套餐 → 模型 → 风控 → 文档 → 隐私政策 → 服务条款 → 控制台

Logo 回主页：

- 静态公开页 Logo 指向 `/home`
- 动态公开页 Logo 指向 `/home`
- 控制台左侧 Logo 指向 `/home`
- 浏览器实测在 `/docs` 点击 Logo 后进入 `/home`

## 首页右上角调整

原问题：不同页面有的缺 `模型`，有的 `模型` 在 `文档` 后。

调整后：首页右上角保留并统一：

价格、套餐、模型、风控、文档、隐私、条款、控制台

理由：

- `模型` 是价格/接入前高频入口，应放在 `风控/文档` 前。
- `控制台` 保持最后，作为主 CTA。
- `隐私/条款` 低频但公开合规入口，放在控制台前。

## 修改文件

- `services/hermes-portal/index.html`
- `services/hermes-portal/docs.html`
- `services/hermes-portal/privacy.html`
- `services/hermes-portal/terms.html`
- `services/xapi-portal/xapi_portal.py`

## 验证

- 静态 HTML 可解析。
- `xapi_portal.py` 编译通过。
- 回归测试 45/45 通过。
- 发布包构建成功。
- 正式项目 Git：`7976a0d`
- 正式运行文件与正式 Git 源码 hash 一致。
- 服务 active：`caddy`、`xapi-portal`、`xapi-v1-wrapper`

## 注意

Caddy 仍偶发 `invalid byte in chunk length`，不是本轮静态导航 HTML 修改造成；需要另开一次针对 `/v1`/反代流式响应的排查。
