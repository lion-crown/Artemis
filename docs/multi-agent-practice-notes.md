# Artemis 多 Agent 实践笔记（2026-09-09）

> 记录一次从"搭建多 Agent 读代码 → 总结业务话术"到排障的完整过程，
> 帮助理解 Artemis 框架的核心概念、配置位置，以及实际踩过的坑。

---

## 一、Artemis 是什么

自托管 AI 助手平台（多用户、多 Agent），单 Python wheel 打包：

- **后端**：FastAPI + uvicorn
- **Agent 运行时**：`harness-agent`（LangGraph）
- **IM 桥接**：`harness-gateway`
- **控制面 DB**：SQLite（WAL，默认）或 PostgreSQL
- **前端**：React 18 + TypeScript + Vite + Ant Design
- **调度**：APScheduler

**单进程**架构，一条 `artemis run` 启动 Web 控制台 + CLI + IM 通道 + 定时任务。
数据默认存 `~/.artemis/`，无需 Redis / 消息队列等中间件，唯一硬依赖是 LLM Provider。

---

## 二、多 Agent 协作模型

Artemis 的多 Agent 是**层级委托模式**（对应 AgentScope 8 种模式里的 Subagents）：

```
主 Agent（编排器）
 ├── SOUL.md        ← 系统提示词，写"如何编排"（派谁、怎么总结）
 ├── workspace        ← 文件根目录，子智能体共享访问
 ├── 子智能体 A        ← 用 task 工具 spawn，读后端代码
 ├── 子智能体 B        ← 用 task 工具 spawn，读前端代码
 └── task 工具      ← 核心编排工具（critical，不可禁用）
```

关键点：

| 概念 | 说明 |
|------|------|
| **SOUL.md** | 主 Agent 的系统提示词，决定编排逻辑。**不写它就不知道要读代码** |
| **子智能体** | 以 `.md` 文件存在，定义人格/职责，**不是独立 Agent** |
| **继承 workspace** | 子智能体共享主 Agent 的 `root_dir`，没有自己的根目录 |
| **task 工具** | 编排核心，负责 spawn 子智能体、派任务、收结果 |

> 比 AgentScope 优势：文件工具（`grep`/`read_file`/`glob`/`execute`）内置，
> 内置 MCP 网关，还能通过 ACP 直接调用 Claude Code / OpenCode 等外部编程 Agent。

---

## 三、目标场景与配置步骤

> 场景：输入一个项目目录，模型读代码，分后端/前端两个子智能体，
> 外层主 Agent 只负责把技术结果总结成**业务语言**。

### 1. 存储后端（决定 agent 能访问哪个目录）

| UI 显示 | 实际值 | 说明 |
|--------|--------|------|
| 本地文件系统（不能执行指令） | `filesystem` | 只能读写文件，推荐读代码用 |
| 本地完整环境（文件+指令执行） | `local_shell` | 还能跑 shell 命令 |
| 组合模式 | `composite` | path mapping 多目录映射 |
| 会话状态 | `state` | 临时存储，不碰真实文件 |

- 只有后端目录：`root_dir` 填后端路径
- 前后端同父目录：`root_dir` 填父目录，靠提示词约束范围
- 前后端不同目录隔离：用 `composite` + 路径映射

> ⚠️ 有完整文件权限的终端启动服务器，否则探测/读写会报 Permission denied。

### 2. Agent 配置要点

- **模型**：必须设成支持 function calling 的模型，且在供应商里**启用**。
  只启用供应商模型、不给 agent 设上，agent 会用默认模型，模型仍会是 `None`。
- **后端/root_dir**：定义子智能体能访问的文件范围。
- **SOUL.md**（系统编排指令）。
- **子智能体**：通过 Agent 卡片 → 子智能体按钮创建。

### 3. 页面操作路径

| 操作 | 位置 |
|------|------|
| 创建 Agent / 设模型 | Agent 列表 → 创建 / 编辑 |
| 写 SOUL.md | Agent 卡片 → 工作区 → SOUL.md |
| 管理子智能体 | Agent 卡片 → 子智能体按钮 |
| 启用供应商模型 | 设置 → 模型/供应商 |
| 存储后端 | 管理 → 存储 |
| 验证 | Agent 启动后，通过 Web 对话或 IM（企微）发问 |

