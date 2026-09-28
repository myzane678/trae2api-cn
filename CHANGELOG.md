# CHANGELOG — trae2api-cn

## v27 (2026-09-28)：控制台自动刷新

- **控制台自己会刷新了**：以前所有数据只在打开页面和点「刷新数据」时取一次，页面开着数字也是死的。
  现在侧栏底部新增「自动刷新」项，10 秒一轮拉取本地数据（统计、请求日志、签到记录、账号状态），
  点一下可暂停/恢复，右侧实时显示距上次刷新的秒数。
- **切换标签页不空转**：页面隐藏时跳过这一轮，回到前台立刻补一次，避免后台标签页无意义地打接口。
- **不打断操作**：统计数据、日志、账号列表都比对内容签名，内容没变就不重绘——
  否则每 10 秒重建一次 DOM 会把鼠标下的按钮换掉、把日志滚动位置弹回顶部。
- **账号探测加了 TTL 兜底**（`TRAE_CONSOLE_ACCOUNT_TTL_SECONDS`，默认 120s）：
  `/api/checkin/accounts` 每个账号都要真打 Trae 上游，如果照搬本地数据的 10 秒节奏轮询，
  开着页面就等于对上游持续探测（这正是签到路径一直刻意避免的封号风险点）。
  现在 120 秒内的重复轮询直接复用缓存，失败的探测也记账（坏账号同样不会被反复打）。
- **手动操作不受缓存影响**：手动「刷新数据」、签到、切换账号、删除账号、积分刷新、授权完成后
  都传 `fresh=1` 强制真实探测，刚签完的到不会因为缓存而看不见。
- 新增 5 项测试：缓存复用、`fresh=1` 强制探测、TTL 过期后重新探测、失败探测也计入 TTL、
  控制台渲染包含自动刷新循环的接线锚点。

## v26 (2026-09-28)：并发 5 + 冷却状态机 + 模型健康度排查 + 账号风险加固

### 与社区项目对比（本轮审计）

| 维度 | trae2api-cn | workbuddy2api | kuku2api | trae2api-web |
|---|---|---|---|---|
| 工具调用 | ✅ SOLO 原生 tool_calls | ✅ 流式 delta 合并 | ✅ TOOL_CALL_* 事件 | ✅ 原生 |
| 工具参数净化 | 清协议残留 | 防提示词注入 | 无 | 无 |
| reasoning_effort | ❌ 无 | ✅ 按模型降级 | 无 | 无 |
| 并发控制 | 信号量 5 + 冷却 | 无限制 | Mutex 串行 | 冷却状态机 |
| 多账号 | round-robin + 切换 | CN/INTL 双区 | 池化 | 池化 |
| API Key | 单 key | 多 key 分区 | 单 key | 单 key |
| 模型管理 | 白名单 + 大小写映射 | 白名单 | 无 | 无 |
| 统计 | 持久化聚合层 | stats.go | 简单 | 无 |

**我们做得好的**：① 模型大小写映射（上游对 `doubao-seed-2.1-pro` 报 4001，workbuddy 无此处理）；
② 冷却状态机 + 信号量组合（比 kuku 的 Mutex 串行更平衡）；
③ 协议残留清理（防止历史污染，workbuddy 是防注入目的不同）；
④ 桌面一键启动（对齐 mimo/workbuddy）；⑤ 测试覆盖 365 项。

**workbuddy 做得比我们好的**：① 防提示词注入的 sanitize；
② reasoning_effort 按模型能力降级；③ 多 API Key 分区路由（CN/INTL 双区）。

**可改进项**（记录待办）：① reasoning_effort 降级；② 防提示词注入净化；
③ 请求最小间隔限流（kuku 的 lastCall）；④ 签到后积分>0 自动解冻（trae2api-web）。



- **并发上限调到 5**（`TRAE_SOLO_MAX_PARALLEL` 默认 5，可 1-10）：信号量配幂等 `release()`，
  流式路径在 generator `finally` 释放、非流式路径在 return 前释放、异常路径兜底。
  实测 6 并发 6/6 成功、第二轮无泄漏（验证信号量释放可靠）。
- **冷却状态机**（承接 v25）：429/4011→60s、1005 权益→12h、其他上游错误→10m，
  成功即解冻。与信号量互补（信号量限并发、冷却限错误重试）。
- **模型健康度排查**：实测 6 个 DeepSeek 变体 + 3 个对照模型。`DeepSeek-V4-Flash/Pro`
  首字 4-5s、工具调用 6-7s 全部正常；`deepseek-v4.1-flash` 上游固定排队 188-218s
  （思考链仅 118 字符，是上游调度不是思考），已移出默认白名单。
- **账号风险加固**：`auth.py` 启动日志不再打印 token 前 36 字符（改为长度）；
  检查确认无提示词注入面（SOLO 纯透传）、无 verify=False、凭据目录已被 gitignore。
- **源码审核**：删未用 `secrets` 导入、孤儿函数 `_remote_only_models`、过时的
  remote/9router 文档字符串与轮询判断残留。

## v25 (2026-09-28)：删除 remote 通道 + 前端照 workbuddy 重做

