# NW-API `/docs` 文档页风格统一

时间：2026-07-07
范围：源码 `services/hermes-portal/docs.html` + 正式页 `https://of.ahner.cn/docs`

## 问题

`/docs` 页面仍是旧静态文档页，采用霓虹深色大背景和旧文案，和已优化的 `/home` 克制深蓝 + 白卡片风格不一致。

## 定位

正式 Caddy：

- `/docs` rewrite 到 `/docs.html`
- `/docs/` rewrite 到 `/docs.html`
- 静态目录：`/srv/hermes-portal`

仓库之前没有 `services/hermes-portal/docs.html`，导致正式文档页不是可复现的 Git 源码。

## 修改

新增源码：

`services/hermes-portal/docs.html`

重做为和首页一致的设计语言：

- 浅蓝灰背景
- 白色圆角卡片
- 克制深蓝 / 蓝靛主按钮
- 同款顶部导航与品牌区域
- 深蓝代码块
- 三步接入说明
- Python / Node.js SDK 示例
- 安全建议与排查顺序
- 底部 CTA 与页脚

## 安全与泄漏检查

正式页和源码均确认不包含：

- `Sub2API`
- `sub2api`
- `10.0.1.66`
- `api.example.com`
- `gpt-5.5`
- `V0.0`
- `rc.`
- `version`
- `查看发布`
- `sk-`

说明：页面使用 `YOUR_API_KEY` 占位，不展示真实 Key 前缀。

## 正式部署

备份：

`/root/nwapi-backups/docs-style-20260707-125917`

部署：

- 写入 `/srv/hermes-portal/docs.html`
- `caddy validate` 通过
- `systemctl reload caddy`

## 验证

HTTP：

- `https://of.ahner.cn/docs`：200，title `接入文档 · NW-API`
- `https://of.ahner.cn/docs/`：200，title `接入文档 · NW-API`

视觉：

- 与 `/home` 的克制深蓝 + 白卡片风格一致
- 无旧霓虹感
- 无明显错位
- 无版本号残留
- 页面内容完整

服务：

- `caddy` active
- `xapi-portal` active
- `xapi-v1-wrapper` active
