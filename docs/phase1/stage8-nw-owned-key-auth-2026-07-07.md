# NW-API 阶段8：自有 Key + 自有鉴权接管

时间：2026-07-07
范围：9088 预览栈；正式站未更新。

## 目标

让 NW-API 开始拥有自己的 API Key 与鉴权入口：新建 Key 默认生成 `nwk_` 自有 Key，后端只保存 SHA256 hash；wrapper 对 `nwk_` Key 优先走本地 portal SQLite 校验，旧 `sk-` 上游 Key 兼容保留。

## 已实现

1. Portal 数据库新增 `nw_api_keys`
   - `key_hash` 唯一索引
   - `key_prefix/key_suffix` 用于掩码显示
   - `status/quota/quota_used/last_used_at/deleted_at`

2. Key 创建/轮换/禁用/删除改为 NW 自有 Key
   - 新 Key 前缀：`nwk_`
   - 完整 Key 只在创建/轮换时显示一次
   - 列表仅显示 prefix + `******` + suffix
   - 后端不保存明文 Key

3. Wrapper 鉴权接管
   - `nwk_` Key：本地查 `nw_api_keys` hash
   - 校验 key status、user status、quota
   - 命中后更新 `last_used_at`
   - 旧 `sk-` Key 继续走 `/keys/verify` 兼容路径

4. Gateway Core 调整
   - AuthPolicy 的 user loader 改为接收完整 auth_info
   - 支持 NW 自有 user_id 与旧 sub2 user_id 两种映射

5. 测试
   - 新增 phase0 wrapper regression：`test_models_with_nw_owned_key`
   - 本地单测覆盖 NW Key 调用和 last_used_at 更新

## 验证结果

本地：
- `python3 -m py_compile ...` 通过
- `tests.phase1.test_gateway_core` 通过
- `tests.phase0.test_v1_wrapper_regression` 39/39 通过
- `tests.phase0.test_release_versioning` 2/2 通过
- secret scan：0

预览 9088：
- services：nginx/data/portal/wrapper 全 active
- smoke：SMOKE_OK http://10.0.1.66:9088
- 新 NW Key `/v1/models`：HTTP 200
- 禁用后同 Key `/v1/models`：HTTP 401 ACCOUNT_DISABLED
- qqw 已切换到新 `nwk_` Key，`hermes -p qqw` 调用成功返回 ok

## 部署插曲

第一次用 `rsync --delete` 直接覆盖 `/opt/nw-api-phase0-preview`，导致预览目录结构短暂变成仓库结构，systemd 找不到旧路径；已立即按服务期望路径恢复：
- `/opt/nw-api-phase0-preview/xapi-data-mock/`
- `/opt/nw-api-phase0-preview/xapi-portal/`
- `/opt/nw-api-phase0-preview/xapi-v1-wrapper/`

恢复后所有服务 active，smoke 通过。备份位置：`/tmp/nwapi-stage8-backup-20260707-093613`。

## 边界

阶段8 只接管 Key/鉴权入口；尚未完成自有计费扣费、自有请求成本计算、自有钱包。
下一阶段应做阶段9：自有用量流水 + 计费接管。