- **删除 `trae_remote_client` 整个通道**（660 行 + 1395 行测试），连带清理 main.py 的
  remote 路由/分派/导入，以及 4 个孤儿助手。`main.py` 从 5846 减至 5065 行。
- **前端照 workbuddy2api 重做**：新增 `stats_agg.py` 持久化聚合层（日/模型/累计，
  30 天保留），新增 `GET /api/stats` 一次返回整页数据；控制台换成独立 `admin.html`
  （SVG 图标、hash 路由、卡片网格、双段柱状趋势图、conic 环形分布图、账号状态条、
  勾选式模型白名单、设置视图）。
- **白名单大小写与目录饥饿修复**：`canonical_model()` 把任意写法映射到目录原始拼写
  （上游对 `doubao-seed-2.1-pro` 报 4001，须 `Doubao-Seed-2.1-Pro`）；`/v1/models?all=1`
  返回完整目录（默认视图仍按白名单过滤），修掉「白名单变小就永远加不回来」的死循环。

## v24 (2026-09-27)：桌面一键启动对齐（launch.vbs / 桌面快捷方式）

- **对齐 kuku/mimo/workbuddy 的「点击即启动」形态**：新增 `launch.vbs`（薄壳，wscript
  隐藏调 PowerShell，无黑窗）+ `start-trae2api-core.ps1`（核心逻辑：健康检查 → 按需
  静默拉起 relay 8092 + OAuth 助手 8765 → 轮询 healthz 最多 20s → Chrome `--app` 无边框
  窗口打开控制台，隔离 profile `data\admin-profile`）。已在跑时秒开控制台。
- `start-trae2api.cmd` 重写为 core 的带输出版（原盲等 8s 改为健康轮询）；
  `stop-trae2api-helper.ps1` 增加按 `--trae2api-admin-window` marker 关闭控制台窗口
  （命令行匹配，不碰日常 Chrome）。桌面快捷方式「Trae2API 控制台.lnk」指向 launch.vbs。
- 实测：launch 秒开控制台窗口、stop 只关窗口不中断 relay、重开正常。

## v23 (2026-09-27)：SOLO 原生工具通道上线（llm_utils_chat），文本提示桥退役

- **换通道（核心）**：新增 `src/trae_solo.py`——SOLO `POST /api/agent/v3/llm_utils_chat`
  （`function=solo_work_lite`）成为默认上游（`UPSTREAM_MODE=solo`）。请求体**原生携带
  OpenAI `tools`/`tool_choice`**（parameters 转上游 JSON 字符串、assistant 工具历史转
  `function_call` 形状），SSE `event:output.tool_calls` **结构化返回工具调用**（id/name
  首帧、arguments 按 index 增量），经 `ToolCallAccumulator` 聚合成标准 OpenAI 流式
  `tool_calls` delta。文本提示桥（`<opencode_tool_call>`）不再是工具主路径。
- **2026-09-27 实测背书**：`get_detail_param` 返回 41 个现役 config（glm-5.3、
  DeepSeek-V4.1/4-Pro/Flash、Seed-2.1-Pro-0915、kimi-k3、qwen3.8-max、minimax-m3、
  step-5-preview…，200K~256K 窗口，含官方 is_new 与积分费率）；`tool_choice=auto` 下
  自然问法（不点名工具）2/2 主动调用；15 工具真实 schema（嵌套数组/枚举/正则参数）
  并行调用与多轮 tool-result 续轮全通过；本地 relay 端到端（非流式+流式、文本+工具+
  续轮+usage 记账）全部验收。
- **v15 SOLO 失败之谜解开**：当年 `param is invalid` 是 **`X-Ide-Version` 版本门**——
  0.1.43 被拒，`0.1.52`（code 20260811）放行全部现役模型。header 全套（Cloud-IDE-JWT
  + X-Cloudide-Token/X-Ide-Token/X-Uid/X-App-Id/设备字段）已按 tra e2api-web/trae2codex
  runbook 实测口径固化在 `solo_headers`。
- **防封（账号安全）**：每账号并发帽（默认 2，`TRAE_SOLO_MAX_PARALLEL`）；失败回合
  **绝不自动重放**（防重复扣分）；错误按业务码分类（1001 auth / 4001 参数 / 4008 配额 /
  4011 限流）；请求头版本三元组与设备字段恒定不逐请求变化；模型目录 TTL 缓存
  （`TRAE_SOLO_MODELS_TTL` 默认 600s）不逐请求打上游；验证请求压小 max_tokens。
- **前端重做**：控制台改为独立模板 `src/web/admin.html`（JS 全量渲染 + JSON API），
  灭掉 f-string 内嵌 JS 的转义炸块病根（v5/v22 两次事故的同一类根因）。workbuddy 设计
  体系：侧栏导航 + 卡片网格 + 状态标签 + 按钮 loading 态 + toast 反馈。功能全保留并新增
  手动添加凭证表单；服务端仅做 6 个占位符替换。
- **修复**：流式响应生命周期（`client.aclose()`/并发帽不得在返回 StreamingResponse 时
  释放，改挂 generator finally）；流式 usage 记账（`_track_usage_from_chunk` 补接线，
  消费记录 tokens 从恒 0 变精确）；模型白名单对齐 SOLO 现役 20 模型（清掉 remote 时代
  的 claude-* 死条目）。
