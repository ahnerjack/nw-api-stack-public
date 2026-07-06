# 当前 /v1 行为基线

来源：`services/xapi-v1-wrapper/xapi_v1_wrapper.py`

## 1. 请求流程

```text
client request
  -> client_ip() from X-Forwarded-For first item or socket IP
  -> risk_allowed(ip) against portal SQLite risk_rules kind=ip
  -> Authorization: Bearer <key>
  -> xapi-data /keys/verify
  -> portal_user_by_sub2(sub2_user_id)
  -> GET /v1/models: synthesize local model list
  -> read body
  -> if JSON, extract model and check allowed_models
  -> TCP check upstream
  -> urllib.request.urlopen(upstream, timeout=UPSTREAM_CONNECT_TIMEOUT)
  -> stream_response / forward_http_error
  -> log_access into api_access_logs
```

## 2. 当前错误码

| 场景 | HTTP | code / 日志 error_code | 行为 |
|---|---:|---|---|
| 缺 Authorization | 401 | `INVALID_API_KEY` | wrapper JSON |
| Key 验证接口异常 | 401 | `INVALID_API_KEY` | 目前会把数据桥异常也当无效 Key |
| Key 无效 | 401 | 上游返回 code，默认 `INVALID_API_KEY` | wrapper JSON |
| 账号禁用或 portal 映射不存在 | 403 | `ACCOUNT_DISABLED` | wrapper JSON |
| IP 黑名单 | 403 | `IP_BLOCKED` | wrapper JSON |
| 模型未授权 | 403 | `MODEL_NOT_ALLOWED` | wrapper JSON |
| 上游 TCP 不通 | 502 | `UPSTREAM_TUNNEL_DOWN` | wrapper JSON |
| 上游 HTTP 429 | 429 | `UPSTREAM_RATE_LIMIT` | 透传上游 body |
| 上游 HTTP 502/503/504 | 原状态 | `UPSTREAM_UNAVAILABLE` | 透传上游 body |
| 连接/首响应超时 | 504 | `UPSTREAM_TIMEOUT` | wrapper JSON |
| 流式总超时/空闲超时 | 已发头后关闭 | `UPSTREAM_STREAM_TIMEOUT` | 不再追加第二个 JSON body |
| 客户端断开 | 499 | `CLIENT_CLOSED` | 写日志，关闭连接 |

## 3. 必测矩阵

每次 wrapper/Gateway/Core 改动至少跑：

1. `GET /v1/models`
2. `POST /v1/chat/completions` 非流式
3. `POST /v1/chat/completions` 流式
4. `POST /v1/chat/completions` JSON mode
5. `POST /v1/chat/completions` tool_calls 请求
6. vision/image_url 请求
7. 无 Authorization
8. 无效 Key
9. Key 禁用
10. 用户禁用
11. 模型未授权
12. 上游 429
13. 上游 5xx
14. 上游 TCP 不通
15. 上游首响应超时
16. SSE 中途断开/空闲超时
17. Content-Length 响应
18. HEAD 请求
19. OPTIONS 预检
20. 并发请求
21. 客户端断连

## 4. 已知行为缺口

- `json.loads` 失败时直接放过，日志里无法记录请求模型。
- request_id 还没有贯穿日志、响应头和上游请求。
- `/v1` 没有请求体大小限制。
- wrapper 信任 `X-Forwarded-For` 第一项，必须依赖反代覆盖。
- `risk_rules` 只有 `kind=ip` 在 wrapper 生效，portal UI 里的 email/path/model/region/note 暂不影响 `/v1`。