---

## 四、遇到的问题全记录

### 问题 1：首页 404 `{"detail":"Not Found"}`

- **现象**：打开根路径 404
- **原因**：`src/artemis/dashboard/` 里没有构建产物（缺 `index.html`）
- **解决**：`make build-frontend` 后重启，根路径返回 200

### 问题 2：探测存储后端 Permission denied

- **现象**：probe API 报 `Permission denied: '~/Documents/trae_projects/gsk/...'`
- **原因**：服务器从早期受限沙箱终端启动，文件访问范围没覆盖 `~/Documents`
- **解决**：从有完整文件权限的终端重启服务器

### 问题 3：Agent 不读代码，直接"靠猜"回答 ★核心问题

- **现象**：无论问什么都直接回答，日志里**整天零工具调用**
- **排查链**：
  1. 确认 SOUL.md 已写、子智能体已建、模型已设、目录可读——全对
  2. 日志确认：`tools_sample=[]`（只是无 MCP 工具，正常）；
     bootstrap 用 BOOTSTRAP.md 覆盖过系统提示词（仅首次）
  3. **用探针直连 MaaS 接口带 tools 测试 → DeepSeek 返回标准 `tool_calls`，
     `finish_reason: "tool_calls"` → 模型本身支持工具调用**
  4. 结论：问题不在模型也不在用户配置，在 **harness-agent 与华为 MaaS 端点的对接**
- **关键异常证据**：MaaS 响应里**同时含 `reasoning_content` 和 `content`**，
  很可能让 harness-agent 的 OpenAI 适配层把它解析成"推理消息"，从而**丢弃了 `tool_calls`**
- **影响**：凡走 harness-agent 的模型（GLM、DeepSeek 均如此），都拿不到工具定义去调用

---

## 五、框架层面的教训 / 理解

1. **工具调用发生在 harness-agent（LangGraph）里，不在本项目仓库内**。
   要排查工具调用，需看 harness-agent 的请求/响应适配逻辑。

2. **`tools_sample=[]` ≠ 没有内置工具**。那只是 MCP 工具统计，文件工具/`task` 是 harness 内置的。

3. **SOUL.md 的位置与生效**：
   - 位于 agent 主目录 `~/.artemis/agents/<id>/SOUL.md`
   - 首次运行 bootstrap 会先用 `BOOTSTRAP.md` 覆盖系统提示词（只管初始化）
   - 之后用 SOUL.md。**有些模型若响应姿势不对（reasoning+content 共存），工具链路会断**

4. **改配置必须重启 Agent**：SOUL.md、子智能体、模型都是启动时加载，
   只改不重启，运行时仍是旧配置。

5. **模型正确设置的两步**：供应商里启用（enabled=true）→ Agent 里分配该模型。
   漏任何一步，agent 实际用的可能还是默认模型。

6. **子智能体共享主 Agent 的 workspace**："后端/前端各读各的"靠**提示词约束**，
   不是靠权限隔离（除非用 `composite` 做路径级隔离）。

7. **隔离实验法**：当怀疑「子智能体 path 有问题」 vs 「模型/适配层有问题」时，
   先让 Agent 直接用 `grep`/`read_file`（不走 `task`）——若仍不调工具，
   即可坐实是运行时与供应商的对接问题，与编排路径无关。

---

## 六、待办 / 下一步

- [ ] 方案 B 验证：把 SOUL.md 改成直接 `grep`/`read_file`，看能否触发工具调用
  - 若能 → 子智能体 `task` 路径有问题
  - 若不能 → 坐实是 harness×MaaS 对接问题
- [ ] （可选）换 Artemis 官方测试良好的供应商端点，确认流水线端到端能跑
- [ ] （根治）若确认 MaaS 响应姿势问题，需修复 harness-agent 对
      `reasoning_content + content` 共存响应的工具调用处理

---

## 七、补充验证：企微长任务、线程上下文与模型切换

> 以下为后续实测结论，修正上文中将“未调用工具”完全归因于 MaaS 适配层的推断。

### 1. GLM-5.2 与 DeepSeek 都能调用工具

