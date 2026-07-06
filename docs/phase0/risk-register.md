# 阶段 0 风险登记

| ID | 风险 | 等级 | 证据 | 阶段 0 处理 |
|---|---|---|---|---|
| R1 | xapi-data 通过 `shell=True` + psql 拼 SQL | 高 | `xapi_data_api.py:sh/sql` | 登记，后续改 DB driver；阶段 0 测试覆盖关键接口 |
| R2 | portal 单体文件过大，HTML/CSS/业务/DB 混合 | 高 | `xapi_portal.py` 约 1560 行，CSS 内嵌 | 不在阶段 0 重构，列入 UI/架构阶段 |
| R3 | SQLite 被 portal 和 wrapper 多进程读写 | 中 | wrapper `log_access()` 直接写 portal DB | 阶段 0 观察，后续迁 Postgres 或日志队列 |
| R4 | request_id 缺失 | 中 | 当前 `request_id` 搜索无结果 | 阶段 0 最小补齐 |
| R5 | X-Forwarded-For 可被伪造 | 中 | wrapper `client_ip()` 信任第一项 | 阶段 0 文档要求核查反代覆盖，后续可只信任反代 IP |
| R6 | 非 JSON/坏 JSON 请求模型审计缺失 | 中 | JSONDecodeError pass | 阶段 0 测试记录，阶段 1 Gateway Core 修 |
| R7 | risk_rules UI 支持多类型但 wrapper 只执行 IP | 中 | wrapper SQL `WHERE kind="ip"` | 文档明确，避免误以为 email/path 生效 |
| R8 | 已补 xapi-v1-wrapper systemd 模板，正式部署前仍需验证实际 unit | 中 | repo systemd 只有 portal/data | 阶段 0 补清单，后续补 unit |
| R9 | session 存内存 | 低/中 | `SESS={}` | 后续改 DB/Redis session |
| R10 | UI 观感差、维护成本高 | 中 | Python 字符串模板 + 内嵌 CSS | 后续单独 UI 阶段优化，不混入阶段 0 |

## 优先处理顺序

1. request_id + 回归测试。
2. `/v1` 行为和错误码基线。
3. 备份/回滚手册。
4. xapi-data SQL 风险评估与替换方案。
5. wrapper systemd 模板和部署一致性。
6. UI 重构路线。
