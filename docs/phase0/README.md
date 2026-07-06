# NW-API 阶段 0：现状测绘与保护层

目标：不改变正式业务行为，先把当前 `/v1`、门户、数据桥、部署更新链路摸清楚，并建立后续重构必须依赖的回归测试、request_id、回滚和风险清单。

阶段 0 不做：
- 不切换正式 Provider。
- 不改真实计费规则。
- 不迁移数据库。
- 不重做 UI。
- 不部署正式站，除非明确授权。

交付物：
- `api-inventory.md`：公开页面、控制台、数据桥、`/v1` API 清单。
- `dataflow.md`：服务拓扑、端口、数据库和上游依赖。
- `model-mapping.md`：当前模型来源、公开模型与上游模型关系。
- `current-behavior.md`：当前 `/v1` 行为基线和必测场景。
- `request-id-design.md`：request_id 最小落地方案。
- `rollback-runbook.md`：回滚触发条件、命令和验证步骤。
- `risk-register.md`：阶段 0 发现的风险与后续处理顺序。
- `ui-roadmap.md`：后续整体界面优化路线，明确不混入阶段 0。
- `../../tests/phase0/test_v1_wrapper_regression.py`：本地 mock 回归测试脚本。

验收标准：
1. 文档能解释当前系统真实工作方式。
2. 测试脚本可在本机无真实上游、无真实 Key 的情况下跑通核心 `/v1` 行为。
3. 后续阶段改 wrapper、Gateway Core、Provider Adapter 前，必须先跑测试。
4. 任何正式部署前，都要先备份、跑回归、再发布。


## 当前阶段 0 执行记录

已完成第一批：
- 阶段 0 文档骨架。
- 本地 mock `/v1` 回归测试脚本。
- request_id 最小实现。
- xapi-v1-wrapper systemd 模板。
- 构建包清单包含 wrapper service。

已验证：
- `python3 tests/phase0/test_v1_wrapper_regression.py`：10 项通过。
- `python3 -m py_compile ...`：通过。

未做：
- 未部署正式环境。
- 未改 UI。
- 未改真实计费。
- 未迁移数据库。
