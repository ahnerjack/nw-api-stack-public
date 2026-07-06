# NW-API 阶段 1 第四刀：normalize_request 统一入口报告

日期：2026-07-06
基准：`phase1-policy-pipeline-20260706`
目标：wrapper 入口统一使用 `gateway_core.normalize_request()`，同时不提前读取 body，并补 IP_BLOCKED 日志回归。

## 1. 本批改动

### xapi_v1_wrapper.py

- 用 `normalize_request()` 替代手工构造 `NormalizedRequest`。
- Risk/Auth 阶段调用：`body=b''`，只解析 header / client_ip / request_id / api_key。
- Auth 通过后才 `read_body()`。
- Model 阶段再次调用 `normalize_request()`，此时传入已读取 body，用于解析 model。

保持不变：

- body 不在 IP/Auth 前读取。
- `/v1/models` 仍在 Auth 后、Model 检查前返回。
- log/render/upstream 转发仍在 wrapper。

### gateway_core.py

给 `NormalizedRequest.model` 加注释：

`model` 只有在 body 已读取并传入 `normalize_request()` 后才有意义。

## 2. 新增测试

### tests/phase0/test_v1_wrapper_regression.py

新增：

- `test_ip_blocked_access_log`
- `test_ip_blocked_post_body_access_log`

覆盖：

- IP 黑名单返回 403 `IP_BLOCKED`
- access log 中 `user_id IS NULL`
- access log 中 `key_id IS NULL`
- IP、method、path、status、error_code、request_id 正确
- POST + body 被 IP 阻断时 model 为空，说明 body 没有进入模型解析路径

### tests/phase1/test_gateway_core.py

新增：

- `test_normalize_request_without_body_keeps_auth_and_empty_model`

覆盖：

- 空 body 时仍能解析 Authorization
- 空 body 时 model 为空
- client_ip 从 X-Forwarded-For 提取

## 3. 本地验证

| 项目 | 结果 |
|---|---:|
| phase1 core 单测 | 17/17 OK |
| phase0 wrapper 回归 | 12/12 OK |
| Python 编译 | OK |

## 4. 9088 预览验证

预览环境：

`http://10.0.1.66:9088/`

部署后：

| 项目 | 结果 |
|---|---:|
| 远端 py_compile | OK |
| 四个预览服务 | active |
| 端口 | 9088/19080/19081/19082 正常监听 |
| 预览 10 轮功能测试 | 50/50 OK |
| 并发无效 key | 30/30 OK |

说明：首次并发预览脚本最后 30 并发出现一次 `ConnectionResetError`，立即检查 systemd/journal 后未发现服务崩溃或异常，四个服务仍 active；随后完整重跑通过。记录为预览 stdlib server 并发瞬时波动，不作为功能失败。

## 5. 性能基线（复测通过轮）

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 16.78 | 16.78 | 19.42 | 19.44 |
| 后台 `/nv-api/` | 30 | 200 x30 | 23.05 | 20.83 | 23.22 | 87.04 |
| 无效 key `/v1/models` | 30 | 401 x30 | 23.28 | 23.30 | 26.05 | 27.59 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 25.37 | 25.38 | 29.63 | 33.96 |
| 并发无效 key workers=10 | 30 | 401 x30 | 49.29 | 34.49 | 138.22 | 159.29 |
| 并发无效 key workers=30 | 60 | 401 x60 | 114.56 | 83.80 | 275.72 | 387.83 |
| 并发首页 workers=30 | 60 | 200 x60 | 81.70 | 29.75 | 161.75 | 531.16 |

## 6. 外部复核

bbq 复核结论：

- normalize_request 接入正确。
- body 读取时机保持不变。
- IP_BLOCKED GET/POST access log 测试覆盖核心字段。
- `NormalizedRequest.model` 注释准确。
- 可合入。

## 7. 风险

1. 预览网关仍是 Python stdlib HTTP server，高并发首页偶有波动。
2. request_id 仍主要依赖 thread-local 传入日志，后续可逐步显式化。
3. Gateway Core 仍未抽流式转发和上游连接策略。

## 8. 下一步

阶段 1 第五刀建议：

- 显式把 `request_id` 传入关键 `log_access()` 调用，降低 thread-local 隐式依赖。
- 增加 AUTH/MODEL 拒绝日志字段回归测试。
- 仍不动正式站。
