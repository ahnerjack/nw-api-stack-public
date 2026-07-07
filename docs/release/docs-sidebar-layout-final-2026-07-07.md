# NW-API `/docs` 左侧目录文档布局上线

时间：2026-07-07
范围：`services/hermes-portal/docs.html` + 正式 `/docs`

## 需求

用户要求 `/docs` 按 `/risk` 的感觉改成：左边是菜单栏，右边是文档。

## 修改

重写 `services/hermes-portal/docs.html`：

- 两栏布局：左侧固定目录，右侧正文。
- 左侧包含：
  - 站点：首页、价格、模型、风控
  - 文档目录：接入概览、快速开始、鉴权、SDK 示例、模型与权限、错误与排查、安全建议
  - 账号：控制台、隐私政策、服务条款
- 右侧包含完整接入文档。
- 移动端改为单栏，左侧不固定。

## 验证

源码：

- HTML 可解析。
- 发布包包含 `services/hermes-portal/docs.html`。
- 未发现 `Sub2API`、`10.0.1.66`、`api.example.com`、`gpt-5.5`、`V0.0`、`rc.`、`version`、`查看发布`、`sk-`、`nwk_`。

正式：

- `/docs`：200，title `接入文档 · NW-API`
- 页面含 `layout`、`side`、`接入概览`、`SDK 示例`
- 浏览器可见左侧目录 + 右侧文档正文
- `caddy`、`xapi-portal`、`xapi-v1-wrapper` active
- 部署后 Caddy 近 3 分钟无新异常日志

## 正式同步

方式：

- Git 提交后生成 bundle。
- 正式 `/opt/nw-api-stack` 通过 bundle 同步。
- 从正式 Git 项目安装 `services/hermes-portal/docs.html` 到 `/srv/hermes-portal/docs.html`。

备份：

`/root/nwapi-backups/docs-sidebar-20260707-142415`

## Git

功能提交：`0c20c8b Redesign docs page with sidebar navigation`
