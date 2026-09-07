# CHANGELOG — trae2api-cn

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