- **已知问题**：tests 会把 fixture 写进真实 `.env`/`data/accounts.json`（uid-1/oauth-token），
  跑完 pytest 后启动服务前需清理，否则服务以假账号应答 401（既有缺陷，本轮未修）；
  uvicorn 端口被占时启动静默失败（10048），换端口/杀旧进程后看日志确认 `Uvicorn running`。
- **积分体系现状**：Work 专属积分已全部升级为通用积分（TraeCode/TraeWork 通吃），
  SOLO 通道消耗通用积分；`token_usage` 报的是本次请求自身的 prompt/completion。

## 实验结论记录 (2026-09-07)：提示词桥实战不可用（tool_choice=auto 下模型遵循率≈0）
> ⚠️ 本结论仅适用于 **remote 文本提示桥**（query 纯文本扁平化通道）。2026-09-27 起默认
> SOLO 原生工具通道（见 v23），auto 下工具调用正常，此结论不再适用于默认路径。

- **触发**：丞相在 DSH 用 trae provider 真实对话后指出「模型不会听话的输出工具格式」。会话日志取证确认。
- **取证**（DSH 会话 `975b5631-86ea-4d66-b67a-a1822c71b2d4`，provider=trae）：5 次真实轮次每次都带 tools=151（DSH 不发 tool_choice，即 auto）；relay 日志 5 次桥接全部激活（req-f962e688 / a568bd43 / d16591e72 / 5f7f19f4 / 1e43edd3），结果 **全部 `tool_chunks=0`**——模型直接文字回答，一次都没输出 `<opencode_tool_call>` 协议块。
- **对比 v18 通过场景**：`tool_choice=required` + 消息里明确点名工具 → 模型服从。即桥只在**调用方显式强制**时可用；自然对话（auto）下不可用。
- **根因**：Trae 上游 Agent 模型有自己的系统提示词，权重远大于注入的文本工具协议；无 tool_choice 硬约束时模型按「直接回答」行为走。151 工具 schema 实测注入约 79K 字符 query，也加剧忽略。
- **结论与定位**：
  - 技术链路本身通（tools → 提示词注入 → 协议块解析 → OpenAI tool_calls），失败在模型遵循环节，非 relay bug；
  - TRAE 渠道（8092）对 DSH 的**实际定位 = 纯文本模型**；本地工具/agent 任务走 zcode (8090) / workbuddy (8091)；
  - 桥保持默认开启无害（纯文本请求不受影响；若调用方自己发 `tool_choice=required` 仍可工作），不做「全量强制 required」——那会导致纯聊天也瞎调工具；
  - `TRAE_RAW_MAX_TOOL_SCHEMA_CHARS=100000` 已按丞相指示调整（.env），但预算问题不是本次失败的主因。
- **不再继续的方向**：向上游探针 Work tier 工具、更复杂的提示词工程对抗 Agent 系统提示词。此为上游产品形态限制。

## v22 (2026-09-07)：修复控制台 JS 崩溃（f-string 内 JS 字符串换行转义）

- **症状**：控制台所有按钮（停止服务/登出/签到…）点击无反应。
- **根因**：`_web_login_html` 是 Python f-string 模板，v21 新增的 `stopService` 里
  `confirm('…\n\n…')` 写成单 `\n`——Python 把它渲染成真实换行符，JS 单引号字符串跨行 →
  `Uncaught SyntaxError`，整个 `<script>` 失效，所有 onclick 全部按不动。
- **修复**：f-string 内的 JS 字符串换行必须写 `\\n`（双反斜杠），渲染后 JS 才得到 `\n` 转义。
  本文件其余 JS 的 `\n` 均为 `\\n`，只有新加段落踩坑。
- **验证**：渲染后 HTML 中 `stopService` 的 confirm 为单行 `\n` 字面；浏览器实测无
  SyntaxError，`stopService`/`logout`/`checkinRefreshAll` 全部定义；8092/8765 健康。
- ⚠️ 教训（第 2 次踩此坑）：**给 main.py 内嵌 JS 加字符串时必须用 `\\n`，不要在 f-string
  里写裸 `\n`**；改动后务必浏览器开控制台确认无红色语法错误。

## v21 (2026-09-07)：控制台新增「停止服务」按钮

- **新增 `POST /api/stop`**：调用 `stop-trae2api-helper.ps1`（杀 8092 relay + 8765 OAuth login helper），
  本进程随之退出；停止后需手动运行 `start-trae2api.cmd`。脚本路径默认相对 cwd，
  可用 `TRAE_STOP_SCRIPT` 覆盖；加入 `PUBLIC_PATHS`（控制台免鉴权可调）。
- 控制台顶部状态栏右侧新增「停止服务」danger 按钮（与「删除账号」同款 `.btn-danger` 样式），
  点击先 `confirm` 确认再调用；500ms 延迟执行以保证响应先返回浏览器。
- 新增 `tests/test_stop_api.py`（脚本缺失 → 500 且不执行，安全路径）。
- 全量回归：pytest 402 passed。

## v20 (2026-09-07)：测试环境隔离 + _FakeUsageTracker 同步