线程持久化记录显示，华为 MaaS 的 `glm-5.2` 和 `deepseek-v4-pro` 均产生过
`finish_reason: "tool_calls"`；因此“模型完全拿不到工具定义”并不成立。排障时必须
同时查看线程中的工具消息、模型 finish reason 和最终错误，不能只依据 `tools_sample=[]`
或单次空回答下结论。

### 2. 企微 `final_only` 回复模式

为代码检索等长任务增加了企微通道级 `final_only` 模式：

```
企微消息 → 立即确认“正在分析” → Agent 内部执行/聚合 → 主动发送最终答案
```

- 页面位置：Agent → 通道 → 企业微信 → 消息展示 → 企业微信回复方式。
- `stream` 仍是默认模式；`final_only` 按单个企微通道保存，不影响其他机器人。
- `final_only` 必须将流式 Agent 事件聚合为最终正文；直接忽略所有 delta 会导致最终
  回退成 `✅`，这是实现时实际遇到过的错误。
- 已实测 DeepSeek 的完整业务回答可在任务结束后主动发送；GLM-5.2 的短回答也能被
  正确投递。

### 3. 同一企微会话会携带线程上下文

- 企微私聊映射到一个固定 thread；后续提问会带上此前对话、工具结果和代码检索内容。
- `/new` 会把当前企微会话重新绑定到新 thread；下一条正常问题不带旧对话上下文，
  但仍保留 SOUL、系统提示词和工具定义。
- `/compact` 会摘要早期上下文并保留最近部分，不会创建新 thread。
- 当前没有企业微信“只带最近 N 轮”或“始终无上下文”的页面配置；QQ 群的
  `history_limit` 不适用于企业微信。

### 4. DeepSeek prompt cache 与 GLM/MaaS 限流

- 当前 DeepSeek Flash 线程实测多次命中服务端 prompt cache；一次最终调用约有
  `123,136` 个 `cache_read_tokens`，因此重复问题回答更快。
- 这是模型服务端缓存，不是 Artemis 直接复用旧答案；Artemis 的作用是保留并再次传递线程历史。
- 华为 MaaS GLM-5.2 在同一线程中没有命中该 DeepSeek 缓存。切换模型后需要重新处理
  大量历史 token，且 MaaS 限流按供应商/API Key 时间窗口计算；`/new` 能清除会话历史，
  但不能立刻清除已经触发的供应商限流。
- 测试 GLM 时应新开 thread、避免连续重试；长线程优先使用已命中 cache 的 DeepSeek。

### 5. 浏览器工作台 CDP 连接

- 浏览器工作台错误 `failed to attach browser profile 'user-1'` 并非 profile 必然损坏。
- 实测 Chrome 已能监听 `127.0.0.1:9222`，且 `/json/version` 和 CDP WebSocket 可直连；
  失败发生在 Chrome 页面目标刚启动时的 CDP 握手竞争。
- 已在 Artemis 的浏览器会话创建处为 `InvalidMessage` / opening-handshake 类错误增加一次
  短暂重试；重启服务后需重新验证浏览器工作台。

---

## 八、华为 MaaS 限流与轻量代码问答（2026-09-10）

### 1. `/new` 的实际作用与限制

- `/new` 会把当前企微会话重新绑定到新的 thread，旧对话和工具结果不再带入。
- 它**不会**清除华为 MaaS API Key 的分钟级 TPM 窗口；刚触发 429 后立即 `/new` 仍可能继续限流。
- 新 thread 也可能被长期记忆检索补入旧业务答案；关闭 Agent 记忆后才会停止这部分注入。

### 2. 429 的量化证据

华为 DeepSeek Flash 的一次企微代码问答中，前三次模型调用输入分别约为：

```
14,553 + 21,689 + 25,512 = 61,754 token
```

这还未计输出，已经超过 MaaS 的 `60,000 TPM` 限制。消耗主要来自工具定义、skills、
子智能体、长对话/工具结果与记忆命中；最终自然语言回答的几百字不是主因。

### 3. 已实现：企微 final_only 与 Agent 轻量预设

`final_only` 让企微立即确认收到、Agent 内部执行、完成后以独立消息发送最终答案，避免
企微流式更新超过十分钟失效。实现中修复了：

