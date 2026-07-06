# NW-API 阶段 0 真实预览环境报告（10.0.1.66:9088）

日期：2026-07-06
预览入口：`http://10.0.1.66:9088/`
后台入口：`http://10.0.1.66:9088/nv-api/`
状态：已部署并通过多轮测试

## 1. 部署目标

阶段 0 预览环境用于在不影响正式站的前提下验证：

- `/v1` wrapper 行为保护层。
- `X-Request-Id` 生成、透传和日志记录。
- 后台页面在独立端口的可访问性。
- 预览环境与生产数据的隔离。
- 后续阶段 1 Gateway Core 改造前的真实运行基线。

本环境不作为正式服务，不绑定正式域名，不触发正式更新。

## 2. 服务与端口

| 服务 | systemd unit | 绑定地址 | 端口 | 用途 |
|---|---|---:|---:|---|
| 预览入口 | `nw-api-phase0-preview.service` | `0.0.0.0` | `9088` | 统一入口，代理 `/nv-api/` 和 `/v1` |
| 预览 Portal | `xapi-portal-phase0-preview.service` | `127.0.0.1` | `19080` | 后台页面 |
| 预览数据 mock | `xapi-data-phase0-preview.service` | `127.0.0.1` | `19081` | 隔离数据服务 |
| 预览 wrapper | `xapi-v1-wrapper-phase0-preview.service` | `127.0.0.1` | `19082` | `/v1` 策略层 |

生产服务端口仍保持原状，预览端口不与生产端口冲突。

## 3. 数据隔离

预览数据目录：

`/opt/nw-api-phase0-preview/state/`

关键文件：

- `/opt/nw-api-phase0-preview/state/xapi_data_mock.db`
- `/opt/nw-api-phase0-preview/state/xapi_portal.db`
- `/opt/nw-api-phase0-preview/logs/update.log`

已确认：

- `XAPI_DATA_BASE=http://127.0.0.1:19081/xapi-data`
- 预览用户、Key、余额、用量都走 mock SQLite。
- 不连接生产 `xapi-data.service` 的 18181。
- 不直接写生产 Sub2API Postgres/Redis。

## 4. 在线更新防护

预览 Portal 设置：

`NW_API_UPDATE_MODE=disabled`

代码层也增加防护：

- `update_state()` 在 disabled 模式下直接返回禁用状态。
- `/admin-update/apply` 在 disabled 模式下返回 403。
- 避免预览后台误触发正式部署脚本。

## 5. 多轮功能测试

### 本地 wrapper 回归

运行 5 轮，每轮 10 项：

| 项目 | 结果 |
|---|---:|
| 总轮次 | 5 |
| 总用例 | 50 |
| 通过 | 50 |
| 失败 | 0 |

覆盖：

- `/v1/models`
- 非流式 chat
- 流式 chat
- 无效 key
- 模型无权限
- 上游 429
- `HEAD`
- `OPTIONS`
- access log
- `X-Request-Id`

### 真实预览环境 10 轮

每轮覆盖：

- `/`
- `/nv-api/`
- 有效预览 key `/v1/models`
- 无效 key `/v1/models`
- 无效 key `/v1/chat/completions`
- `X-Request-Id`

结果：

| 项目 | 结果 |
|---|---:|
| 总轮次 | 10 |
| 总检查项 | 50 |
| 通过 | 50 |
| 失败 | 0 |

### 并发测试

| 场景 | 并发/请求数 | 结果 |
|---|---:|---|
| 无效 key `/v1/models` | 30 请求 | 30/30 正确返回 401 |

## 6. 性能基线

测试入口：`http://10.0.1.66:9088`

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 18.39 | 18.44 | 21.94 | 22.78 |
| 后台 `/nv-api/` | 30 | 200 x30 | 22.12 | 21.32 | 27.76 | 35.03 |
| 无效 key `/v1/models` | 30 | 401 x30 | 25.43 | 24.76 | 32.02 | 32.45 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 24.60 | 23.59 | 30.07 | 37.62 |
| 并发无效 key workers=10 | 30 | 401 x30 | 52.42 | 40.83 | 112.62 | 118.05 |
| 并发无效 key workers=30 | 60 | 401 x60 | 112.52 | 63.18 | 279.05 | 395.82 |
| 并发首页 workers=30 | 60 | 200 x60 | 69.73 | 30.00 | 156.84 | 159.76 |

结论：

- 预览网关基础响应稳定。
- 低并发页面和 401 场景 P95 在 30ms 左右。
- 30 并发下 P95 上升到 150–280ms，符合 Python stdlib 预览网关预期。
- 阶段 1 如果引入真实 Gateway Core，应把该数据作为最低基线。

## 7. 外部 agent 复核

已调用独立复核：

- bbq：完成复核。
- OpenCode：初次超时，但输出中定位了预览数据污染风险。

已按复核意见修复：

- 原 `XAPI_DATA_BASE` 指向生产 18181 的问题。
- 改为 19081 mock。
- 禁用预览在线更新。
- 修复 systemd 环境变量空格警告。

最终 bbq 复核结论：

- 19081 mock 已隔离。
- 在线更新已禁用。
- 9088/19080/19081/19082 不冲突。
- 阶段 0 预览改动安全，可部署。

## 8. 剩余风险

1. `/v1` 上游仍指向本机 18443。
   - 当前预览 key 由 mock 校验，生产 key 不会被预览创建。
   - 后续若要完整真实调用，需要单独建 preview upstream 或专用测试 key。

2. 当前预览网关是 Python stdlib `http.server`。
   - 适合阶段 0 预览。
   - 不适合作为未来正式 Gateway Core。

3. UI 仍是旧界面。
   - 阶段 0 只验证保护层。
   - 后续 UI 优化按 `ui-roadmap.md` 分批做。

4. mock data 只覆盖阶段 0 所需场景。
   - 不能代替完整 Sub2API 数据行为。
   - 阶段 1/2 需要设计正式数据层。

## 9. 当前结论

阶段 0 的真实预览环境已经可用。

`10.0.1.66:9088` 可以作为后续阶段 1 Gateway Core 改造前的固定验证入口。

后续任何涉及 `/v1` 行为、后台入口、request_id、回归测试的改动，都应先在该预览环境验证，再决定是否进入正式发布流程。