- **修复 `_tracked_stream` 测试脱节**：v18（d0e2e39）给 `_tracked_stream` 增加了 `tracker.first_token_ms` / `tracker.started` 读取（TTFB 统计），但 tests 的 `_FakeUsageTracker` 未同步 → 首帧即 `AttributeError`，`UsageStreamTerminalTests` 4 个用例稳定超时。已补齐两个字段。
- **新增 `tests/conftest.py` 统一测试环境隔离**：生产 `.env` 含 `TRAE_MODEL_ALLOWLIST`、`TRAE_REMOTE_PROMPT_TOOLS_ENABLED=true`，且 `data/model-allowlist.json`（运行时文件）存在时，全部 `model=auto` / 呼方 tools 用例会 403。conftest 在收集前置空 `RELAY_API_KEYS` / `TRAE_MODEL_ALLOWLIST` / `TRAE_REMOTE_PROMPT_TOOLS_ENABLED` 并屏蔽运行时白名单文件加载，任何部署配置下全量测试可复现。
- 全量回归：pytest 401 passed（此前本地部署配置下 50 failed）。

## v19 (2026-09-07)：删除 solo_work_lite 死代码 + 提示词桥默认开启
- 删除 v15 遗留的 SOLO Lite 工具通道代码：`_solo_messages`、`_solo_tools`、`resolve_solo_model`、`build_solo_chat_body`、`send_solo_chat_request`（trae_client.py）、`run_solo_chat` + dispatch solo 分支（main.py）、3 个对应测试（test_main_smoke.py）。
- 不动的：`trae_decrypt` 里的 SOLO CN 桌面登录态探测（auth 功能）、`remote_agent_type` 里的 `solo_work_lite` 别名归一（tier 映射）、`traework_native_bridge` 里的 solo_lite 原生桥设置。
- `.env` 新增 `TRAE_REMOTE_PROMPT_TOOLS_ENABLED=true`：v18 端到端验证通过后，提示词桥改为生产默认开启。带 tools 请求 → Agent tier + 提示词桥；不带 tools → Agent tier 纯文本。旧「强制 Work → 500」路径退出默认。
- README 部署卡同步更新。CHANGELOG 保留 v15 试错记录。

## v18 (2026-09-07)：修复非流式路径丢弃 finish summary 工具块 + 真实端到端验证通过
- **Bug 根因**：`collect_nonstream_web` 在第 2143 行先执行 `_ensure_required_tool_call`，之后（第 2156 行）才从 `final_summary` 提取工具调用。当上游把模型的 `<opencode_tool_call>` 块放进 finish 项 `params.summary`（实测上游行为：thought 增量快照在块中途结束，完整块由 finish summary 返回）时，required 模式下必然在提取前就报错。流式版 `translate_web_events` 顺序正确，不受影响。
- **修复**：把 required 检查移到 summary 工具调用提取之后，与流式版对齐；新增回归测试 `test_required_tool_call_in_finish_summary_is_not_dropped`（先红灯复现、修复后转绿）。
- **真实端到端验证（glm-5.3，单次请求）**：虚拟 `get_weather` + `tool_choice=required` → 上游 Agent 会话创建成功 → 模型输出协议块 → relay 返回 HTTP 200、`finish_reason=tool_calls`、`tool_calls[0].function.name=get_weather`、参数 JSON 正确。此前三次"失败"均为该 relay bug，并非模型不配合。
- 已知次要问题：模型在 thought 里的协议复述旁白会随 content 一并返回（不影响 tool_calls 正确性）；后续可按需收紧旁白过滤。
- 全量回归：`tests.test_sse` + `tests.test_raw_client` 共 129 个测试通过。

## v17 (2026-09-07)：Remote 文本工具提示桥
- 新增默认关闭的 `TRAE_REMOTE_PROMPT_TOOLS_ENABLED`：不把 `tools`、MCP、Work 云端环境字段作为可执行工具发送给上游，只把调用方工具目录写入文本提示，复用现有文本/XML 工具调用解析器转换为 OpenAI `tool_calls`。
- 工具提示明确要求模型只请求调用方本地工具、不得声称执行或生成工具结果；工具名、参数 JSON 和 `role=tool` 续轮仍由调用方/relay 校验。
- 旧 `solo_work_lite` 和 TraeCode CLI ACP 路线不再作为生产候选；普通 remote 文本链路保持不变。Remote 云端隐藏工具无法仅靠提示词做绝对禁止，因此默认关闭并保留安全边界。
- A 盘 `A:\\DevTools\\trae-cli` 安装与临时探测文件已清理；未修改现有 Trae 登录态。

## v16 (2026-09-07)：官方 TraeCode CLI ACP 安全探测
- 按官方 Windows 安装脚本审查后，未执行其硬编码 `%LOCALAPPDATA%\\trae-cli` 安装流程；从官方 CDN 下载 `trae-cli_0.120.52_windows_amd64.zip`，手动安装到 `A:\\DevTools\\trae-cli\\bin`，未修改用户 PATH、未覆盖 `C:\\Users\\huang\\.trae-cn`。
- 验证：`traecli --version` 为 `0.120.52`；`traecli acp serve --help` 正常；ACP `initialize` 与 `session/new` 均成功，声明 `loadSession`、MCP HTTP/SSE 和 `default/bypass_permissions/plan` 模式。
- 当前隔离配置没有企业 CLI 登录和有效模型：`session/new.models.availableModels=null`，`doctor` 报 `no effective model configured`；未发送 `session/prompt`，未执行工具调用。
- CLI 的自带 ripgrep 曾释放到 C 盘临时目录，已复制到 `A:\\DevTools\\trae-cli\\localappdata` 并清理本次产生的 `C:\\Users\\huang\\AppData\\Local\\trae-cli`；后续 CLI 进程可通过 `USERPROFILE/HOME/APPDATA/LOCALAPPDATA` 重定向到 A 盘。

