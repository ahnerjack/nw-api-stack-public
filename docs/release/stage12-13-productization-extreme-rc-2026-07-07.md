# NW-API 阶段12-13：产品化收口、极端场景、RC Gate

时间：2026-07-07
范围：9088 预览栈 + V0.0.3-rc.1 构建；正式站只读检查，未更新。

## 阶段12：产品化收口

已把管理端“账号消耗统计”改为 NW 自有视角：

- 读取 `nw_usage_events`
- 读取 `nw_wallets`
- 读取 `nw_wallet_ledger`
- 读取 `nw_providers`
- 展示 NW 影子消耗、请求数、Token、钱包余额、最近账本流水、Provider Adapter
- 页面文案明确：当前是 shadow billing，不影响正式真实余额

正式包构建脚本同步修正：

- 正式包加入 `provider_adapter.py`
- 正式包加入 `usage_wallet.py`
- 正式包移除 preview-only 脚本：
  - `preview_release_update.py`
  - `deploy-preview-package.sh`

## 阶段12.5：极端场景压测与安全检查

新增脚本：

`/Users/ahner/projects/nw-api-stack-public/scripts/stage12_extreme_checks.py`

已验证：

- 重复 request_id：只写 1 条 usage event
- 重复 request_id：只写 1 条 wallet ledger
- 20 并发请求：全部 HTTP 200
- 20 并发请求：usage_events 至少写入 20 条
- Key 禁用后：HTTP 401 `ACCOUNT_DISABLED`
- 无效 Key：HTTP 401
- 公开页面：未发现 `sk-` / `Bearer` / `xai-` / `DASHSCOPE_API_KEY` 泄漏

执行结果：`EXTREME_OK`

## 阶段13：RC Gate / 正式迁移准备

已构建 RC 包，但未发布 GitHub Release、未更新正式站。

RC 包：

`/tmp/hermes-nwapi-stage12-13-20260707-102128/dist/nw-api-V0.0.3-rc.1-linux-amd64.tar.gz`

SHA256：

`c7ba3e3a571357ca462fe33d888a032a6f6f4dc53d0cefc7875983eba2a4b030`

Gate 结果：

- 本地测试：42/42 通过
- py_compile：通过
- secret scan：0
- tar listing：未发现 phase0 / preview / mock / test / .git / __pycache__
- manifest 可解析
- `PACKAGE_GATE_OK`

## 预览验证

9088 服务状态：

- nginx active
- xapi-data active
- xapi-portal active
- xapi-v1-wrapper active

## 正式站只读检查

正式站未更新，仅检查状态：

- `xapi-portal` active
- `xapi-v1-wrapper` active
- `caddy` active
- `xapi-data` inactive
- `https://of.ahner.cn/login` 返回 HTTP 200

说明：正式站当前 login 可访问；但 `xapi-data` inactive 需要在正式迁移前单独处理或确认是否已被当前正式架构替代。

## 边界

- 本轮没有发布 GitHub Release。
- 本轮没有执行正式站部署。
- 阶段13已完成“可迁移 RC Gate + 正式只读评估”，正式切换需下一步明确执行生产更新。
