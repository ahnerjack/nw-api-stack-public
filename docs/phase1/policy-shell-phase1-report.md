# NW-API 阶段 1 第二刀：Policy Shell 报告

日期：2026-07-06
基准：`phase1-gateway-core-20260706`
目标：继续只做低风险重构，把策略判断外壳抽入 Gateway Core，保持 `/v1` 对外行为不变。

## 1. 本批改动

新增到 `services/xapi-v1-wrapper/gateway_core.py`：

- `PolicyResult`
- `IPRiskPolicy`
- `AuthPolicy`
- `ModelAllowPolicy`

这些策略类不直接访问：

- 网络
- SQLite
- 文件系统
- systemd
- 环境变量

所有 I/O 仍由 `xapi_v1_wrapper.py` 注入：

- IP 风险：`risk_allowed`
- Key 校验：`lambda key: post_json('/keys/verify', {'key': key})`
- Portal 用户加载：`portal_user_by_sub2`
- 模型允许列表：`allowed_models`

## 2. wrapper 行为边界

`xapi_v1_wrapper.py` 仍保留：

- HTTP Handler 生命周期
- 请求体读取
- access log 写入
- SQLite 查询函数
- xapi-data 调用函数
- 上游转发与流式处理

本批只把原先内联的判断逻辑改成等价委托：

| 旧逻辑 | 新逻辑 | 行为 |
|---|---|---|
| `risk_allowed(cip)` | `IPRiskPolicy(risk_allowed).evaluate(req)` | 等价 |
| Authorization 解析 + `post_json('/keys/verify')` | `AuthPolicy(...).evaluate(req)` | 等价 |
| `model in allowed_models(uid)` | `ModelAllowPolicy(allowed_models).evaluate(...)` | 等价 |

日志调用仍在 wrapper 中，不进入策略层。

## 3. 已验证

### 本地测试

| 项目 | 结果 |
|---|---:|
| phase1 core 单测 | 13/13 OK |
| phase0 wrapper 回归 | 10/10 OK |
| Python 编译 | OK |

### 9088 预览环境

已部署：

`http://10.0.1.66:9088/`

部署验证：

| 项目 | 结果 |
|---|---:|
| 四个预览 systemd 服务 | active |
| 远端 `py_compile` | OK |
| 首页 `/` | OK |
| mock data health | OK |
| 预览 10 轮功能测试 | 50/50 OK |
| 并发无效 key | 30/30 OK |

### 性能基线

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 18.87 | 18.92 | 22.06 | 22.96 |
| 后台 `/nv-api/` | 30 | 200 x30 | 23.80 | 21.97 | 34.11 | 55.47 |
| 无效 key `/v1/models` | 30 | 401 x30 | 26.00 | 25.55 | 29.96 | 31.37 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 25.16 | 25.11 | 29.12 | 30.99 |
| 并发无效 key workers=10 | 30 | 401 x30 | 49.76 | 41.42 | 106.72 | 109.62 |
| 并发无效 key workers=30 | 60 | 401 x60 | 129.69 | 96.02 | 361.61 | 394.97 |
| 并发首页 workers=30 | 60 | 200 x60 | 76.61 | 35.41 | 167.59 | 173.79 |

## 4. 外部复核

bbq 复核结论：

- 策略外壳等价委托完整。
- 日志字段无变化。
- 部署风险低。
- 当前变化仍属于纯重构。

复核指出两个边缘行为变化，均为容错改善：

1. 非 dict JSON body 不再触发异常，而是跳过模型检查继续转发。
2. xapi-data 返回空 `code` 时，错误码 fallback 为 `INVALID_API_KEY`。

正常请求路径不受影响。

## 5. 风险

1. 策略层仍不是完整 pipeline，只是外壳。
2. Auth / Model / Risk 的 I/O 仍在 wrapper 函数中。
3. 流式转发仍依赖当前 stdlib 实现，尚未抽象。
4. 30 并发下 P95 有波动，仍属于预览网关和 Python stdlib server 范围。

## 6. 下一步

阶段 1 第三刀建议：

- 增加 `PolicyPipeline`，只负责编排，不做 I/O。
- 把 `NormalizedRequest` 真正贯穿入口。
- 继续保持 log/render 在 wrapper。
- 每刀都跑 phase0 + phase1 + 9088 多轮测试。

不建议现在换 FastAPI，不建议触碰正式站。