## v15 (2026-09-07)：工具请求灰度接入 SOLO 原生 tool_calls
- 新增 `llm_utils_chat + function=solo_work_lite` 通道：带 `tools` / 工具续轮历史的请求优先走 SOLO；普通请求继续走既有 remote。
- OpenAI 工具 schema 转为 Trae 格式：`parameters` 序列化为 JSON 字符串，assistant `tool_calls[].function` 转为上游 `function_call`；SSE 继续复用现有 OpenAI tool-call 翻译器。
- 默认关闭灰度路由；设置 `TRAE_SOLO_TOOLS_ENABLED=true` 后才让工具请求走 SOLO；`TRAE_SOLO_TOOLS_FALLBACK_REMOTE=true` 才允许失败后回退 remote，默认不回退以避免云端沙箱伪造本地工具结果。
- 当前 `.env` 未切换，普通请求仍为 `UPSTREAM_MODE=remote`；raw 仍保持关闭/研究状态。只读 `get_detail_param(function=solo_work_lite)` 后确认当前 star 账号可用 wire 配置为 `glm-5-turbo` + `glm-5-turbo__dev`，不支持此前测试的 glm-5.3/deepseek-v4-flash；SOLO 路由现按账号可用别名映射，仍默认关闭。
- 进一步真实验证：SOLO 已认证，但上游实际 provider 选成 `glm-5.2`，与 detail 返回的 `glm-5-turbo__dev` 不一致，说明还缺少账号绑定的 SOLO model detail/encrypted 参数；未继续猜测或探针，灰度保持关闭。
- 离线验证：SOLO body 协议测试、工具路由隔离测试、显式回退测试、Python 编译通过；恢复 `star` 账号后受控真实请求已认证通过，但 `glm-5.3` 与 `deepseek-v4-flash` 均返回上游 `param is invalid`，灰度保持关闭，未继续探针。

## 通道诊断记录 (2026-09-06 晚)：raw 网关故障，锁定 remote
- 现象：DSH 调 qwen3.8-max 间歇报 `remote: Trae remote model is not available for the bound account`
- 实验：UPSTREAM_MODE=auto（raw）→ 连 glm-5.3 都报 `failed to get app config: record not found`（raw 网关 llm_raw_chat 当天故障/变更）；切回 remote → glm-5.3 ✅ 21.8s、qwen3.8-max ✅ 17.1s
- 结论：**非风控**，是上游 remote 云沙箱按账号的模型可用表浮动（免费池 + Agent/Work 执行器池差异）；**配置定稿 UPSTREAM_MODE=remote**
- 附加认知：上游真实模型名是大写驼峰（Qwen3.8-Max / DeepSeek-V4-Flash / GLM-5.3，见 Trae 客户端截图），relay 小写 id 经 convert_model_name 映射；DSH 默认模型建议 glm-5.3，间歇失败重试一次

## v14 (2026-09-06)：消费记录加「首字 / 耗时」两列（对齐 workbuddy2api v3）
- 后端：`_UsageTracker` 增加 `first_token_ms`——`_tracked_stream` 首个上游 chunk 到达时刻 − started；非流式不计（显示 "-"）
- `_record_usage` / `_normalize_usage_record` 透传 `ttfb_ms`，随 usage_records.json 持久化
- 前端消费记录表新增「首字」「耗时」两列（秒格式如 0.6s / 2.9s，缺失显示 "-"）
- 实测：glm-5.3 流式一条，首字 606.3ms、耗时 2965.1ms、积分正常记录

## v13 (2026-09-06)：启停脚本体验调整（丞相要求）
- 启停脚本停留时间 2s → **约 7s**（ping -n 8）：双击后能看清启动/停止输出再自动关窗
- 授权助手启动加 `--no-open`：**不再自动弹浏览器**（之前每次启动 helper 都会拉起一个 /web/login 标签页）

## v12 (2026-09-06)：白名单视图重构——默认只看在用模型
- 按丞相反馈改交互：**默认只显示当前白名单 14 个**（勾选态），不再一次性糊出 62 个全量
- 添加走「下拉挑选 + 添加」：下拉只列**未加入白名单的**模型（字母序），点「添加」追加进勾选列表；去勾 + 保存 = 移出
- 保存后重渲染视图；全量目录仍通过 /api/allowlist 的 all 字段按需提供
- 验证：py 编译 + node --check 通过，renderAllowlist/addAllowlistModel 就位