- 网关传入 `InboundMessage` 时不能再按字典读取；
- final_only 必须聚合最终正文，不能在无 `MESSAGE` 时回退为 `✅`；
- 新企微主动消息客户端不能继承失效的本地 HTTP 代理；
- 浏览器 CDP 连接将 loopback 加入 `NO_PROXY`，并对短暂握手失败重试和按 profile 串行创建。

小G现已写入 Agent 级配置：

```json
{
  "execution_profile": "lean_code_qa",
  "memory": { "memory_enabled": false },
  "max_input_length": 16000
}
```

轻量预设在 Agent 编辑页的“高级选项 → 执行策略”中可选；启动时禁用非代码内置工具、
附加“读取文件后才下结论，证据不足不猜”的提示，并使用更低的上下文上限。递归上限
属于独立安全设置，不应被预设强制压低，否则多文件代码问答会在总结前中断。

### 4. 仍未彻底解决：按 TPM 等待而非 429

`max_iters` 是 LangGraph 图递归步数，不等同于模型调用次数。设得过低会导致
`GraphRecursionError`；设得高又可能再次超出 MaaS TPM。它只能作为保护，不能替代限流器。

正确的长期方案是：在 `harness-agent` 的共享 `ChatModelFactory` / 模型请求 middleware 中，
按 Provider/API Key 维护滑动 token 窗口；调用前预留输入和输出 token，接近 60k TPM 时
排队等待窗口释放。当前 Artemis 工作区只包含已安装的 `harness-agent` wheel，未挂载其源码；
不得将临时 `.venv/site-packages` 修改当作正式实现。需要取得 `harness-agent` 源码并在其
模型 factory 层实现、测试和发布该限流器。

---

## 九、LiteLLM 中转验证与后续代码问答预检（2026-09-10）

### 1. LiteLLM 模型的验证结果

- `liteLLM/gpt-5.6-luna` 可正常返回，但曾直接给出“通常情况下”的泛化业务回答，未读代码。
- `liteLLM/DeepSeek-V4-Pro` 可完成多轮 HTTP 调用，且没有华为 MaaS 的 60k TPM 429；但仍未
  稳定产生可核验的代码工具调用，部分回答声称“工作区没有 Gmeeting 源码”，这与实际已挂载的
  `/sp-service`、`/sp-web`、`/public`、`/common`、`/manage-service` 代码根不符。
- 因此，中转模型即使能返回文本或多轮响应，也不能视为可靠的 function calling / 代码问答模型。

### 2. 轻量代码问答预设的当前状态

- Agent 编辑页已新增“高级选项 → 执行策略”：`standard` / `lean_code_qa`。
- `lean_code_qa` 启动时会关闭长期记忆、设置 `max_input_length=16000`、禁用非代码内置工具，
  并附加“读取文件后才下结论、证据不足不猜”的系统规则。
- 不应由预设强制压低 `max_iters`：它是 LangGraph 图递归步数，过低会在最终总结前抛
  `GraphRecursionError`。迭代上限应作为独立安全配置保留用户值。
- 保存模型时可能将 `execution_profile` 覆盖回 `standard`；测试前必须检查编辑页仍选中
  “轻量代码问答（严谨）”。

### 3. 下一步：服务端代码问答预检（尚未实现）

为绕开中转模型 tool calling 不稳定，拟实现 Agent 级预检：

```
企微问题 → 服务端在 Agent 已配置的 BackendWorkspace 中受限搜索
         → 最多返回 3 个命中路径与短片段
         → 将证据注入模型上下文
         → 模型仅基于证据总结
```

预检必须走 `HarnessAgent.workspace` / `BackendWorkspace`，不得直接用 `Path` 读取 Agent
工作区内容；初期搜索范围为 `sp-service`、`sp-web`、`public`、`common`、`manage-service`。

### 4. 当前开发阻塞

本地命令执行桥接层在读取 `BackendWorkspace` API 前出现随机 `SyntaxError`，简单 shell 命令尚未
进入项目终端即失败；这不是 Artemis 服务、模型或企微问题。重新开启 Codex 对话后，应优先：

1. 阅读本节与 §八；
2. 验证命令执行是否恢复；
3. 检查 `harness_agent.backends.workspace.BackendWorkspace` 的搜索/读取 API；
4. 以测试先行实现服务端代码问答预检；
5. 不修改 `.venv` 或 `~/.cache/uv` 中的依赖源码。
