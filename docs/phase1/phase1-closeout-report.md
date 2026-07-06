# NW-API 阶段 1 收口报告

日期：2026-07-06
最终预览环境：`http://10.0.1.66:9088/`
最终分支：`public-sanitized`
最终 tag：`phase1-closeout-20260706`

## 1. 目标

阶段 1 目标是把 `/v1` wrapper 中可纯化的网关核心逻辑逐步抽到 `gateway_core.py`，并保持行为不变。

本阶段坚持：

- 不动正式站。
- 不改正式端口 18180/18181/18182。
- 只部署 9088 预览环境。
- 不改 DB schema。
- 不改 xapi-data / portal 业务协议。
- 每刀都跑本地回归和 9088 预览验证。

## 2. 已完成的阶段 1 刀次

1. Gateway Core 纯函数骨架。
2. PolicyResult / AuthPolicy / IPRiskPolicy / ModelAllowPolicy。
3. PolicyPipeline 编排层。
4. normalize_request 统一入口构造。
5. access log 显式 request_id。
6. AccessLogRecord / build_access_log_record。
7. AccessLogWriter 协议外壳。
8. upstream_http_error_code 纯函数。
9. 阶段 1 总收口验证、归档、tag。

## 3. Gateway Core 当前导出能力

`services/xapi-v1-wrapper/gateway_core.py` 现在包含：

- `ErrorResponse`
- `PolicyResult`
- `IPRiskPolicy`
- `AuthPolicy`
- `ModelAllowPolicy`
- `PolicyPipeline`
- `NormalizedRequest`
- `AccessLogRecord`
- `build_access_log_record()`
- `AccessLogWriter`
- `write_access_log_record()`
- `header_get()`
- `make_request_id_from_headers()`
- `client_ip_from_headers()`
- `extract_bearer_token()`
- `model_from_json_body()`
- `normalize_request()`
- `build_model_list_payload()`
- `proxy_request_headers()`
- `should_forward_response_header()`
- `upstream_http_error_code()`
- `should_chunk_downstream()`
- `encode_chunk()`

## 4. 最终收口新增改动

最后收口新增两项低风险抽取：

### AccessLogWriter 协议外壳

新增：

- `AccessLogWriter(Protocol)`
- `write_access_log_record(writer, record, created_at)`

现阶段仅定义协议和纯调用外壳，不接管 SQLite。
SQLite 连接、建表、补列、索引、清理旧日志、插入、提交仍留在 wrapper 的 `log_access()`。

### upstream_http_error_code

把 wrapper 中内联的上游 HTTP 错误码映射抽为纯函数：

- 429 -> `UPSTREAM_RATE_LIMIT`
- 502/503/504 -> `UPSTREAM_UNAVAILABLE`
- 其他 -> `UPSTREAM_HTTP_ERROR`

映射逻辑与旧代码等价。

## 5. 最终验证结果

### 本地验证

| 项目 | 结果 |
|---|---:|
| Python 编译 | OK |
| phase1 core 单测 | 22/22 OK |
| phase0 wrapper 回归 | 14/14 OK |
| release package 构建 | OK |

### 9088 预览验证

| 项目 | 结果 |
|---|---:|
| 远端 py_compile | OK |
| xapi-data-phase0-preview | active |
| xapi-portal-phase0-preview | active |
| xapi-v1-wrapper-phase0-preview | active |
| nw-api-phase0-preview | active |
| 预览 10 轮功能测试 | 50/50 OK |
| 并发无效 key | 30/30 OK |
| mock data health | OK |

### 性能基线

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 16.66 | 16.25 | 20.80 | 20.86 |
| 后台 `/nv-api/` | 30 | 200 x30 | 20.91 | 20.48 | 26.47 | 28.08 |
| 无效 key `/v1/models` | 30 | 401 x30 | 21.39 | 20.83 | 27.24 | 28.85 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 21.90 | 21.37 | 30.20 | 32.29 |
| 并发无效 key workers=10 | 30 | 401 x30 | 53.24 | 35.37 | 167.67 | 167.92 |
| 并发无效 key workers=30 | 60 | 401 x60 | 110.84 | 80.30 | 256.09 | 374.78 |
| 并发首页 workers=30 | 60 | 200 x60 | 77.98 | 30.46 | 156.97 | 158.97 |

## 6. 外部复核

bbq 最终复核结论：

- DB schema 未改。
- SQLite 写入仍在 wrapper。
- 上游错误映射等价。
- phase1 core 22/22 OK。
- phase0 wrapper 14/14 OK。
- 正式站未触碰。
- 可合入。

## 7. 明确未改边界

以下内容仍保留在 wrapper 或后续阶段处理：

- SQLite 建表/ALTER/索引/清理/INSERT。
- `post_json()` 与 xapi-data 通信协议。
- `portal_user_by_sub2()` 与 portal DB 查询。
- `allowed_models()` 与模型授权查询。
- `upstream_reachable()` TCP 预检。
- stdlib `BaseHTTPRequestHandler` 生命周期。
- 流式响应 `_sock` 私有属性逻辑。
- 生产 systemd / Caddy / 正式端口。
- portal UI 与在线更新逻辑。

## 8. 已知风险与阶段 2 建议

1. stdlib HTTP server 预览并发 P95 有波动，但功能结果稳定。
2. 流式转发依赖 `response.fp.raw._sock`，阶段 2 应单独重构和压测。
3. quota / 账户禁用经 `urllib.HTTPError` 的归一行为仍保持现状，需单独作为业务修复处理。
4. SQLite writer 仍在 wrapper，阶段 2 可抽 repository 层并补临时 SQLite 集成测试。
5. FastAPI/httpx 迁移应放阶段 2，不在阶段 1 混入。

## 9. 结论

阶段 1 已完成。

当前产物已经具备清晰的 Gateway Core 纯函数和策略编排基础，wrapper 仍承担 I/O、SQLite、HTTP handler 生命周期和上游转发，行为保持不变。

最终验证全部通过，已可作为阶段 2 的安全起点。