## v11 (2026-09-06)：白名单可视化勾选管理
- 控制台"模型列表"区改造为**勾选式白名单管理**：
  - 「获取全量模型」→ 拉上游全量目录（62 个），每项带 checkbox，当前白名单默认勾选
  - 勾/去勾实时显示「已选 N / 全量 62」，点「保存白名单」→ POST `/api/allowlist` 即时生效
  - 未勾选的模型不暴露到 /v1/models，调用也被 403 拦截
- 后端：`GET/POST /api/allowlist`（GET 返回 all+allowed；POST 校验+小写化+热更新内存+落盘 `data/model-allowlist.json`，重启保留、优先于 .env）
- 验证：POST 加 gpt-4o → /v1/models 立即变 15 个 → 还原 14 个；py 编译 + 页面 script node --check 通过

## v10 (2026-09-06)：白名单收紧至 14 个
- 丞相点名移除：claude-opus-4-5、claude-haiku-4-5、gpt-4o、gpt-4o-latest（GPT 系暂时清空，需要时可加回或走国际版）
- 白名单最终 14 个：claude-opus-4-6 / 4-7、claude-sonnet-4-6、glm-5.3 / 5.2、deepseek-v4-pro / flash、doubao-seed-2.1-pro / turbo / code、kimi-k3、kimi-k2.7-code、minimax-m3、qwen3.8-max

## v9 (2026-09-06)：模型白名单机制 + 协议确认
- 新增 `TRAE_MODEL_ALLOWLIST` 环境变量（逗号分隔，小写比较；留空 = 全量）：
  - `/v1/models` 只返回名单内模型（62 → 23 → **18**：先按名单过滤，再按小写 id 去重，大小写重复别名只保留规范小写版）
  - `/v1/chat/completions` 等调用入口对名单外模型返回 403 `model not allowed by TRAE_MODEL_ALLOWLIST: <id>`（实测 claude-3.5-sonnet 被拒）
- 初版白名单 18 个：claude-opus-4-5/4-6/4-7、claude-sonnet-4-6、claude-haiku-4-5、gpt-4o、gpt-4o-latest、glm-5.3/5.2、deepseek-v4-pro/flash、doubao-seed-2.1-pro/turbo/code、kimi-k3、kimi-k2.7-code、minimax-m3、qwen3.8-max
- 协议确认（丞相问询）：标准 **OpenAI Chat Completions** 格式（`messages[]` + `tools`/`tool_calls`），另有 Codex **Responses API**（/v1/responses）；**不支持** Anthropic messages 格式（那是 ProjectEio/trae2api 国际版项目的形态）

## v8 (2026-09-06)：切换按钮"装死"修复
- 病根：服务端对当前账号渲染 `disabled` 属性（`switch_disabled = " disabled" if acc.get("is_active")`），丞相点的是个禁用按钮，物理无响应——设计初衷是"当前账号不能切到自己"，但禁用态视觉太隐蔽
- 修复：不再渲染 disabled；`switchAccount()` 增加早退——点当前账号直接 toast「该账号已是当前账号，无需切换」（5s），点其他账号走正常切换流程
- 移除孤儿赋值（switch_disabled 改恒空串并留注释说明）
- 验证：script node --check 通过、按钮无 disabled、helper/relay 双活

## v7 (2026-09-06)：trae.cn 链接直达 dashboard
- 说明文字与"访问 trae.cn"按钮的链接改为 `https://www.trae.cn/dashboard`（trae.cn 首页对已登录用户多一次跳转，直达用量管理）
- OAuth 授权端点（/authorization）不动
- 验证：relay + helper 双活、script node --check 通过、dashboard 链接 2 处生效

## v6 (2026-09-06)：反馈体验完善（JS 复活后的收尾）
- **helper 常驻**：start-trae2api.cmd 现在同时拉起 relay(8092) 和 OAuth 助手(8765)——之前 stop 脚本双杀后 helper 不随 relay 复活，授权按钮每次都要等 1.2s 检测超时才弹"未检测到助手"。现在按钮即时响应
- **"多账号轮询"区块折叠**（summary：多账号用户才需要，单账号可无视）——丞相点名要求
- 忙碌指示文案 "正在查询/签到..." → "正在处理..."（积分查询也走同一指示器，原文案误导）
- 切换成功的 toast 3s → 6s（3 秒太短，丞相没看到以为没反应）
- 服务端 /api/accounts/switch 实测 success:true——切换功能本身正常

## v5 (2026-09-06)：总病根修复——页面 JS 从部署起就是死的

### 决定性发现
控制台页面的 `<script>` 块里有一处 **f-string 转义 bug（上游遗留）**：`connModelList()` 中的正则 `/[\n,]+/` 写在 Python f-string 里，`\n` 被 Python 吃成真实换行，正则跨行断裂 → **整块 script 解析失败** → 所有全局函数（startAuth/checkinRefreshAll/creditsRefreshAll/refreshModels/switchAccount…）从未定义 → **页面上所有按钮从部署起就没有过响应**。

这解释了全部历史症状：
- 首次登录时授权按钮"没反应"（当时误判为浏览器弹窗拦截，靠直开授权页 URL 绕过）
- 查询签到状态/查询全部积分/一键轮询/单行签到/切换全部无反应
- 消费记录永远"暂无"（纯 JS 渲染，没有 JS 就永远空）
- 获取模型列表无反应
- 而**积分三列、签到状态能显示**是因为它们由**服务端渲染**进 HTML，不依赖 JS——正是这个假象把排查引向了"前端锁"的歧路

