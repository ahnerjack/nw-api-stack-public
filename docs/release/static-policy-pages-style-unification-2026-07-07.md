# NW-API 文档/协议页面风格统一

时间：2026-07-07
范围：`/privacy`、`/terms` 静态页 + 发布包清单

## 问题

用户反馈从当前页面点进文档/协议类页面时，视觉像“换了一个网站”。

排查发现：

- `/docs` 已改为新风格。
- `/privacy` 和 `/terms` 仍是旧静态页：旧深色霓虹背景、旧品牌小字 `AI API Gateway`。
- 仓库里之前没有 `privacy.html` / `terms.html`，正式页不可从 Git 完整复现。

## 修改

新增：

- `services/hermes-portal/privacy.html`
- `services/hermes-portal/terms.html`

并修改：

- `scripts/build-release-package.py`

将以下静态页全部纳入发布包：

- `index.html`
- `docs.html`
- `privacy.html`
- `terms.html`

## 新风格

- 与 `/home` 和 `/docs` 保持同一套浅蓝灰背景、白色圆角卡片、蓝靛主按钮、统一顶部导航。
- 隐私页重写为：账号信息、用量审计、通知、安全、保留、联系。
- 条款页重写为：凭证、用途、额度、稳定性、审计、规则变更。

## 检查

源码检查通过：

- HTML parser 可解析。
- 发布包包含 `privacy.html` 和 `terms.html`。
- 未发现：`Sub2API`、`10.0.1.66`、`api.example.com`、`gpt-5.5`、`V0.0`、`rc.`、`version`、`查看发布`、`sk-`、`nwk_`。
