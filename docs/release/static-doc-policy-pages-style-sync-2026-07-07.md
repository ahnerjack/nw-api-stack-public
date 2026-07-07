# NW-API 静态文档/协议页风格统一

时间：2026-07-07
范围：`/privacy`、`/terms`、发布包清单、正式项目 Git checkout

## 问题

用户反馈从官网点入文档/协议类页面时，视觉像“换了一个网站”。

## 定位

检测正式页面：

- `/docs` 已是新风格。
- `/privacy` 和 `/terms` 仍是旧静态页：旧深色霓虹背景、旧小字 `AI API Gateway`、旧布局。
- 仓库原本缺 `services/hermes-portal/privacy.html` 和 `services/hermes-portal/terms.html`，导致正式静态页面不能完整从 Git 复现。

## 修改

新增 Git 源码：

- `services/hermes-portal/privacy.html`
- `services/hermes-portal/terms.html`

修改：

- `scripts/build-release-package.py`

将以下静态页加入发布包：

- `index.html`
- `docs.html`
- `privacy.html`
- `terms.html`

## 新页面风格

统一为 `/docs` 同款：

- 浅蓝灰背景
- 白色圆角卡片
- 蓝靛主按钮
- 统一顶部导航
- 统一页脚
- 统一“进入控制台 / 查看接入文档”动作

## 正式同步

方式：

- 本机 Git 提交后生成 bundle。
- 正式 `/opt/nw-api-stack` 通过 bundle 同步到提交 `43ab183`。
- 从正式 Git 项目安装：
  - `services/hermes-portal/privacy.html` -> `/srv/hermes-portal/privacy.html`
  - `services/hermes-portal/terms.html` -> `/srv/hermes-portal/terms.html`

备份：

`/root/nwapi-backups/static-policy-pages-20260707-141755`

## 验证

正式页面：

- `/privacy`：200，title `隐私政策 · NW-API`
- `/terms`：200，title `服务条款 · NW-API`
- `/docs`：200，title `接入文档 · NW-API`
- `/home`：200，title `NW-API`

hash 一致：

- `services/hermes-portal/privacy.html` = `/srv/hermes-portal/privacy.html`
- `services/hermes-portal/terms.html` = `/srv/hermes-portal/terms.html`

泄漏检查未发现：

- `Sub2API`
- `10.0.1.66`
- `api.example.com`
- `gpt-5.5`
- `V0.0`
- `rc.`
- `version`
- `查看发布`
- `sk-`
- `nwk_`

服务：

- `caddy` active
- `xapi-portal` active
- `xapi-v1-wrapper` active

## 备注

Caddy 日志仍偶发 `invalid byte in chunk length`，但 `/privacy` 和 `/terms` 是静态文件服务，不走 reverse_proxy；本次访问静态页后未持续新增同类错误。该问题应单独针对 `/v1` 或其他反代路径定位，不属于本次静态页面风格问题。
