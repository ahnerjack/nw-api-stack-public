# 当前数据流与服务图

## 1. 服务拓扑

```text
Browser / API Client
        |
        v
Caddy/Nginx/Public HTTPS
        |
        +--> xapi-portal :18180
        |      - public pages
        |      - login/session
        |      - dashboard/admin
        |      - SQLite: /opt/xapi-portal/xapi_portal.db
        |      - calls xapi-data
        |
        +--> xapi-v1-wrapper :18182
        |      - Bearer API key verify via xapi-data
        |      - IP risk rules via portal SQLite
        |      - model allowlist via portal SQLite
        |      - upstream proxy to Sub2API :18066
        |      - access logs into portal SQLite
        |
        +--> static home/nav pages

xapi-data :18181
        |
        +--> docker exec sub2api-postgres psql
        +--> docker exec sub2api-redis redis-cli FLUSHDB
        +--> docker restart sub2api in selected mutations
```

## 2. 端口矩阵

| 端口 | 进程 | 来源 | 用途 |
|---|---|---|---|
| 18180 | xapi-portal | `xapi_portal.py` | 门户与后台 |
| 18181 | xapi-data | `xapi_data_api.py` | Sub2API 数据桥 |
| 18182 | xapi-v1-wrapper | `xapi_v1_wrapper.py` | `/v1` 策略 wrapper |
| 18066 | Sub2API / upstream | 外部依赖 | OpenAI-compatible 上游和可能的 `/xapi-data` 转发 |

## 3. 数据存储

| 存储 | 当前用途 | 风险 |
|---|---|---|
| SQLite `/opt/xapi-portal/xapi_portal.db` | portal 用户映射、模型价格、风控、日志、通知、套餐 | 多进程读写，未来并发和迁移风险 |
| Sub2API Postgres | 上游用户、Key、usage_logs、channel_model_pricing | xapi-data 通过 shell + psql 操作，强依赖表结构 |
| Sub2API Redis | Key/用户缓存 | 修改 Key/用户后需要清缓存 |
| 内存 dict `SESS` | portal session | 重启丢失，无跨进程共享 |

## 4. 部署与发布链路

- 仓库当前只提供 `systemd/xapi-portal.service` 和 `systemd/xapi-data.service`。
- `xapi-v1-wrapper` 有 README 和 deploy 安装逻辑，但仓库已补 `systemd/xapi-v1-wrapper.service` 模板。
- `scripts/deploy-aliyun.sh` 会安装 portal、wrapper、静态页，并重启 portal/wrapper/Caddy。
- 正式环境只能在明确授权后更新；阶段 0 只做本地仓库和 mock 测试。
