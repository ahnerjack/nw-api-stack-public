# NW-API 真实上游高并发验证

时间：2026-07-07
范围：9088 预览栈；正式站未更新。

## 初始现象

使用 qqw 的 `nwk_` 自有 Key 直接压测真实 `/v1/chat/completions`：

- 5 并发：0/5，全部 401 `INVALID_API_KEY`
- 20 并发：0/20，全部 401
- 50 并发：0/50，全部 401

直接打上游 `10.0.1.66:18443`，使用 Sub2API 服务 Key：

- `/v1/models`：200
- `/v1/chat/completions`：200

## 根因

阶段8自有 Key 做了本地鉴权，但 wrapper 转发真实上游时仍把客户端 Authorization 原样传给 Sub2API。

`nwk_` 是 NW 自有 Key，上游 Sub2API 不认识，所以真实 chat 返回 401。

## 修复

新增环境变量：

`XAPI_UPSTREAM_API_KEY`

wrapper 行为：

- 客户端 Key 只用于 NW 本地鉴权
- 转发真实上游时，如果配置了 `XAPI_UPSTREAM_API_KEY`，用服务端上游 Key 覆盖 Authorization
- 避免把 `nwk_` 或用户 Key 透传给上游

新增回归测试：

`test_nw_key_uses_service_upstream_key`

验证：

- 上游收到服务端 key
- 上游没有收到用户 `nwk_` key

## 修复后真实上游压测

模型：`gpt-5.4-mini`
请求：低 token，`max_tokens=3`
路径：9088 预览 `/v1/chat/completions`
Key：qqw `nwk_` 自有 Key
Mock：关闭，真实上游

结果：

- 3 并发：3/3 成功，P50 2396ms，P95 2456ms
- 10 并发：10/10 成功，P50 2217ms，P95 5066ms
- 30 并发：24/30 成功，6 个 429

429 错误：

`Too many pending requests, please retry later`

这是上游 pending rate limit，不是 wrapper 崩溃。

## DB 核验

`req_real_fixed_%`：

- `nw_usage_events`：37 条
- `nw_wallet_ledger`：37 条
- http_status/status：37 条 `200 / billed_shadow`
- usage_status：37 条 `reported`

说明：成功的真实上游请求均写入 usage 与 shadow wallet ledger。

## 服务状态

- nginx active
- xapi-data active
- xapi-portal active
- xapi-v1-wrapper active
- warning 日志：无

## 本地回归

- 43/43 通过
- secret scan：真实 key 0；测试变量名存在 api_key 规则假阳性 1

## Commit

`9bd60f9 Use service upstream key for owned-key forwarding`

## 结论

真实上游高并发已验证。

可稳定承载：

- 3 并发真实上游：全成功
- 10 并发真实上游：全成功

30 并发开始触发上游 pending 限流，建议正式策略：

- wrapper 加并发限流/排队阈值
- 对上游 429 做明确提示与重试建议
- 正式默认并发阈值低于上游 pending limit
