# NW-API 阶段 1 第六刀：AccessLogRecord 抽取报告

日期：2026-07-06
基准：`phase1-explicit-request-id-20260706`
目标：抽出 access log 数据结构和构造函数，但 SQLite 写入仍留在 wrapper，不改 DB schema，不改行为。

## 1. 本批改动

`services/xapi-v1-wrapper/gateway_core.py`：

- 新增 `AccessLogRecord` dataclass。
- 新增 `build_access_log_record()` 纯函数。
- 新增 `AccessLogRecord.insert_values(created_at)`，只返回 DB insert tuple。

`services/xapi-v1-wrapper/xapi_v1_wrapper.py`：

- `log_access()` 内部先构造 `AccessLogRecord`。
- SQLite 建表、补列、索引、清理旧日志、插入、提交仍全部留在 wrapper。
- `created_at` 仍由 `log_access()` 使用 `int(time.time())` 生成。
- `request_id` fallback 仍在 wrapper：`request_id or current_request_id()`。

## 2. 新增测试

`tests/phase1/test_gateway_core.py`：

- `test_access_log_record_defaults`
- `test_access_log_record_insert_values`
- `test_access_log_record_normalizes_empty_values`

覆盖：

- 默认值语义与旧 `log_access()` 参数一致。
- `insert_values(created_at)` 顺序与 DB INSERT 绑定值一致。
- None/空值规范化仍产生旧行为需要的空串/0。

## 3. 不变项

| 项目 | 状态 |
|---|---|
| DB schema | 未改 |
| request_id 列/索引 | 未改 |
| created_at 生成位置 | wrapper 内部，未改 |
| SQLite 写入位置 | wrapper 内部，未改 |
| access log 调用点 | 未改业务语义 |
| 正式站 | 未动 |

## 4. 本地验证

| 项目 | 结果 |
|---|---:|
| phase1 core 单测 | 20/20 OK |
| phase0 wrapper 回归 | 14/14 OK |
| Python 编译 | OK |

## 5. 9088 预览验证

预览环境：

`http://10.0.1.66:9088/`

| 项目 | 结果 |
|---|---:|
| 远端 py_compile | OK |
| 四个预览服务 | active |
| 预览 10 轮功能测试 | 50/50 OK |
| 并发无效 key | 30/30 OK |

## 6. 性能基线

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 18.08 | 17.14 | 25.11 | 26.20 |
| 后台 `/nv-api/` | 30 | 200 x30 | 21.37 | 20.74 | 26.82 | 27.69 |
| 无效 key `/v1/models` | 30 | 401 x30 | 23.56 | 23.35 | 28.90 | 30.78 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 23.58 | 22.88 | 26.93 | 28.25 |
| 并发无效 key workers=10 | 30 | 401 x30 | 58.13 | 34.45 | 190.12 | 197.59 |
| 并发无效 key workers=30 | 60 | 401 x60 | 146.21 | 65.78 | 411.19 | 710.73 |
| 并发首页 workers=30 | 60 | 200 x60 | 80.61 | 36.05 | 170.44 | 182.82 |

说明：高并发 P95 波动仍来自预览 stdlib server，并发功能结果全部正确。

## 7. 外部复核

bbq 复核结论：

- DB schema 未改。
- `created_at` 仍在 `log_access()` 内计算。
- `request_id` fallback 保留旧逻辑。
- 默认值语义分层清晰。
- phase1 20/20、phase0 14/14 测试通过。
- 纯重构，可合入。

## 8. 风险

1. `AccessLogRecord.insert_values()` 当前仍面向现有 SQLite insert 顺序，后续改 schema 必须同步测试。
2. wrapper 仍负责 SQLite 写入和 schema 迁移，后续可抽 repository 层，但本刀刻意不做。
3. quota/账户禁用 HTTPError 行为仍保持第五刀记录的现状。

## 9. 下一步

阶段 1 第七刀建议：

- 抽 `AccessLogRepository` 或 `write_access_log_record()` 外壳，但保持 SQLite 仍由 wrapper 调用。
- 增加 log writer 的临时 SQLite 集成测试。
- 继续不动正式站。
