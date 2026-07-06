# 阶段1 Gateway Core 骨架抽取复核报告

> 只读复核，不改文件。基准：`services/xapi-v1-wrapper/xapi_v1_wrapper.py`（403行）。
> 验证：阶段0回归测试 `python3 tests/phase0/test_v1_wrapper_regression.py` → **10/10 通过**。

---

## 一、可抽取模块（按优先级排序）

### 1.1 请求规范化层（NormalizedRequest） — 最高优先级

当前 wrapper 的 `proxy()` 方法（L215-281）里把请求拆解分散在方法体中：

| 当前代码位置 | 职责 | 可抽为 |
|---|---|---|
| L105-107 `client_ip(handler)` | 从 XFF 取客户端 IP | `NormalizedRequest.client_ip` |
| L229-233 `Authorization` 解析 | Bearer token 提取 | `NormalizedRequest.api_key` |
| L255-258 `read_body()` + JSON 解析 | 请求体解析、model 提取 | `NormalizedRequest.body, .model` |
| L216-217 request_id 生成 | ID 生成/透传 | `NormalizedRequest.request_id` |

**建议抽取为一个纯数据类**：

```python
@dataclass
class NormalizedRequest:
    method: str
    path: str
    headers: dict
    body: bytes | None
    parsed_body: dict | None
    model: str
    api_key: str
    client_ip: str
    request_id: str
```

**抽取收益**：后续 FastAPI/WSGI 适配器只需各自实现 `from_http_request(raw)` 工厂方法，核心策略函数只消费 `NormalizedRequest`。

**测试点**：
- `NormalizedRequest` 能从 mock HTTP headers 正确构造
- XFF 第一项优先 → 回退 socket IP
- Bearer token 解析空/auth 不含 Bearer → 返回空字符串
- JSON body 解析失败 → `parsed_body=None`，不崩

### 1.2 策略管道（Policy Pipeline） — 核心骨架

当前 `proxy()` 里的校验逻辑是线性的 if-return 链（L224-265），天然适合抽成策略管道：

```text
AuthPolicy → IPRiskPolicy → ModelAllowPolicy → (future: RateLimitPolicy)
```

每个策略接口：

```python
class PolicyResult:
    allowed: bool
    error_code: str      # 如 'INVALID_API_KEY'
    error_message: str
    http_status: int     # 401/403/429/502
    context: dict        # 附加信息，供后续策略/log使用

class Policy(ABC):
    def evaluate(self, req: NormalizedRequest, ctx: dict) -> PolicyResult: ...
```

**可抽取的具体策略**：

| 策略 | 来源代码 | 纯度 | 依赖 |
|---|---|---|---|
| `AuthPolicy` | L229-243 + `post_json('/keys/verify')` | 中 | 需注入 `key_verifier` 回调 |
| `IPRiskPolicy` | L224-227 + `risk_allowed(ip)` | 高 | 纯函数，只依赖 SQLite 连接 |
| `ModelAllowPolicy` | L260-262 + `allowed_models(uid)` | 中 | 需注入 `model_resolver` 回调 |

**关键设计决策**：上述策略当前依赖外部 I/O（SQLite、HTTP 调用 xapi-data）。抽取策略接口时，把 I/O 依赖注入为回调/接口，策略本身只做判断逻辑：

- `risk_allowed(ip)` 已经是一个纯函数（L110-136），可直接抽为策略对象，只需把 SQLite 连接注入。**这是最干净的抽取目标**。
- `allowed_models(portal_user_id)` 同理（L79-90），查询逻辑纯粹。
- `post_json('/keys/verify')` + `portal_user_by_sub2()` 需要组合成两步，建议封装为 `KeyVerifier` 接口。

**测试点**：
- `IPRiskPolicy`：allow 规则优先级 > block；无规则默认放行；无效 IP 格式不崩
- `ModelAllowPolicy`：用户有专属配置用专属，否则回退全表
- `AuthPolicy`：有效 key → pass；无效/禁用/超配额 → 对应错误码
- 管道短路：Auth 失败不再跑后续策略

### 1.3 错误响应工厂（ErrorResponseFactory） — 已近完成

`json_error(handler, code, message, status)`（L58-66）已经是纯函数逻辑，但耦合了 `handler.wfile`。

**建议**：抽为纯数据构造 + HTTP 渲染分离：

```python
def error_response(code: str, message: str, status: int) -> dict:
    return {"code": code, "message": message}

def render_error(handler, error: dict, status: int): ...
```

当前所有错误码（L58 注释定义 + L226-281 实际使用）已经一致，可以直接做映射表：

```python
ERROR_CODES = {
    "IP_BLOCKED": (403, "Client IP blocked"),
    "INVALID_API_KEY": (401, "Missing API key"),
    "ACCOUNT_DISABLED": (403, "Account disabled"),
    "MODEL_NOT_ALLOWED": (403, "Model not allowed"),
    "UPSTREAM_TUNNEL_DOWN": (502, "Upstream tunnel unavailable"),
    "UPSTREAM_TIMEOUT": (504, "Upstream timed out"),
    "UPSTREAM_ERROR": (502, "Upstream error"),
}
```

