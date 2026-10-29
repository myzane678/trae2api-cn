# Trae2API CN（本地维护版）

> WorkBuddy / Trae CN 的 OpenAI 兼容反向代理（Python / FastAPI）。多账号、工具调用、
> 流式输出、桌面快捷方式启动、按账号统计与独立 API Key。
>
> **仅供学习和技术交流使用，请勿用于任何商业用途。** 使用本项目需自行遵守 Trae /
> CodeBuddy 的服务条款，一切使用风险由使用者自行承担。

## 项目来源与致谢

本项目基于 [autumnsentiment/Trae2api-cn](https://github.com/autumnsentiment/Trae2api-cn)
（MIT License）修改而来，感谢原作者的工作。本地维护版相对上游的主要改动
（SOLO 通道、多账号、控制台、Windows 部署链路、按账号 API Key 等）见
[CHANGELOG.md](CHANGELOG.md)。

控制台布局与启动链路参考了 [myzane678/WorkBuddy-Proxy](https://github.com/myzane678/WorkBuddy-Proxy)
（MIT License，WorkBuddy CN 反向代理），感谢其侧边栏分组、看门狗与快捷方式启动的设计。

## 贡献者

- [autumnsentiment](https://github.com/autumnsentiment) — 上游 Trae2api-cn 原作者
- [myzane678](https://github.com/myzane678) — 本地维护版（WorkBuddy-Proxy 作者），
  控制台布局与启动链路借鉴自其 WorkBuddy-Proxy

| 本地部署卡（2026-10-10） | 值 |
|---|---|
| 服务地址 | `http://127.0.0.1:8092/v1`（OpenAI Chat Completions 兼容 + Codex Responses API） |
| 鉴权 | `Authorization: Bearer <你的 RELAY_API_KEYS>`（配置在 `.env`） |
| 控制台 | `http://127.0.0.1:8092/web/login`（账号/积分/签到/白名单勾选/消费记录含首字耗时） |
| 启停 | `launch.vbs`（桌面快捷方式，隐藏启动 + 常驻看门狗）/ `start-trae2api.cmd`（控制台窗口）/ `stop-trae2api.cmd`（连看门狗一起停） |
| 登录 | 控制台授权按钮（或 `start-trae2api-login.cmd` 先行）；token 自动续期 |
| 白名单 | 控制台勾选管理（data/model-allowlist.json）；**不勾 = 放行全部**；`/v1/models?all=1` 查完整目录（当前 25 个） |
| 工具调用 | ✅ SOLO 原生通道：请求体原生 `tools`/`tool_choice`，SSE `event:output.tool_calls` 结构化返回，标准 OpenAI 流式 `tool_calls` delta。**25 个模型全部实测通过**，含 3 工具并行调用（参数 JSON 合法、index 分组正确） |
| 上游模式 | `UPSTREAM_MODE=solo`（唯一路由）：`llm_utils_chat` + `function=solo_work_lite`，`X-Ide-Version: 0.1.52` 解锁现役模型 |
| 模型 | 25 个（glm-5.x、DeepSeek-V4 系列、Doubao-Seed-2.x、kimi-k3、qwen3.8-max、minimax-m3、step-5-preview、mimo-v2.6…），控制台勾选管理 |
| 积分 | 全部为通用积分（Work 专属已升级合并，TraeCode/TraeWork 通吃），SOLO 通道消耗通用积分；实测费率 ≈ 0.09 分/千token（豆包） |
| 并发 | 每账号信号量上限 5（`TRAE_SOLO_MAX_PARALLEL` 可调）+ 冷却状态机（429→60s、1005→12h、其他错误→10m，成功即解冻） |

### 模型可用性实测（2026-10-10，25 个全测）

**工具调用：25/25 全部通过**——这些模型在工具能力上无差异。

**长文收尾：23 个正常，1 个反复截断。**

| 模型 | 长文收尾 | 耗时 | 费率 | 备注 |
|---|---|---|---|---|
| `deepseek-v4.1-flash` | ❌ **4/4 截断** | 45s | 0.15 | **不要用**：长文结尾停在词中间（复测 3/3 一致） |
| `mimo-v2.6-flash` | ✅ | 70s | 0.06 | 最便宜，思考链短（41-98 字） |
| `step-5-preview` | ✅ | 32-84s | 0.48 | 综合稳定 |
| `glm-5.3-flash` | ✅ | 138s | 0.06 | ⚠️ 思考链极长（单轮 2000+ 字），交互观感差 |
| `glm-5.3-flashx` | ✅ | 29s | 0.31 | |
| `kimi-k3` / `kimi-k2.7-code` / `kimi-k2.6` | ✅ | 27-87s | 0.75-1.83 | |
| `DeepSeek-V4-Flash` / `-Official` | ✅ | 31-38s | 0.2 | 与 `deepseek-v4.1-flash` 是两个模型，这两个正常 |
| `DeepSeek-V4-Pro` / `-Official` | ✅ | 57-120s | 0.72 | |
| `qwen3.8-max` / `qwen-3.7-plus` | ✅ | 32-129s | 0.25-1.5 | |
| `minimax-m3` | ✅ | 27s | 0.26 | |
| `Doubao-Seed-2.x` 系列 | ✅ | 145-388s | 0.08-0.39 | 慢，但完整 |
| `glm-5` / `glm-5.2` / `glm-5.3` / `glm-5-turbo` | ✅ | 67-284s | 0.7-0.78 | |

**结论：唯一确认有缺陷的是 `deepseek-v4.1-flash`，长文必截断。选模型时避开它即可。**

### 已知问题

- **`deepseek-v4.1-flash` 长文截断**：4/4 复现，结尾停在词中间（无句号），`finish_reason=stop`。上游计费 token 与实际发出字数一致（1.67-1.72 chars/token，中文健康值），**不是中转丢内容，是模型生成侧提前停笔**。换 `function` 值不解决。控制台「请求日志」的「结尾未完」徽章可识别此类情况。
- **`glm-5.3-flash` 思考链过长**：单轮思考可达 2000+ 字，期间正文零输出。zcode 不显示 `reasoning_content`（bundle 内 0 次出现），所以体感像"卡住不吐字"，实际是思考中。
- **工具调用轮次正文为空是正常行为**：模型决定调工具时 `content=0` + `finish_reason=tool_calls`，正文要等工具结果回传后的下一轮才产生。
- **路由器 DNS 污染（本机环境）**：`192.168.1.1` 把 `trae-api-cn.mchost.guru` 解析成 `127.0.0.1`，导致模型列表刷不出、请求超时。已在 `hosts` 固定为 `113.59.40.147`（备份 `hosts.bak-zcode-20261010`）。同后缀的 `api5-normal.mchost.guru` 不受影响。
- auto 模型 id 不可用（用显式模型）；Work 通道（`create_agent_task`）加密字段锁在本地进程不可反代。

**仅供学习使用。请勿用于商业用途。**

## 特点

- OpenAI 兼容接口：`GET /v1/models`、`POST /v1/chat/completions`、`POST /v1/responses`、`POST /v1/chat`、`POST /v1`
- 流式与非流式输出，SSE 心跳防止网关空闲断开
- 完整工具调用：`tools` / `tool_choice`（auto / none / required / 指定函数）/ `parallel_tool_calls`，流式输出标准 `delta.tool_calls`
- Codex Responses API：文本流、`function_call`、`custom_tool_call`、namespace 工具、`*_call_output` 续轮
- 单一上游通道：SOLO `llm_utils_chat`（原生工具调用）。历史通道 raw / remote / web / ide / cli 已移除
- 多账号：网页 OAuth 登录、手动添加凭证、顺序轮询 / 积分优先轮询、每账号并发槽位与排队
- 每日签到：一键签到、定时自动签到（北京时间）、9074 风控自动换设备 ID 并退避重试
- 积分与消费记录：按请求记录 tokens、单次积分、状态、首字耗时、收到字数
- 网页控制台：运行概览、账号池、模型白名单、请求日志、设置、连接测试
- **按账号区分**：概览/请求日志/签到记录/模型白名单/连接测试全部可按账号切换或筛选
- **按账号 API Key**：每个账号可绑定独立 key；绑定账号不可用时直接 503 报错（不自动换号），`.env` 全局 key 保持原有轮询行为

## 认证方式

| 方式 | 说明 |
|---|---|
| `auto` | 自动解密本地 Trae CN / SOLO CN 的 `storage.json` |
| `env` | 从 `.env` 读取 TRAE_TOKEN / TRAE_REFRESH_TOKEN / TRAE_USER_ID |
| `manual` | 网页抓包得到的 Cloud-IDE-JWT |
| `web-login` | 浏览器授权登录，打开 `http://服务器:端口/web/login` 后在页面完成授权 |

## 快速开始

```bash
cp .env.example .env
# 编辑 .env 配置 TRAE_AUTH_SOURCE
pip install -r requirements.txt
uvicorn src.main:app --host 127.0.0.1 --port 8092
```

Windows 本机推荐用一键启动（零黑窗，含 OAuth 助手）：

```cmd
start-trae2api.cmd
```

想要「双击桌面图标即用」的体验，先建一次快捷方式：

```cmd
create-desktop-shortcut.cmd
```

之后双击桌面的 `Trae2API` 即可：服务没起就隐藏拉起（约 3~20 秒）并以 Chrome 应用窗口
打开控制台；已在运行则秒开。`launch.vbs` 同时会拉起 `watchdog.ps1` 常驻探活
（每 5 秒查一次 `/healthz`，掉线自动重启，日志在 `data/watchdog.log`）。

停止：`stop-trae2api.cmd`（会先停看门狗再停服务，否则会被立刻拉起）。

## 配置

关键变量（完整列表见 `.env.example`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TRAE_AUTH_SOURCE` | `auto` | 认证来源 |
| `UPSTREAM_MODE` | `solo` | 上游通道；本版仅支持 `solo`（`llm_utils_chat` + `function=solo_work_lite`） |
| `TRAE_IDE_VERSION` | `0.1.52` | 客户端版本头，解锁现役模型；旧版本号报 4001 `param is invalid` |
| `TRAE_MODEL_ALLOWLIST` | 空 | 逗号分隔的模型白名单；留空 = 放行全部。控制台「模型白名单」页读写 `data/model-allowlist.json`，**不勾任何项 = 放行全部** |
| `TRAE_FETCH_MODEL_LIST` | `true` | 从上游拉真实模型目录（`get_detail_param`），关闭则用内置表 |
| `TRAE_SOLO_MAX_PARALLEL` | `5` | 每账号并发上限；超限排队 |
| `TRAE_MAX_COMPLETION_TOKENS` | `64000` | 单次输出 token 上限；Agent 模型最高 64K |
| `TRAE_VERBOSE_REASONING` | 空 | 设为 `1` 输出完整思考链；默认只保留压缩后的关键结论 |
| `SSE_HEARTBEAT_SECONDS` | `1` | 上游空窗时的 SSE 心跳间隔；`0` 为关闭 |
| `TRAE_USAGE_RECORDS_PATH` | `data/usage_records.json` | 消费记录持久化文件 |
| `RELAY_API_KEYS` | 空 | API 密钥鉴权（逗号分隔多个）；公网部署必须设置并配合 TLS |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 工具调用

工具调用使用标准 OpenAI 多轮协议。首次请求把工具 schema 和调用方环境放进请求：

```json
{
  "model": "step-5-preview",
  "stream": false,
  "messages": [{"role": "user", "content": "读取 README.md"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "read_file",
      "description": "读取调用方工作区中的文件",
      "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"]
      }
    }
  }],
  "tool_choice": "auto",
  "parallel_tool_calls": true,
  "client_context": {
    "workspace_path": "A:\ClaudeWorkspace",
    "system_type": "Windows 11"
  }
}
```

非流式响应使用 `message.content: null`、`message.tool_calls` 和 `finish_reason: "tool_calls"`；`function.arguments` 是 JSON 字符串。流式响应在 `delta.tool_calls` 中返回增量，客户端按 `index` 拼接，直到收到 `finish_reason: "tool_calls"`。

第二轮请求需带回完整历史（原 assistant 消息 + `role: "tool"` 结果 + 匹配的 `tool_call_id`），relay 会保持调用关联。

**relay 不执行工具**：请求中声明的工具由 API 调用方执行，relay 只转发调用与结果。`client_context` 只告诉模型真实环境，不能替代客户端工具实现。

### 传输实现说明

`solo` 模式调用 `POST /api/agent/v3/llm_utils_chat`，请求体使用 Trae SOLO 原生字段 `function=solo_work_lite`，工具 `parameters` 按 Trae 协议序列化为 JSON 字符串，请求头使用 Cloud-IDE-JWT、设备指纹和生产流量标识（`trae_solo.solo_headers`）。

上游事件词汇表（实测）：`output`（承载 `response` / `reasoning_content` / `tool_calls`）、`token_usage`、`done`、`metadata`、`timing_cost`、`extra_info`（模型原始思考链 JSON，relay 忽略）、`progress_notice`（排队/处理中）、`error`。

## 思考内容与思考强度

思考内容默认不对外输出到正文，通过 `reasoning_content` 字段分离返回。请求带 `thinking: {"type": "enabled"}`（或 `include_reasoning: true`）时返回 `reasoning_content`，正文 `content` 中不会出现思考文本。`TRAE_VERBOSE_REASONING=1` 可恢复完整思考链。

**注意**：部分客户端（如 zcode）不识别 `reasoning_content` 字段，思考内容对用户不可见但照常计费。模型在调工具前通常先思考一大段，此时正文为空——看起来像"卡住不吐字"，实际是思考中。

## 消费记录与截断取证

控制台「请求日志」按请求保存一行，包含模型、tokens、单次积分、状态、首字耗时（TTFB）、总耗时。积分优先级为：上游显式 usage、TraeWork 回合级 `credits_float`、同一账号请求前后的累计积分差值；无法安全归属时显示 `--`。

**「结尾未完」徽章**：长回复（≥200 字）在 `finish_reason=stop` 下，若最后一行以词字符结尾（而非句号等收尾符），或整行只有破折号，判定为「结尾未完」。工具调用轮次不参与判定（正文天然极短）。判定依据是**结尾形态**，不是 token/字符比值——实测上游计费 token 与实际发出字数一致（1.67-1.72 chars/token），不存在「生成了却扣着不发」。

## 使用注意事项

- **网络边界**：本项目设计为内网部署。不要把端口直接暴露到公网；如必须公网访问，请设置 `RELAY_API_KEYS` 并加 TLS 反代。
- **敏感数据**：`.env` 与 `data/`（`accounts.json`、`usage_records.json`）包含 JWT、刷新令牌和账号信息，已在 `.gitignore` 中排除，切勿提交或分享。
- **端点选择**：本版只有 `solo` 一条通道。`solo` 与上游 README 所称的 `ide` 通道**是同一个东西**（同一端点路径、同一 `function` 值），不存在「换到 IDE Agent 更好」这个选项。
- **工具执行在调用端**：relay 只转发工具调用和结果。模型声称"已下载 / 已写入"但本地没有文件，说明客户端没有真正执行工具。
- **并发**：每账号默认 5 个并行会话，槽位全满时排队。并发过高会触发上游限流（1005 / 429），账号进入冷却。
- **签到 9074**：9074 是上游风控码。relay 会自动轮换签到设备 ID 并指数退避重试；若长期失败，可在 `TRAE_CHECKIN_DEVICE_IDS_JSON` 中填入真实客户端的设备 ID。
- **合规**：使用本项目需自行承担账号风险，请遵守 Trae 服务条款。

## 项目结构与运维

```text
src/                    relay 服务与协议转换
  main.py               路由、SOLO 调度、网页控制台 API、签到与消费记录
  trae_solo.py          SOLO llm_utils_chat 协议、请求头、SSE 解析、模型目录
  sse.py                SSE 转换、思考分离与工具调用解析
  responses_api.py      Responses API 转换与会话缓存
  auth.py               账号存储、OAuth、令牌刷新
  model_limits.py       输出 token 上限钳制
  web/admin.html        控制台前端（独立文件，避免 f-string 转义坑）
tools/oneclick.py       Windows 零黑窗一键启动核心
tests/                  离线协议、流式和路由回归测试
launch.vbs              桌面快捷方式入口（隐藏启动 + 拉起看门狗）
start-trae2api.cmd      控制台入口
stop-trae2api.cmd       停止服务（含看门狗）
watchdog.vbs            无窗口拉起 watchdog.ps1
watchdog.ps1            常驻探活，掉线自动重启（崩溃自愈）
create-desktop-shortcut.cmd  生成桌面 Trae2API 快捷方式
```

发布前运行：

```bash
python -m pytest -q
```

控制台前端改动后建议额外做一次 JS 语法检查（历史上 f-string 转义曾导致整块 script 解析失败、所有按钮失效）：

```bash
python -c "import sys;sys.path.insert(0,'.');from src import main;open('.tmp/admin.html','w',encoding='utf-8').write(main._web_login_html())"
node --check .tmp/admin.js   # 抽出 <script> 块后检查
```

## 开源协议

[MIT](LICENSE)

Copyright (c) 2026 autumnsentiment（上游）、myzane678（本地维护版改动）

本项目仅用于学习和研究目的。使用本项目产生的任何后果由使用者自行承担。

## 更新日志

查看 [CHANGELOG.md](CHANGELOG.md)
