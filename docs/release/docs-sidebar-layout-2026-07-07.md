# NW-API `/docs` 左侧目录文档布局

时间：2026-07-07
范围：`services/hermes-portal/docs.html`

## 需求

用户要求 `/docs` 按 `/risk` 的使用体验来做：左边是菜单栏，右边是文档。

## 修改

重写 `services/hermes-portal/docs.html`：

- 改为两栏布局：左侧固定目录菜单，右侧文档内容。
- 左侧包含：站点导航、文档目录、账号入口。
- 右侧包含：
  - 接入概览
  - 快速开始
  - 鉴权
  - SDK 示例
  - 模型与权限
  - 错误与排查
  - 安全建议
- 保留 NW-API 品牌、浅蓝灰背景、白卡片和控制台入口。
- 移动端自动改为单栏，左侧目录不固定。

## 检查

- HTML 可解析。
- 发布包包含 `services/hermes-portal/docs.html`。
- 未发现 `Sub2API`、`10.0.1.66`、`api.example.com`、`gpt-5.5`、`V0.0`、`rc.`、`version`、`查看发布`、`sk-`、`nwk_`。
