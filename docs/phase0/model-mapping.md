# 当前模型映射清单

## 1. Portal 默认模型

来源：`xapi_portal.py:init_db()`

| 模型 | 输入价 | 输出价 | 缓存价 | 说明 |
|---|---:|---:|---:|---|
| `gpt-5.5` | 35 | 210 | 3.5 | 主力模型 |
| `gpt-5.4` | 17.5 | 105 | 1.75 | 均衡模型 |
| `gpt-5.4-mini` | 5.25 | 31.5 | 0.525 | 经济模型 |

## 2. xapi-data 价格来源

来源：`xapi_data_api.py:/xapi-data/pricing`

当前从 Sub2API Postgres `channel_model_pricing` 读取：
- `gpt-5.5`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-image-2`

返回单位标注为 `USD per 1M tokens`。

## 3. /v1/models 暴露逻辑

来源：`xapi_v1_wrapper.py:respond_models()`

- 先按 portal 用户 ID 查 `user_models`。
- 如果用户没有专属模型配置，则回退到 `model_prices` 全表。
- 返回 OpenAI-compatible 结构：

```json
{
  "object": "list",
  "data": [
    {"id": "gpt-5.5", "object": "model", "created": 0, "owned_by": "nw-api"}
  ]
}
```

## 4. 阶段 0 不能变更的兼容点

- 公开模型名暂时保持不变。
- `/v1/models` 仍只展示公开模型，不展示 Sub2API 内部渠道名。
- 不做 Provider 路由切换。
- 不做价格口径迁移。

## 5. 后续阶段要补的表

阶段 3 前需要把现在隐含的关系明确为：
- `public_models`
- `providers`
- `provider_models`
- `model_routes`
- `model_prices` with price snapshot