**测试点**：
- 所有错误码返回正确 HTTP status
- JSON body 结构一致：`{"code": "...", "message": "..."}`
- Content-Type 始终 `application/json; charset=utf-8`

### 1.4 上游转发与流式处理

`forward_to_upstream()`（L299-345）和 `stream_response()`（L347-377）是 wrapper 的核心转发逻辑。

**可抽取部分**：
- **Hop-by-hop header 过滤**（L35-39 的 `HOP_BY_HOP_HEADERS` + L319-328 的过滤逻辑）→ 纯函数 `filter_hop_by_hop(headers: dict) -> dict`
- **流式 chunk 编码**（L368-376）→ 独立函数 `encode_chunk(data: bytes) -> bytes`
- **上游错误分类**（L379-395 `forward_http_error`）→ 纯映射 `upstream_error_code(http_status: int) -> str`

**不可抽取部分**：
- `urllib.request.urlopen()` 的直接调用 — 这是传输层，留在 Handler 里
- `select.select([sock], ...)` — 与 Python stdlib HTTP 实现紧耦合
- `self.wfile.write()` — HTTP handler 特定

**测试点**：
- hop-by-hop header 过滤不遗漏 `connection`/`transfer-encoding`/`content-length`
- 流式编码正确：chunk-size hex + CRLF + data + CRLF，末尾 `0\r\n\r\n`
- 上游 429 → `UPSTREAM_RATE_LIMIT`，502/503/504 → `UPSTREAM_UNAVAILABLE`

### 1.5 模型列表合成

`respond_models()`（L287-297）逻辑简单但可复用：

```python
def build_model_list(models: list[str]) -> dict:
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "created": 0, "owned_by": "nw-api"}
            for m in sorted(models)
        ]
    }
```

**测试点**：
- 输出格式符合 OpenAI `/v1/models` 规范
- 按字母排序

---

## 二、不可碰的边界

### 2.1 绝对不能改的

| 边界 | 原因 | 代码位置 |
|---|---|---|
| `log_access()` 写入 portal SQLite | 改了会破坏正式环境的日志链路，且 portal 依赖该表做管理后台展示 | L139-167 |
| `post_json()` 的 xapi-data 调用签名 | xapi-data 是独立服务，换签名会导致所有 `/v1` 请求验证失败 | L69-76 |
| `allowed_models()` / `portal_user_by_sub2()` 的 SQLite 查询 | 直接绑定 portal DB schema，修改后 portal 和 wrapper 数据不同步 | L79-90, L93-102 |
| `upstream_reachable()` 的 TCP 预检 | 去掉会导致上游不通时长时间挂起而非快速返回 502 | L170-180 |
| `Handler.end_headers()` 中注入 `X-Request-Id` | 这是阶段0补的 request_id，必须保持在所有响应头中 | L190-194 |
| `BaseHTTPRequestHandler` 的生命周期方法（`do_GET`/`do_POST`/`do_HEAD`/`do_OPTIONS`） | 这些是 stdlib HTTP server 契约，Gateway Core 不应该侵入 | L196-213 |

### 2.2 阶段1不要碰的

| 边界 | 原因 |
|---|---|
| xapi-data 的 `shell=True` + psql 拼接 | 风险登记 R1，但需要单独阶段处理，不是 Gateway Core 范畴 |
| portal 1560行单体 | 风险 R2，属于 UI/架构阶段 |
| SQLite 多进程并发 | 风险 R3，需要迁移到 Postgres 或日志队列 |
| `risk_rules` 只处理 `kind=ip` | 风险 R7，功能缺口不是架构问题 |
| 正式站 systemd unit / Caddy 配置 / 部署脚本 | 阶段1只在本地/预览环境验证 |
| 正式线上端口 18182 / 18180 / 18181 | 不动，不在本地启动占用这些端口 |
| `xapi_portal.py` 任何代码 | portal 不在 Gateway Core 范畴 |

### 2.3 只能原地保留的（留在 Handler 适配器里）

- `ThreadingHTTPServer` 启动逻辑（L402-403）
- `self.wfile.write()` / `self.rfile.read()` — stdlib HTTP 特定
- `self.send_response()` / `self.send_header()` / `self.end_headers()` — HTTP 协议层
- `self.headers` / `self.path` / `self.command` — BaseHTTPRequestHandler 属性
- 环境变量读取（L23-33）— 配置注入点，但读取方式可保留

---

## 三、阶段0测试的保持策略

### 3.1 当前测试覆盖（10项）

| 测试 | 验证点 | Gateway Core 抽取后的对应 |
|---|---|---|
| `test_models` | GET /v1/models 返回用户模型 | `build_model_list()` + `ModelAllowPolicy` |
| `test_missing_key` | 无 Authorization → 401 | `AuthPolicy` |
| `test_invalid_key` | 无效 Key → 401 | `AuthPolicy` + `KeyVerifier` |
| `test_model_not_allowed` | 未授权模型 → 403 | `ModelAllowPolicy` |
| `test_non_stream_chat` | 非流式透传 | `NormalizedRequest` + 转发 |
| `test_stream_chat` | SSE 流式透传 | 流式处理 + chunk 编码 |
| `test_upstream_429_passthrough` | 上游 429 透传 | `upstream_error_code()` |
| `test_head` | HEAD 请求 | 转发层 |
| `test_options` | OPTIONS 204 | 路由层 |
| `test_access_log_written` | 日志写入 + request_id | `log_access()` |

