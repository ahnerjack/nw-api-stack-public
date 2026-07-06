# NW-API 阶段 1 第三刀：PolicyPipeline 报告

日期：2026-07-06
基准：`phase1-policy-shell-20260706`
目标：把分散策略调用收敛到 `PolicyPipeline` 编排层，不改变 `/v1` 对外行为。

## 1. 本批改动

新增到 `services/xapi-v1-wrapper/gateway_core.py`：

- `PolicyPipeline`

职责：

- 按顺序执行 policy。
- 合并每个 `PolicyResult.context`。
- 遇到 deny 立即短路。
- 返回携带累积 context 的 `PolicyResult`。

不负责：

- 网络 I/O
- SQLite
- access log
- HTTP response render
- 上游转发

## 2. wrapper 接入方式

`xapi_v1_wrapper.py` 当前使用两段 pipeline：

1. Risk + Auth：

- `IPRiskPolicy(risk_allowed)`
- `AuthPolicy(lambda key: post_json('/keys/verify', {'key': key}), portal_user_by_sub2)`

2. Model：

- `ModelAllowPolicy(allowed_models)`

保持 `/v1/models` 仍在 Auth 后、Model 检查前返回。

## 3. 行为边界

保持不变：

- IP 拒绝：403 `IP_BLOCKED`
- 缺 key：401 `INVALID_API_KEY`
- 无效 key：401，沿用 xapi-data 返回 code/message
- 账号不可用：403 `ACCOUNT_DISABLED`
- 模型未授权：403 `MODEL_NOT_ALLOWED`
- `/v1/models` 模型列表返回
- 上游 429/stream/non-stream 透传
- access log 写入位置和字段语义

## 4. 测试结果

### 本地

| 项目 | 结果 |
|---|---:|
| phase1 core 单测 | 16/16 OK |
| phase0 wrapper 回归 | 10/10 OK |
| Python 编译 | OK |

新增 pipeline 单测覆盖：

- 全部 allow 并合并 context
- deny 短路，后续策略不执行
- 初始 context 传入与保留

### 9088 预览环境

已部署：

`http://10.0.1.66:9088/`

验证：

| 项目 | 结果 |
|---|---:|
| 远端 py_compile | OK |
| 四个预览服务 | active |
| 预览 10 轮功能测试 | 50/50 OK |
| 并发无效 key | 30/30 OK |

### 性能基线

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 20.61 | 20.43 | 27.47 | 33.07 |
| 后台 `/nv-api/` | 30 | 200 x30 | 24.03 | 24.02 | 28.23 | 30.69 |
| 无效 key `/v1/models` | 30 | 401 x30 | 26.23 | 25.09 | 30.44 | 39.40 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 27.15 | 26.13 | 35.96 | 36.97 |
| 并发无效 key workers=10 | 30 | 401 x30 | 49.29 | 38.06 | 102.21 | 116.13 |
| 并发无效 key workers=30 | 60 | 401 x60 | 123.79 | 84.03 | 278.83 | 349.26 |
| 并发首页 workers=30 | 60 | 200 x60 | 127.43 | 139.51 | 398.05 | 403.31 |

并发首页本轮波动较高，但功能正确；/v1 关键路径保持稳定。

## 5. 外部复核

bbq 复核结论：

- Context 合并正确。
- deny 短路正确。
- wrapper 日志字段语义无变化。
- `/v1/models` 路径行为无变化。
- Model 检查通过单策略 pipeline 后行为等价。
- 可合入。

## 6. 风险

1. Pipeline 目前只编排，不捕获 policy 内部异常；当前 policy 行为仍与旧 wrapper 一致。
2. Body 仍保持 Auth 后读取，避免无效 key 大 body 提前读入。
3. Auth/Risk/Model 的 I/O 仍在 wrapper 注入函数中，后续才逐步外移。
4. 流式转发仍未抽象。

## 7. 下一步

阶段 1 第四刀建议：

- 用 `normalize_request()` 统一入口请求构造。
- 保持 body 读取时机不提前。
- 增加 wrapper 集成测试覆盖 IP_BLOCKED 日志字段。
- 继续不动正式站。
