# NW-API 阶段 0 执行报告

日期：2026-07-06
仓库：`/Users/ahner/projects/nw-api-stack-public`
分支：`public-sanitized`
阶段：阶段 0 第一批保护层

## 1. 本批目标

不改变正式业务、不部署正式站的前提下，完成阶段 0 的第一批可验证交付：

- 梳理当前系统路径、服务、数据流和模型映射。
- 建立 `/v1` 本地回归测试。
- 实现 request_id 最小链路。
- 补齐 wrapper systemd 模板和发布包清单。
- 记录风险、回滚和后续 UI 优化路线。

## 2. 已完成交付物

### 文档

目录：`docs/phase0/`

| 文件 | 内容 |
|---|---|
| `README.md` | 阶段 0 总说明和执行记录 |
| `api-inventory.md` | Portal、xapi-data、/v1 路径清单 |
| `dataflow.md` | 服务拓扑、端口、数据库、部署链路 |
| `model-mapping.md` | 当前模型来源、公开模型、价格来源 |
| `current-behavior.md` | 当前 `/v1` 请求流程、错误码、必测矩阵 |
| `request-id-design.md` | request_id 设计和当前实现状态 |
| `rollback-runbook.md` | 备份、回滚、回滚后验证命令 |
| `risk-register.md` | 风险登记和优先级 |
| `ui-roadmap.md` | 后续界面优化路线 |
| `phase0-execution-report.md` | 本报告 |

### 测试

新增：

`tests/phase0/test_v1_wrapper_regression.py`

特点：
- 使用 mock xapi-data。
- 使用 mock upstream。
- 不需要真实 API Key。
- 不访问正式环境。
- 覆盖 `/v1` 核心兼容行为。

当前覆盖：
1. `GET /v1/models`
2. 缺失 Key
3. 无效 Key
4. 模型未授权
5. 非流式 chat
6. 流式 chat
7. 上游 429 透传
8. HEAD
9. OPTIONS
10. access log 写入 request_id

### 代码保护层

修改：

`services/xapi-v1-wrapper/xapi_v1_wrapper.py`

已实现：
- 接收客户端 `X-Request-Id`。
- 未传时生成 `req_` + 24 位 hex。
- 所有响应头返回 `X-Request-Id`。
- 转发上游时带 `X-Request-Id`。
- `api_access_logs` 自动补 `request_id` 列。
- 创建 `idx_api_access_logs_request_id` 索引。

### 部署模板

新增：

`systemd/xapi-v1-wrapper.service`

修改：

- `scripts/build-release-package.py`：发布包包含 wrapper service。
- `scripts/deploy-aliyun.sh`：安装 wrapper service 并执行 `systemctl daemon-reload`。

## 3. 已执行验证

### 回归测试

命令：

```bash
cd /Users/ahner/projects/nw-api-stack-public
python3 tests/phase0/test_v1_wrapper_regression.py
```

结果：

```text
Ran 10 tests in ~1.03s
OK
```

### Python 编译检查

命令：

```bash
python3 -m py_compile \
  services/xapi-v1-wrapper/xapi_v1_wrapper.py \
  services/xapi-portal/xapi_portal.py \
  services/xapi-data/xapi_data_api.py \
  scripts/build-release-package.py \
  tests/phase0/test_v1_wrapper_regression.py
```

结果：通过。

### shell 语法检查

命令：

```bash
bash -n scripts/deploy-aliyun.sh scripts/deploy-sub2api-host.sh scripts/bootstrap-working-copy.sh
```

结果：通过。

### 发布包测试构建

命令：

```bash
python3 scripts/build-release-package.py --version phase0-test --dist /tmp/nwapi-phase0-dist
```

结果：通过。

确认 tar 包包含：

```text
services/xapi-v1-wrapper/xapi_v1_wrapper.py
systemd/xapi-v1-wrapper.service
```

## 4. 外部 agent 复核

已调用：

- bbq Hermes profile：完成，产出报告。
- Claude：超时，未形成可用文件。
- OpenCode：超时，未形成可用文件。

bbq 复核报告：

`/tmp/hermes-nwapi-phase0-dispatch-20260706-120520/bbq-review.md`

复核重点结论已吸收进：
- `risk-register.md`
- `current-behavior.md`
- `ui-roadmap.md`
- `request-id-design.md`

## 5. 当前风险判断

### 已降低的风险

- 后续修改 `/v1` 有了最小回归测试。
- 请求链路有 request_id，可用于用户反馈定位。
- 发布包不再遗漏 wrapper service 模板。
- 回滚和备份动作已文档化。

### 仍存在的风险

- request_id 目前主要在 wrapper 层，尚未打通 xapi-data 和 Sub2API usage 日志。
- 回归测试目前是 mock，本批未跑正式环境真实 Key。
- xapi-data 仍通过 shell + psql 操作数据库。
- portal 仍是单体 Python 字符串 HTML/CSS。
- UI 暂未优化。
- SQLite 多进程读写仍需观察。

## 6. 后续建议

下一批阶段 0：

1. 增加真实预览环境测试，不动正式站。
2. 加 `/v1` 性能基线：P50/P95/P99、首 token、错误率。
3. 扩展测试：tool calls、JSON mode、vision、长上下文、并发、客户端断连。
4. 把 request_id 继续传到 xapi-data 和 usage 查询。
5. 归档 NAS 并提交 Git。

UI 优化：

- 不在阶段 0 改。
- 阶段 1 后做视觉清理。
- 阶段 2 做控制台信息架构重构。
- 阶段 5 做完整运营后台重构。

## 7. 当前结论

阶段 0 第一批已经具备“可保护后续开发”的基本能力：

- 有文档。
- 有回归测试。
- 有 request_id。
- 有回滚手册。
- 有风险清单。
- 有 UI 后续路线。

还不能认为阶段 0 完全结束；需要再补真实预览环境测试、性能基线和更完整的 API 场景。