### 3.2 保持测试通过的约束

1. **测试直接 `import` wrapper 模块并修改模块级变量**（L158-165：`cls.wrapper.PORTAL_DB = ...`）。抽取后新模块的接口必须兼容这种 monkey-patch 方式。
2. **测试依赖 `cls.wrapper.Handler` 类存在**。如果 Handler 被重构为调用 Gateway Core，Handler 类必须仍然可被 ThreadingHTTPServer 实例化，且行为不变。
3. **测试依赖 `cls.wrapper.log_access()` 作为模块级函数**。如果移到新模块，需保留 re-export 或兼容 import 路径。
4. **Mock 数据（`MockDataHandler`、`MockUpstreamHandler`）测试了 `/keys/verify` 和上游代理的行为**。抽取 `KeyVerifier` 抽象后，mock 仍然必须能注入到测试中。

### 3.3 测试增强建议（阶段1应补）

不替代现有测试，新增：

1. **`NormalizedRequest` 单元测试**：XFF 多级、无 XFF、IPv6、异常 IP 格式
2. **策略管道组合测试**：多策略按序执行、短路逻辑
3. **`filter_hop_by_hop()` 边界测试**：全部 hop-by-hop header、自定义 header 保留
4. **`encode_chunk()` 规范测试**：空 chunk、大 chunk、最后 0 chunk
5. **错误码映射完整性**：所有注册错误码都有对应 HTTP status

---

## 四、建议的目录结构

```
services/xapi-v1-wrapper/          # 现有，保持不变（HTTP 适配器 + 入口）
  xapi_v1_wrapper.py               # 精简后的 Handler + 入口，委托给 core

gateway_core/                      # 新增，纯 Python 包
  __init__.py
  request.py                       # NormalizedRequest, from_http_handler()
  policies.py                      # AuthPolicy, IPRiskPolicy, ModelAllowPolicy
  errors.py                        # error_response(), ERROR_CODES
  headers.py                       # filter_hop_by_hop()
  streaming.py                     # encode_chunk(), StreamWriter protocol
  models.py                        # build_model_list()

tests/phase1/                      # 新增
  test_request.py
  test_policies.py
  test_errors.py
  test_streaming.py
  test_models.py
```

**注意**：`log_access()`、`post_json()`、`allowed_models()`、`portal_user_by_sub2()`、`upstream_reachable()` 这些带外部 I/O 的函数暂留 wrapper 内，通过依赖注入供 Gateway Core 策略调用。

---

## 五、抽取顺序建议

```
第1步：NormalizedRequest 纯数据类 + from_http_handler() 工厂
       → 跑阶段0测试，确认 10/10

第2步：error_response() + ERROR_CODES 映射表 + json_error() 重构
       → 跑阶段0测试，确认错误码行为不变

第3步：filter_hop_by_hop() + encode_chunk() 纯函数
       → 跑阶段0测试，确认流式透传不变

第4步：IPRiskPolicy 策略对象（risk_allowed 逻辑搬家）
       → 跑阶段0测试，确认 IP 拦截不变

第5步：AuthPolicy + ModelAllowPolicy（注入 KeyVerifier/ModelResolver 接口）
       → 跑阶段0测试，确认认证/授权不变

第6步：Handler.proxy() 重构为调用策略管道
       → 跑阶段0测试 + 阶段1新测试，全部通过
```

每步只移一个模块，每步跑全量测试。任何一步失败就回退该步。

---

## 六、风险与注意事项

1. **SQLite 连接管理**：当前 wrapper 每次调用 `allowed_models()`/`risk_allowed()`/`portal_user_by_sub2()` 都独立 `sqlite3.connect()` + `close()`。抽取后如果引入连接复用要注意线程安全（当前 `ThreadingHTTPServer` 每请求一线程）。
2. **`_REQUEST_CONTEXT` thread-local**：当前 request_id 通过 `threading.local()` 传递（L43）。如果在策略管道中需要 request_id，保持 thread-local 模式，不要引入全局状态。
3. **json.loads 失败静默**：当前 L263 `except json.JSONDecodeError: pass` 是已知行为缺口（R6）。不要趁机修 bug — 修 bug 和架构抽取分开做。
4. **`forward_to_upstream()` 中的 `response.fp.raw._sock`**（L348）：这是 CPython stdlib 私有属性访问，非常脆弱。不要把这行移到 Gateway Core，它必须留在 HTTP 适配器里。
5. **预览环境阶段0测试**：`tests/phase0/test_v1_wrapper_regression.py` 设为 CI 门禁，任何 Gateway Core 改动提交前必须先跑。

---

*复核完成时间：2026-07-06*
*分支：public-sanitized*
*基准 commit：2975bbc*