### 修复
- `src/main.py` connModelList 内：`raw.split(/[\n,]+/)` → `raw.split(/[\\n,]+/)`（f-string 中 `\\n` 输出字面 `\n`，JS 正则恢复"换行或逗号"语义）
- 用 `node --check` 对渲染后的整块 script 做语法验证，通过；关键函数（startAuth/checkinRefreshAll/creditsRefreshAll/refreshModels/silentLoadState）全部齐全

## v4 (2026-09-06)：消费记录诊断增强 + 真实模型列表
- refreshUsage 失败分支新增 showToast 弹窗（15s），加载失败原因直接弹脸
- `.env` `TRAE_FETCH_MODEL_LIST=true`；OAuth 回调助手重新拉起（8765）

## 排查方法论（教训，排查时必读）
- "按钮没反应"先怀疑 **script 解析级死亡**（全灭），再怀疑锁与网络（部分灭）；服务端渲染的数据能显示恰恰会伪装成"JS 活着"
- 验证法：curl 页面 HTML → 抽 `<script>` 块 → `node --check`，30 秒定位，不需要浏览器
- 同类隐患：Python f-string 内嵌 JS 时所有 `\n` `\s` `\d` `\t` 都会被 Python 解释——上游更新后需重新 `node --check`
- 从 pwsh 调 start/stop 脚本禁止管道捕获输出（句柄死锁连坐杀服务），正确姿势：`cmd /c "xx.cmd > 文件 2>&1"`
- pwsh 工具偶发 exit 1 无输出 = 进程被强杀，换简单写法重试

## v3 (2026-09-06)：前端锁死修复 + 真实模型列表

### 问题定位（丞相反馈：所有按钮没反应、消费记录"暂无"）
- 病根是 v2 补丁：页面加载时自动调用 `checkinRefreshAll()` / `creditsRefreshAll()`，这两个函数带 **setBusy 全局锁**（禁用全部查询/签到按钮），超时 90s——赶上重启后首次上游慢，"开页面即锁死，越刷越锁"
- 消费记录"暂无"：API 一直有数据（5 条），是页面加载时该请求失败的残留显示

### 修复（src/main.py 本地 patch）
1. 新增 `silentLoadState()`：页面加载只读 `/api/checkin/accounts` 缓存（8s 超时、不碰 setBusy、失败静默），替代 v2 的自动重查询
2. `checkinRefreshAll` / `creditsRefreshAll` 的前端超时 90000 → **20000**（上游正常 3.2s，20s 兜底；手点按钮最多锁 20s）
3. `.env` `TRAE_FETCH_MODEL_LIST=true`：控制台"获取模型列表"按钮现在真从上游拉账号可用模型（实测 62 个 / 2.9s）

### 界面行为说明（非 bug）
- **多账号轮询**：上游自带功能，多个 TRAE 账号时每次请求自动换号（顺序轮询/积分优先），单账号可无视
- **切换按钮**：单账号点了等于切给自己，提示 3s 即逝，无可见变化属正常
- **获取模型列表**：需 `TRAE_FETCH_MODEL_LIST=true` 才拉上游真实列表（已开启）

### 运维经验（重要）
- **从 pwsh 调 start/stop 脚本禁止用管道捕获输出**（`cmd /c xx.cmd | Select-String`）：脚本内 Start-Process 拉起的 python 继承管道句柄不关闭 → pwsh 等管道 EOF 直到超时被杀，且作业树连坐杀掉刚拉起的 relay。正确姿势：`cmd /c "xx.cmd > 文件 2>&1"`

## v2 (2026-09-06)：控制台体验修复 + 积分体系查清

### 本地前端 patch（src/main.py，上游更新时需重新套用）
1. **页面打开自动加载数据**：`refreshUsage()` 后追加 `checkinRefreshAll()` + `creditsRefreshAll()` —— 积分三列（通用/Work/总）、签到状态不再需要手点按钮（此前页面加载只刷消费记录，积分列永远 "-"，这是"刷新刷不出来"的根因）
2. **"下载本机授权助手"折叠**：登录卡片里的下载按钮组包进 `<details>`（summary：下载本机授权助手（首次登录/换号才需要）），与"手动填写凭证"折叠样式一致

### 积分体系真相（/api/checkin/credits/accounts 实测，3.2s）
- **总积分 4650，已用 4.83，剩 4645.17**（丞相记忆中的 4500 即此总盘子）
- 通用（IDE）侧 2650 = 老用户福利 2000 + 每月登录赠送 500 + 每日签到 150
- Work（SOLO）侧 2000（一分未动）
- 权益包 5 个：老用户福利(2000, source_type=10) / 免费 SOLO 能力包(非积分) / 每月登录(500) / 签到奖励(150)
- 消耗参考：glm-5.3 每次调用约 1 分（0.96~1.05），4650 分 ≈ 4000+ 次调用

### 运维备注
- 重启后首次积分刷新端点偶发慢（>90s 一次，之后稳定 3.2s），前端超时 90s 兜底
- 消费记录：/api/usage/records 按请求一行（模型/tokens/单次积分/耗时/状态），页面下方"消费记录"区块自动刷新

