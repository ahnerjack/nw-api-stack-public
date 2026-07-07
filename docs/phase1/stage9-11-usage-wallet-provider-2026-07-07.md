# NW-API 阶段9-11：自有用量流水、影子账本、Provider Adapter

时间：2026-07-07
范围：9088 预览栈；正式站未更新。

## 阶段9：自有用量流水

已新增 `nw_usage_events`：
- request_id 唯一，防重复记账
- user_id/key_id/key_source
- provider/method/path/model
- http_status/status/error_code/latency_ms
- prompt_tokens/completion_tokens/total_tokens
- input/output/total USD micros
- usage_status/raw_usage_json

wrapper 行为：
- `/v1/models` 不计费
- chat/mock 或非流式响应可解析 `usage`
- 记录 `reported/no_usage/error` 状态
- request_id 贯穿 access log 与 usage event

## 阶段10：钱包/账本最小闭环

已新增：
- `nw_wallets`
- `nw_wallet_ledger`

当前策略是 shadow billing：
- 成功请求 + 有 usage + NW 自有 key 时，写入 `usage_debit_shadow`
- 账本金额为负数 debit
- 同时更新 `nw_api_keys.quota_used`
- 不影响正式真实余额，不对正式用户扣费

## 阶段11：Provider Adapter 最小抽象

新增 `services/xapi-v1-wrapper/provider_adapter.py`：
- `OpenAICompatibleAdapter`
- `ProviderResponse`
- `UsageSnapshot`
- `parse_usage_from_body()`

新增 `services/xapi-v1-wrapper/usage_wallet.py`：
- schema 初始化
- usage 计费估算
- usage event + wallet ledger 幂等写入

Provider 表：
- `nw_providers`
- `nw_provider_models`
- 默认 provider：`sub2api/openai_compatible/env:XAPI_UPSTREAM`

## 测试

本地：
- py_compile：通过
- `tests.phase1.test_gateway_core`：通过
- `tests.phase0.test_v1_wrapper_regression`：通过
- `tests.phase0.test_release_versioning`：通过
- 总计 42/42 通过
- secret scan：0

预览：
- 9088 smoke：SMOKE_OK
- 临时 `nwk_stage911_*` 调用 `/v1/chat/completions`：HTTP 200
- 响应包含 usage：prompt=1, completion=1, total=2
- `nw_usage_events` 落库：`billed_shadow`, usage_status=`reported`
- `nw_wallet_ledger` 落库：`usage_debit_shadow`
- `nw_providers` 默认 provider 存在：`sub2api/openai_compatible/active`
- qqw 调用 9088：成功

## 预览验证样例

request_id：`req_stage911_live_1783389906`
usage：`('req_stage911_live_1783389906', 'gpt-5.5', 'billed_shadow', 200, 1, 1, 245, 'reported')`
ledger：`('usage_debit_shadow', -245, -245)`
providers：`[('sub2api', 'openai_compatible', 'active')]`

## 边界

- 当前是 shadow billing，不是正式实扣费。
- stream 响应如上游不返回 usage，记录为 no_usage，不强行扣费。
- 阶段11 只做最小 provider adapter，不做多 provider fallback、健康检查、成本路由。
- 正式站未更新。

## 下一步

阶段12：产品化收口。
建议包含：
- 控制台 UI 独立产品化
- 管理端展示 NW usage/wallet/provider
- 正式发布 V0.0.3-rc.1
- 用户可见文案弱化 Sub2API 依赖
- 正式迁移前跑 Release Gate
