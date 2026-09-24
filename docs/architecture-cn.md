# 架构说明

Artemis 是面向多用户、多 Agent 的自托管 AI 助手平台，以单个 Python 进程交付。
它将三个可复用库整合为一个 Python wheel：基于 LangGraph 的聊天运行时
`harness-agent`、IM 通道管线 `harness-gateway`，以及 React + TypeScript
控制台；同时提供 CLI、HTTP/WebSocket API 和 Web 界面。

> 本文是面向开发者的架构概览。模块边界、变更流程和禁止事项请参见仓库根目录的
> [AGENTS.md](../AGENTS.md)，该文件是供编码 Agent 使用的工作手册。

## 1. 分层结构

```
┌──────────────────────────────────────────────────────────────────┐
│  使用入口        │ 控制台（React）  CLI（Click）  HTTP API        │
├──────────────────────────────────────────────────────────────────┤
│  API 层          │ FastAPI 路由       WS / SSE / JSON             │
├──────────────────────────────────────────────────────────────────┤
│  领域层          │ AgentManager  Gateway  GlobalProcessor         │
│                  │ CronManager   UserManager  SharedServices       │
├──────────────────────────────────────────────────────────────────┤
│  可复用库        │ harness-agent   harness-gateway                │
├──────────────────────────────────────────────────────────────────┤
│  存储层          │ SQLite 或 PostgreSQL 控制面 + Agent 工作区     │
└──────────────────────────────────────────────────────────────────┘
```

整个系统运行在一个进程内：没有独立 Worker、外部消息队列，也不强依赖除用户配置的
LLM 供应商之外的服务。

## 2. 进程模型

`ArtemisServer.start()` 按依赖顺序组装运行时。组合根位于
`src/artemis/infra/server.py`；FastAPI/uvicorn 在 `src/artemis/launch.py` 中接入。
后者是唯一可以同时导入 `infra/server` 和 `api/app` 的模块。

```
ArtemisServer.start()
 ├─ PathLayout.from_env()            （根目录、数据库、密钥目录）
 ├─ load_config(config.json)         （环境变量覆盖配置文件）
 ├─ open_database()                  （SQLite WAL 或 PostgresPool 的 PostgreSQL）
 ├─ run_migrations()                 （infra/db/migrations/*.sql，带版本迁移）
 ├─ SharedServices                   （仓库与工厂对象）
 ├─ WizardTokenStore                 （有效期 5 分钟的初始化令牌）
 ├─ ExpertCatalog / SubagentCatalog  （内置专家与子 Agent 目录）
 ├─ PluginManager.seed_bundled() 后 load_installed()
 │                                  （~/.artemis/plugins/*；内置插件默认关闭）
 ├─ AgentManager                     （全进程唯一 Agent 注册表）
 │    └─ 对每条 Agent 记录按需构建 HarnessAgentRuntime
 │       ├─ HarnessAgent             （LangGraph）
 │       ├─ GlobalProcessor          （斜杠命令分发与流式事件投影）
 │       └─ BackendWorkspace         （文件系统或远程存储适配器）
 ├─ Gateway                          （IM 通道、WS Hub、Cron 触发源）
 │    ├─ ChannelManager              （每个有通道配置的 Agent 一个）
 │    └─ WebSocketHub                （控制台与 CLI 通道）
 ├─ CronManager                      （全进程 APScheduler）
 └─ UserManager                      （鉴权与按用户查询）
```

`AppRuntime` 数据类持有四个在线单例；`api/routers/*` 通过
`server.app_runtime.<thing>` 访问它们。

### 按用户隔离

每个请求都由 JWT 鉴权，并解析为一个 `User` 行。Agent 所有权在**数据行**级别执行：
调用者必须匹配 `agents.user_id`，管理员可绕过。系统不再按用户分别维护
`AgentManager`；全局注册表将请求分发给匹配该 Agent 行的 harness 运行时，便于
`/api/admin/*` 管理能力和跨用户诊断。

控制台仅通过 `/api` HTTP/WebSocket 与 Artemis 交互；React SPA 不导入 Python 模块，
也不会直接打开 SQLite 文件。

## 3. 对话入口

三个入口复用同一套 Agent 运行时：

| 入口 | 通信方式 | 默认会话键 | 说明 |
|------|----------|------------|------|
| Web 控制台 | WebSocket `/api/agents/{aid}/chat/ws` | `<aid>:dashboard:<user_id>:dm` | 控制台轮次入口 |
| CLI | 内嵌 `ArtemisServer`（REPL）或 WebSocket | `<aid>:cli:<user_id>:dm` | `artemis chats send` / `chats repl` |
| IM 通道 | gateway `ChannelManager` | `<aid>:<channel_kind>:<platform_session>:<dm\|group>` | 见 `infra/gateway/process/message_keys.py` |
| Cron 任务 | APScheduler 触发 → `Gateway.push_text_from_session` | 行中的 `session_key`，默认是所有者的 `dashboard_key` | `task_type=text\|agent` 决定直接推送或先运行 AI 再推送 |

