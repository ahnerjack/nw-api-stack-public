# NW-API 首页视觉优化

时间：2026-07-07
范围：源码 `services/hermes-portal/index.html` + 正式静态首页 `https://of.ahner.cn/home`

## 目标

用户反馈首页“颜色和页面都不好看”，要求改 Git 源码。

## 修改

重写首页静态源码，保留原有路由和核心入口，优化：

- 配色：从霓虹紫青改为克制深蓝 + 蓝靛强调色。
- 背景：取消深浅硬切，改为柔和渐变过渡。
- Hero：标题改为“一个稳定入口，接入多模型能力。”
- 顶部标签：改为“统一 API 网关 · 多模型接入”。
- 右侧展示：从 curl 终端改为平台能力概览卡，避免公开暴露真实 Base URL / 模型名。
- 卡片：白底、细边框、轻阴影，统一中文标签“网关 / 计费 / 管控”。
- CTA：改为“进入控制台创建 Key”，Base URL 登录后查看。
- 移动端：隐藏低频导航和右侧能力卡，减少首屏拥挤。

## 安全/泄漏检查

源码与正式页均确认不包含：

- `OpenAI-compatible`
- `gpt-5.5`
- `of.ahner.cn/v1`
- `api.example.com`
- `影子账本`
- `Sub2API`
- `10.0.1.66`
- `V0.0`
- `rc.`
- `version`
- `查看发布`

## 正式部署

备份：

`/root/nwapi-backups/home-visual-20260707-121908`

部署：

- 更新 `/srv/hermes-portal/index.html`
- `caddy validate` 通过
- `systemctl reload caddy`

## 验证

正式 URL：

- `https://of.ahner.cn/home`：HTTP 200，title `NW-API`
- `https://of.ahner.cn/`：HTTP 200，title `NW-API`

服务：

- `caddy` active
- `xapi-portal` active
- `xapi-v1-wrapper` active

浏览器视觉检查：

- 颜色克制
- 布局完整
- 无明显溢出/错位
- 无低级霓虹感
- 无版本号
