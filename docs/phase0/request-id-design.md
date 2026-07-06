# request_id 最小落地方案

## 1. 目标

每个 `/v1` 请求都有一个可追踪 ID，用于串联：
- 客户端反馈
- wrapper access log
- 上游请求 header
- 后续 xapi-data / usage / billing 日志

阶段 0 只做最小方案，不改变 API 响应 body。

## 2. ID 格式

建议：
`req_` + 24 位 hex，例如：
`req_9f3c12a4e8b14d0aa0b1c2d3`

## 3. 生成规则

- 如果客户端传 `X-Request-Id` 且格式安全，沿用并截断到 80 字符。
- 否则 wrapper 生成新 ID。
- 响应头返回 `X-Request-Id`。
- 转发上游时带 `X-Request-Id`。

## 4. 数据库变更

给 `api_access_logs` 增加可选列：

```sql
ALTER TABLE api_access_logs ADD COLUMN request_id TEXT;
CREATE INDEX IF NOT EXISTS idx_api_access_logs_request_id ON api_access_logs(request_id);
```

SQLite 不支持 `ADD COLUMN IF NOT EXISTS`，代码里应捕获 duplicate column 异常。

## 5. 阶段 0 范围

做：
- wrapper 生成/透传/响应 `X-Request-Id`
- wrapper access log 写 request_id
- 回归测试验证 header 存在

暂不做：
- portal 页面按 request_id 搜索
- xapi-data 全链路追踪
- Sub2API 代码修改
- 分布式 tracing 系统

## 6. 后续阶段

阶段 1 Gateway Core 时，把 request_id 放进 `NormalizedRequest`。
阶段 4 计费时，把 request_id 作为 usage/ledger 幂等键的组成部分。


## 7. 当前实现状态

已在阶段 0 最小实现中完成：
- wrapper 接收或生成 `X-Request-Id`。
- 所有响应头自动带 `X-Request-Id`。
- 转发上游时带 `X-Request-Id`。
- `api_access_logs` 自动补 `request_id` 列和索引。
- 本地 mock 回归测试验证 header、上游透传、日志字段。

测试命令：

```bash
cd /Users/ahner/projects/nw-api-stack-public
python3 tests/phase0/test_v1_wrapper_regression.py
python3 -m py_compile services/xapi-v1-wrapper/xapi_v1_wrapper.py tests/phase0/test_v1_wrapper_regression.py
```
