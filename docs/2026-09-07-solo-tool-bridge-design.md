# SOLO 工具调用灰度接入设计

## Goal

让带调用方工具协议的请求通过 `llm_utils_chat + solo_work_lite` 获得结构化 `tool_calls`，由 DSH 在本机执行工具；普通请求继续使用现有 remote 路线。

## Scope

- 新增独立 `solo` 传输函数，不替换现有 raw/remote 实现。
- 仅在请求声明 `tools`、`tool_choice`、工具续轮历史时选择 solo。
- 由 relay 转换 OpenAI 消息、工具 schema 和工具历史为 Trae SOLO 格式，再复用现有 SSE 翻译器输出 OpenAI `tool_calls`。
- 增加显式环境开关：可关闭 solo 工具路由，也可选择失败后回退 remote；默认不回退，避免云端沙箱伪造本地工具结果。
- 普通无工具请求、raw 路线、remote 路线的既有行为不变。

## Files

- `src/trae_client.py`：构造 SOLO body、发送 `llm_utils_chat` 请求、补齐 SOLO headers。
- `src/main.py`：增加 solo 执行器和带工具请求的路由选择。
- `tests/test_main_smoke.py`：覆盖路由选择、body 结构和可配置回退。
- `CHANGELOG.md`：记录灰度通道、验证结果和限制。
- `README.md`：记录配置开关和工具执行边界。

## Data flow

1. OpenAI/Responses facade 接收 `messages`、`tools`、`tool_choice` 和可选 `client_context`。
2. `_dispatch_chat` 判断工具协议；普通请求留在 remote，工具请求在开关开启时进入 solo。
3. solo transport 将每个文本 content 转为 `{type: "text", text: ...}`，assistant `tool_calls[].function` 改为上游 `function_call`，工具 schema 的 `parameters` 序列化为 JSON 字符串，并设置 `function=solo_work_lite`、`config_name`、`model`。
4. Trae SSE 的 `output.tool_calls`/`function_call` 交给既有 SSE translator，返回 OpenAI `delta.tool_calls` 或非流式 `message.tool_calls`。
5. DSH 执行工具并回传 `role=tool`；下一轮携带同一会话 ID和工具历史再次走 solo。
6. solo 失败默认直接返回错误；只有 `TRAE_SOLO_TOOLS_FALLBACK_REMOTE=true` 时才允许回到 remote。

## Tasks

1. 先增加一个会因缺少 solo body 构造函数而失败的单元测试。
2. 实现 SOLO body 和请求发送，确保 stream 强制为 true，非流式由现有聚合器处理。
3. 增加 solo 执行器并接入工具请求路由。
4. 增加失败回退和配置读取测试。
5. 更新 README/CHANGELOG。
6. 运行语法检查、相关测试和完整测试。
7. 使用短请求做一次真实 solo 文本验证，再做一次只读工具调用闭环；失败立即停用实验并恢复 remote。

## Failure modes

- raw v1/v2 的 `record not found` 不影响新 solo 路线。
- SOLO 返回 4xx、业务 error 或首事件前 EOF 时直接报告；默认不重放，避免重复扣费。
- SOLO SSE 没有 terminal event 时沿用既有 `IncompleteUpstreamResponse` 逻辑。
- 工具调用只转发给 DSH，不在 relay 或 Trae 云端执行本机文件/Shell 工具。
- 当前账号、模型权益或上游限流可能导致 solo 失败；可通过单个环境开关关闭。

## Verification

- 单元测试验证请求 body 的 `function`、`config_name`、消息 content 数组、`function_call` 历史和工具 schema。
- 路由测试验证无工具走 remote、带工具走 solo、默认不回退、显式开关才回退。
- 全量 `python -m pytest -q`。
- 真实验证最多一条短文本和一轮只读工具调用，不做并发或持续探针。

## Rollback

- 不改现有 `.env` 的 `UPSTREAM_MODE=remote`。
- 设置 `TRAE_SOLO_TOOLS_ENABLED=false` 即恢复所有请求的原有 remote 路由。
- 删除本轮提交即可完全撤销；不删除账号凭据和运行数据。