## v1 (2026-09-06)：TRAE CN 反代首次部署

### 来源
- 上游项目：[autumnsentiment/Trae2api-cn](https://github.com/autumnsentiment/Trae2api-cn)（Python/FastAPI，14★，MIT）
- 选型时活跃度：最后提交 2026-09-01（当天 5 个 commit：签到 9074 退避轮换修复、模型连通面板）；作者 Issue #1 确认 chat 端点 tools 调用正常
- 备选对比：ProjectEio/trae2api（Anthropic 协议，国际版模型）、connectedGraph/trae2api-web（Sliverkiss 系）、linqiu919/trae2api（已归档，弃用）

### 部署
- 位置：`A:\ClaudeWorkspace\trae2api-cn`（venv 在 `.venv\`，Python 3.13，依赖走清华镜像）
- 端口：`127.0.0.1:8092`（8090 zcode / 8091 workbuddy 之后的第三顺位）
- API Key：`sk-trae-6a056f59f298f35f69f01772515f3316`（写在 `.env` 的 RELAY_API_KEYS）
- 认证：`TRAE_AUTH_SOURCE=web-login`，授权回调助手监听 `127.0.0.1:8765`，token 自动续期
- 上游：`UPSTREAM_MODE=remote`（默认 Agent 执行器，调用端工具请求自动走 Work 会话）
- 账号：star（uid 604047438004087），签到积分 150 通用 + 50 额外

### 脚本（纯 ASCII，无窗口自关；`timeout` 换成 `ping -n 3` 防无控制台环境报错）
- `start-trae2api.cmd` — 启动 relay（日志落 `data\relay-stdout/stderr.log`）
- `start-trae2api-login.cmd` — 启动 OAuth 回调助手（8765，登录/换号时才需要）
- `stop-trae2api.cmd` + `stop-trae2api-helper.ps1` — 按 8092/8765 端口杀进程

### 验证结果（2026-09-06 全部通过）
- `/healthz` ok；`/v1/status` capabilities：openai_tool_calls / openai_responses / parallel_tool_calls 全 true，tool_execution=client
- 非流式工具调用 round-trip：glm-5.3 与 doubao-seed-2.1-turbo 均正确返回 `tool_calls`（get_weather {"city":"北京"}）并成功续轮消化 tool result（finish_reason: stop）
- 流式：`delta.tool_calls` 分帧 + `finish_reason: tool_calls` + `[DONE]` 正常
- 签到：`POST /api/checkin/claim-all` 成功（服务端直查签到状态仅 2.8s）

### 已知问题 / 经验
1. **`auto` 模型不可用**：remote 路径解析成 `Doubao-Seed-2.1-Turbo__dev` 后会话创建失败 → 一律用显式模型 id（glm-5.3 等）
2. **登录弹窗会被浏览器拦截**：授权页按下面模板直接开普通标签页（助手需在跑）：
   `https://www.trae.cn/authorization?login_version=1&auth_from=solo&login_channel=native_ide&plugin_version=2.3.24254&auth_type=local&client_id=ono9krqynydwx5&redirect=0&login_trace_id=<uuid>&auth_callback_url=http%3A%2F%2F127.0.0.1%3A8765%2Fauthorize&machine_id=<hex32>&device_id=<19位>&x_device_id=<同device_id>&x_machine_id=<同machine_id>&x_device_brand=ASUS+TUF+Gaming+A15+FA507RM_FA507RM&x_device_type=windows&x_os_version=Windows+10+Pro&x_env=&x_app_version=3.3.65&x_app_type=stable&hide_saas_login=true`
3. **控制台页面查积分转圈**：前端显示问题，服务端接口实测 2.8s 正常返回；积分/签到操作可走 curl
4. raw 桥接的固有开销：工具 schema 翻译进系统提示，单请求 prompt 约 3 万 token 起步（TRAE_RAW_MAX_TOOL_SCHEMA_CHARS 有压缩机制）；usage 的 prompt_tokens 有时为 0（上游不回传）
5. tool_calls 的 id 可能是 `<unique-id>` 占位符或模型自编 id → 客户端续轮时 tool_call_id 建议同时带 name 匹配

### 模型池（内置表，2026-09-06）
Claude Opus 4.5/4.6/4.7、Claude Sonnet 4/4.5/4.6、Claude 3.5/3.7、Haiku 4.5、GPT-4o 系、GLM-4.6/4.7/5/5.1/5.2/5.3、DeepSeek-V4-Flash/Pro（含别名）、Doubao-Seed-2.1-Pro/Turbo/Code/Evolving、Kimi-K2/K2.6/K2.7-code/K3、MiniMax-M2.1/M2.7/M25/M3、Qwen-3.6/3.7/3.8-plus、qwen3.8-max、mimo-v2.5、qwen3-coder 等。
**实际可用性以账号权益为准**（`TRAE_FETCH_MODEL_LIST=true` 可拉上游真实列表）。

### 三份额度进度
ZCode ✅ (8090) · WorkBuddy ✅ (8091) · **TRAE ✅ (8092)** · 豆包多模态侧车 ⏸（doubao2api，待装）
