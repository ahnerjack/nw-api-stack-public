# NW-API 阶段 1 第五刀：显式 request_id 日志报告

日期：2026-07-06
基准：`phase1-normalize-request-20260706`
目标：减少 access log 对 thread-local request_id 的隐式依赖，并补充 AUTH/MODEL 拒绝日志回归。

## 1. 本批改动

`services/xapi-v1-wrapper/xapi_v1_wrapper.py`：

- 所有 Handler 内 `log_access()` 调用显式传入 `request_id=self.request_id`。
- `log_access()` 函数保留 `request_id=''` 默认值，保持向后兼容。

覆盖场景：

- IP/Auth 拒绝
- Model 拒绝
- 上游 tunnel down
- upstream timeout
- client closed
- upstream error
- `/v1/models` 成功
- 流式/非流式上游成功
- stream timeout
- HTTPError 透传

## 2. 新增测试

`tests/phase0/test_v1_wrapper_regression.py`：

- `test_auth_reject_access_log`
- `test_model_not_allowed_access_log`

覆盖：

- 无效 key 返回 401，并写入 `INVALID_API_KEY` 日志。
- 模型未授权返回 403，并写入 `MODEL_NOT_ALLOWED` 日志。
- 日志中的 user_id/key_id/ip/method/path/model/status/error_code/request_id 符合现有语义。

说明：曾尝试加入 quota 拒绝日志测试，但 mock quota 返回 HTTP 403 会被 `urllib` 抛 `HTTPError`，当前 wrapper 按现有行为归一为 `INVALID_API_KEY`。该测试不等价，已移除，不在本刀改变行为。

## 3. 本地验证

| 项目 | 结果 |
|---|---:|
| phase1 core 单测 | 17/17 OK |
| phase0 wrapper 回归 | 14/14 OK |
| Python 编译 | OK |

## 4. 9088 预览验证

预览环境：

`http://10.0.1.66:9088/`

| 项目 | 结果 |
|---|---:|
| 远端 py_compile | OK |
| 四个预览服务 | active |
| 预览 10 轮功能测试 | 50/50 OK |
| 并发无效 key | 30/30 OK |

## 5. 性能基线

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 21.12 | 19.80 | 29.21 | 33.40 |
| 后台 `/nv-api/` | 30 | 200 x30 | 22.49 | 21.92 | 25.79 | 26.94 |
| 无效 key `/v1/models` | 30 | 401 x30 | 25.10 | 24.81 | 31.22 | 32.24 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 26.82 | 26.48 | 31.81 | 33.35 |
| 并发无效 key workers=10 | 30 | 401 x30 | 61.15 | 42.06 | 201.38 | 217.46 |
| 并发无效 key workers=30 | 60 | 401 x60 | 121.75 | 87.83 | 313.91 | 408.84 |
| 并发首页 workers=30 | 60 | 200 x60 | 65.49 | 37.69 | 185.76 | 194.70 |

## 6. 外部复核

bbq 复核结论：

- wrapper 共 11 处 `log_access()` 调用均已显式 `request_id`。
- AUTH invalid 日志回归覆盖正确。
- MODEL_NOT_ALLOWED 日志回归覆盖正确。
- quota 测试移除合理。
- 可合入。

## 7. 风险

1. 预览网关仍为 Python stdlib HTTP server，高并发表现有波动。
2. request_id 传参已显式化，但日志结构仍在 wrapper 内部，后续可抽成 AccessLogRecord。
3. quota/账户禁用等 xapi-data HTTPError 行为暂未改变，保持现状。

## 8. 下一步

阶段 1 第六刀建议：

- 抽 `AccessLogRecord` 数据结构，但仍由 wrapper 执行 SQLite 写入。
- 补 access log 构造纯函数测试。
- 继续不动正式站。
