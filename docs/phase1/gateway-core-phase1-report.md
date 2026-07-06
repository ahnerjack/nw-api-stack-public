# NW-API 阶段 1 Gateway Core 骨架报告

日期：2026-07-06
基准：阶段 0 检查点 `phase0-guardrails-20260706`
当前目标：只抽取低风险纯函数骨架，不改变 `/v1` 对外行为，不触碰正式站。

## 1. 本批目标

阶段 1 第一刀不做大重构，只把 `xapi-v1-wrapper.py` 中最稳定、无 I/O 副作用的逻辑抽到 Gateway Core：

- request_id 生成与校验
- 客户端 IP 解析
- Bearer token 解析
- JSON body 中 model 提取
- `/v1/models` 响应 payload 构造
- 上游请求 header 过滤
- hop-by-hop response header 过滤
- chunk 编码
- 是否使用 chunked downstream 的判断

保持不变的边界：

- `Handler` 生命周期
- `log_access()`
- SQLite 查询
- `post_json()` 到 xapi-data
- 上游转发与 socket 流式读取
- 正式部署服务

## 2. 新增模块

`services/xapi-v1-wrapper/gateway_core.py`

该模块为纯函数/数据结构模块，不访问：

- 网络
- 文件系统
- SQLite
- systemd
- 环境变量

当前导出：

- `ErrorResponse`
- `NormalizedRequest`
- `make_request_id_from_headers()`
- `client_ip_from_headers()`
- `extract_bearer_token()`
- `model_from_json_body()`
- `normalize_request()`
- `build_model_list_payload()`
- `proxy_request_headers()`
- `should_forward_response_header()`
- `should_chunk_downstream()`
- `encode_chunk()`

其中部分函数已被 wrapper 使用，部分作为后续策略管道预留。

## 3. wrapper 改动

`services/xapi-v1-wrapper/xapi_v1_wrapper.py` 仍是运行入口。

本批只做等价替换：

| 原位置 | 新逻辑 | 行为变化 |
|---|---|---|
| 内联 request_id 校验 | `make_request_id_from_headers()` | 基本等价，header 匹配更稳 |
| 内联模型列表 JSON | `build_model_list_payload()` | 等价，仍按模型名排序 |
| 内联请求 header 过滤 | `proxy_request_headers()` | 等价 |
| 内联 response header 判断 | `should_forward_response_header()` | 等价 |
| 内联 chunk 编码 | `encode_chunk()` | 字节级等价 |
| 内联 chunked 判断 | `should_chunk_downstream()` | 等价 |

为保证单文件部署结构，wrapper 使用：

`sys.path.insert(0, str(Path(__file__).resolve().parent))`

这样 `/opt/xapi-v1-wrapper/xapi_v1_wrapper.py` 与同目录 `gateway_core.py` 可以直接导入。

## 4. 部署/打包更新

已更新：

- `scripts/build-release-package.py`
  - 发布包包含 `services/xapi-v1-wrapper/gateway_core.py`

- `scripts/deploy-aliyun.sh`
  - 安装 `gateway_core.py` 到 `/opt/xapi-v1-wrapper/gateway_core.py`

- `scripts/deploy-phase0-preview-host.sh`
  - 安装 `gateway_core.py` 到 `/opt/nw-api-phase0-preview/xapi-v1-wrapper/gateway_core.py`

## 5. 测试结果

### 本地测试

| 测试 | 结果 |
|---|---:|
| phase1 core 单测 | 9/9 OK |
| phase0 wrapper 回归 | 10/10 OK |
| Python 编译 | OK |
| deploy 脚本语法 | OK |
| wrapper 文件路径导入 | OK |
| release package 构建 | OK |
| 包内包含 gateway_core.py | OK |

### 9088 预览环境

已部署到：

`http://10.0.1.66:9088/`

部署后多轮测试：

| 项目 | 结果 |
|---|---:|
| 预览环境 10 轮功能测试 | 50/50 OK |
| 并发无效 key | 30/30 OK |
| 四个预览服务 active | OK |

### 部署后性能基线

| 场景 | 请求数 | 状态码 | 平均 ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---|---:|---:|---:|---:|
| 首页 `/` | 30 | 200 x30 | 19.89 | 19.33 | 28.95 | 33.14 |
| 后台 `/nv-api/` | 30 | 200 x30 | 22.77 | 22.31 | 26.58 | 26.94 |
| 无效 key `/v1/models` | 30 | 401 x30 | 25.02 | 24.32 | 30.81 | 31.50 |
| 无效 key `/v1/chat/completions` | 30 | 401 x30 | 26.22 | 24.97 | 31.58 | 68.05 |
| 并发无效 key workers=10 | 30 | 401 x30 | 59.10 | 36.10 | 177.88 | 197.72 |
| 并发无效 key workers=30 | 60 | 401 x60 | 122.45 | 100.18 | 279.40 | 387.35 |
| 并发首页 workers=30 | 60 | 200 x60 | 59.89 | 26.21 | 152.64 | 156.56 |

与阶段 0 基线相比，低并发行为基本稳定；30 并发波动仍属于 Python stdlib 预览网关范围。

## 6. 外部 agent 复核

已调度：

- bbq：阶段1边界复核 + 部署前复核
- OpenCode：只读复核抽取改动

复核结论：

- 当前抽取边界正确。
- 不应在本批触碰日志、DB、网络转发、Handler 生命周期。
- 导入路径、打包、deploy 已满足当前部署模型。
- phase0 行为兼容，测试通过。

## 7. 已发现并处理的问题

1. 文件路径导入失败

问题：阶段0测试通过 `importlib.util.spec_from_file_location()` 加载 wrapper 时，`gateway_core` 不在 `sys.path`。

处理：wrapper 启动时把自身目录加入 `sys.path`。

2. 部署包缺依赖风险

问题：wrapper 改为依赖 `gateway_core.py`，发布/部署必须带上。

处理：发布包、正式部署脚本、预览部署脚本均已加入安装。

3. 远端 py_compile 权限提示

问题：普通用户在 `/opt/nw-api-phase0-preview/xapi-v1-wrapper/__pycache__` 写 pyc 权限不足。

影响：不影响服务运行；服务以 root 运行，且源码已经本地编译验证。

处理建议：后续远端手工编译用 `sudo python3 -m py_compile` 或 `PYTHONDONTWRITEBYTECODE=1`。

## 8. 剩余风险

1. Gateway Core 仍只是纯函数骨架，还没有策略管道。
2. Auth / Model / Risk 仍散落在 wrapper Handler 中。
3. 流式转发仍依赖 CPython `response.fp.raw._sock` 私有属性。
4. 当前仍是 Python stdlib HTTP server，不是未来正式 Gateway Core 最终形态。
5. UI 尚未优化，只保留路线图。

## 9. 下一步建议

阶段 1 下一刀：

- 引入 `PolicyResult`
- 抽 `AuthPolicy` 外壳，但把 `post_json('/keys/verify')` 作为注入依赖
- 抽 `ModelAllowPolicy` 外壳，但保留 `allowed_models()` 查询函数
- 抽 `IPRiskPolicy` 外壳，但保留 SQLite 查询函数
- 每抽一步跑：phase1 core、phase0 wrapper、9088 多轮测试

不要一次性改完整网关，也不要现在换 FastAPI。