`thread_id` 本身不包含来源；来源存放在 `chat_sessions` / `threads` 的列中。线程复用和
归档只是数据行更新，完整状态机见 `infra/gateway/threads.py`。

> **流式聊天现已采用 WebSocket。** 旧的
> `POST /api/agents/{aid}/chat/stream` SSE 接口已由双向 WS 替代，控制台可在同一轮中
> 发送斜杠命令或 `/compact`。只有
> `POST /api/agents/{aid}/chat/hitl/resume` 仍使用 SSE，用于把恢复后的轮次流回客户端。

## 4. 存储

**控制面**数据（用户、Agent、供应商、通道、Cron、会话、审计记录和 JWT 密钥）存放在：

* SQLite：默认位于 `~/.artemis/`，使用旧版 `artemis.db` 或
  `config.json` 中的 `database.sqlite_path`；或
* PostgreSQL：通过 `config.json`、`ARTEMIS_DATABASE_*` 或初始化向导的数据库步骤配置。

数据库迁移文件为 `src/artemis/infra/db/migrations/NNN_*.sql`（SQLite）和
`NNN_*.pg.sql`（PostgreSQL）。SQLite 连接 PRAGMA 位于连接池；PostgreSQL 扩展
（例如 `vector`）由 Docker/运维初始化，而不是应用迁移。Agent 记忆的 DDL 由
`harness-memory` 负责，详见 [ADR 002](./adr/002-database-backends.md)。

wheel 内含已构建的控制台 SPA，因此整个系统可通过一次 `pip install` 安装。

每个 Agent 工作区的内容文件（Markdown、技能、专家模板）经由其
`BackendWorkspace` 读写：`artemis.infra.backend` → `harness_agent.backends`。
默认后端为根目录在 `~/.artemis/agents/<agent_id>/` 的 `filesystem` 适配器；S3、COS 等
远程后端也挂载在同一根目录之上。Artemis 服务不会通过 `Path.write_text` / `read_text`
直接读写这些内容文件，完整规则见
[Agent 后端文件 I/O](./agent-backend-file-io.md)。检查点、LangGraph 状态和
`sessions/*.jsonl` 回退文件由 harness 管理，仍存放在本地工作区目录。

## 5. 国际化（i18n）

服务器产生的文本，如斜杠命令回复、IM 状态、API 错误、工具展示名称和 CLI 输出，均来自
`src/artemis/i18n/{en,zh}.json` 与 `src/artemis/i18n/domains/` 的辅助函数。语言解析顺序为：
用户已保存偏好 → `Accept-Language` 请求头 → 通道类型提示，逻辑位于
`infra/utils/locale.py`。控制台在 `dashboard/src/locales/{en,zh}.json` 中镜像
`apiErrors.*` 键，并可从 `GET /api/i18n/tools` 获取工具标签。

## 6. 多 Agent 协作（harness teams）

`@Agent` 和 `ask_agent` 经由 harness 的 `TeamManager`（`InboxManager` +
`GlobalProcessor`）处理。队列协议见 [Agent 互操作邮箱](./agent-interop-mailbox.md)，
两个用户侧入口见 [Agent 调用 Agent](./agent-call-agent.md) 和
[Agent 后台协作](./agent-delegation.md)。Artemis 的 `GlobalProcessor` 实现
`TeamProcessor` 协议，使回复回写到父线程检查点，并由 `on_reply` 推送给控制台或 IM。

## 延伸阅读

- [AGENTS.md](../AGENTS.md)：模块边界、禁止事项和变更流程
- [架构决策记录](./adr/)：单进程、无队列等设计决策（ADR 001）
- [配置说明](./configuration.md)：`~/.artemis/` 布局与环境变量
- [API 参考](./api.md)：路由、请求体和错误码
- [CLI 参考](./cli.md)：所有子命令
- [人格说明](./personas.md)：MBTI 模板与 `mbti_profiles` 数据模块
- [ACP 集成](./acp.md)：入站/出站 ACP 服务与 Runner 工具
- [Agent 互操作](./agent-interop-mailbox.md)、[Agent 调用](./agent-call-agent.md)、
  [Agent 后台协作](./agent-delegation.md)
- [Agent 后端文件 I/O](./agent-backend-file-io.md)：工作区内容文件规则
