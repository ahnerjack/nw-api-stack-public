# NW-API 正式首页 `/home` 修复

时间：2026-07-07
范围：正式站 `https://of.ahner.cn/home`，静态首页 `/srv/hermes-portal/index.html`

## 定位

正式 `/home` 由 Caddy 静态文件服务：

- `/home*` rewrite 到 `/index.html`
- 文件：`/srv/hermes-portal/index.html`
- 仓库源文件：`services/hermes-portal/index.html`

## 问题

首页存在过期/误导文案：

- `<title>` 为 `AI API Gateway · NW-API`，不符合当前正式品牌标题只显示 `NW-API` 的口径。
- curl 示例仍使用 `https://api.example.com/v1/chat/completions`。
- 文案包含“人工充值审核”和“订单记录”，与当前正式站 admin-led/影子账本口径不一致。

未发现：

- `Sub2API` / `sub2api` 泄漏
- `10.0.1.66` 泄漏
- `/pricing/update` 泄漏
- `编辑价格` 泄漏

## 修复

- title 改为 `NW-API`
- 品牌小字改为 `OpenAI-compatible API`
- curl 示例改为 `https://of.ahner.cn/v1/chat/completions`
- 首页主文案改为“统一接入、Key 管理、用量统计、模型价格和运营风控”
- 用量卡片改为“Token 和影子账本追踪”
- 控制卡片移除“订单”
- CTA 改为直接使用 `https://of.ahner.cn/v1`

## 正式部署

备份：

`/root/nwapi-backups/home-static-20260707-114636`

部署：

- 更新 `/srv/hermes-portal/index.html`
- `caddy validate` 通过
- `systemctl reload caddy`

## 验证

`https://of.ahner.cn/home`：

- HTTP 200
- title：`NW-API`
- `https://of.ahner.cn/v1/chat/completions`：1
- `api.example.com`：0
- `人工充值`：0
- `Sub2API`：0
- `10.0.1.66`：0
- `pricing/update`：0
- `编辑价格`：0

`https://of.ahner.cn/`：同样验证通过。

服务状态：

- `caddy` active
- `xapi-portal` active
- `xapi-v1-wrapper` active
