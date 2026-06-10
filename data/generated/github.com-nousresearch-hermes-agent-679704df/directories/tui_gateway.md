# 目录：tui_gateway

## 它负责什么

`tui_gateway` 是 Hermes TUI 的 Python 后端网关层，作用是在 Ink/React 终端界面和核心 Python agent 之间建立一条 JSON-RPC 通道。前端 `ui-tui` 负责显示、输入、快捷键和交互状态；`tui_gateway` 负责创建/恢复会话、构造 `AIAgent`、转发用户 prompt、把模型输出和工具事件流式推回前端，并复用 CLI 侧已有的 slash command、审批、sudo、secret、会话数据库、工具回调等能力。

它不是一个独立 UI，也不是模型运行时本身。它更像“协议适配 + 会话编排 + 事件总线”：一端接收 stdio 或 WebSocket 上的 JSON-RPC 请求，另一端调用 `run_agent.AIAgent`、`hermes_state.SessionDB`、`cli.HermesCLI`、`tools.approval`、`tools.delegate_tool` 等核心模块。

## 直接子目录地图

`tui_gateway` 当前没有直接子目录，是一个扁平 Python 包。主要文件角色如下：

`tui_gateway/entry.py` 是 stdio 模式入口，通常由 `hermes --tui` 间接启动。它负责启动时发送 `gateway.ready`、循环读取 stdin 的 JSON-RPC 行、调用 `server.dispatch()`，并把响应写回 stdout。

`tui_gateway/server.py` 是核心调度器和大部分业务逻辑所在，包含 JSON-RPC 方法注册、会话状态表、agent 构造、prompt 提交、工具/思考/状态事件、slash 命令桥接、图片附件、会话压缩、分支、子 agent 观察等。

`tui_gateway/transport.py` 抽象输出通道，提供 `Transport`、`StdioTransport`、`TeeTransport`，让同一套 `server.dispatch()` 可以跑在 stdio 或 WebSocket 上。

`tui_gateway/ws.py` 提供 WebSocket 版本的网关入口，复用 `server.dispatch()`，面向浏览器、移动端或 dashboard 侧边栏等非 stdio 客户端。

`tui_gateway/event_publisher.py` 是 dashboard PTY 场景下的旁路事件发布器，把 PTY 子进程里的事件通过 WebSocket best-effort 镜像出去。

`tui_gateway/slash_worker.py` 是持久 slash command 子进程。每个 TUI session 可维护一个 `HermesCLI` 实例，用 JSON 行协议执行 `/command`，从而复用传统 CLI 命令实现。

`tui_gateway/render.py` 是渲染桥，尝试调用 `agent.rich_output` 的 Python 渲染器；不可用时返回 `None`，让前端回退到自己的 markdown 渲染。

`tui_gateway/__init__.py` 只是包标记。

## 关键入口

最重要的入口是 `tui_gateway/entry.py` 的 `main()`。它会先安装 dashboard sidecar publisher，按配置决定是否后台发现 MCP tools，然后向前端发送 `gateway.ready` 事件，之后逐行读取 JSON-RPC 请求。每个请求经过 JSON 解析后交给 `tui_gateway.server.dispatch()`，如果该方法同步返回响应，就通过 `write_json()` 写回前端；长耗时方法会由 `server.py` 放到线程池里异步写回。

WebSocket 场景入口是 `tui_gateway/ws.py` 的 `handle_ws()`。它接受连接后同样先发 `gateway.ready`，然后读取文本帧、解析 JSON、调用 `server.dispatch(req, transport)`。这里的关键点是：WebSocket 没有另一套业务实现，只是换了 transport。

核心注册入口在 `tui_gateway/server.py` 的 `method(name)` 装饰器和 `_methods` 表。诸如 `session.create`、`session.resume`、`prompt.submit`、`slash.exec`、`approval.respond`、`session.interrupt` 等 JSON-RPC 方法都通过这个机制注册。

## 主流程位置

启动流程主要在 `tui_gateway/entry.py`：`main()` 初始化 sidecar、MCP 后台发现、发送 `gateway.ready`，然后进入 stdin JSON-RPC 循环。输出最终由 `tui_gateway/server.py` 的 `write_json()` 走 `tui_gateway/transport.py` 中当前绑定的 transport。

请求分发流程在 `tui_gateway/server.py`：`dispatch()` 会校验请求、查 `_methods`，并根据方法是否属于长耗时集合决定同步执行还是丢给线程池。这样 `prompt.submit`、`slash.exec`、`session.resume` 等可能耗时的操作不会堵住审批、interrupt 等控制请求。

会话创建流程在 `server.py` 的 `@method("session.create")`。它先生成短 session id 和持久 session key，立刻返回一个 lightweight session，让 TUI 能先绘制界面；随后用定时器触发 `_start_agent_build()`，最终通过 `_make_agent()` 创建 `AIAgent`，并在 `_init_session()` 中安装回调、slash worker、approval 通知和 session info 事件。

恢复流程在 `@method("session.resume")`。它从 `SessionDB` 查找历史 session，读取历史消息，调用 `_make_agent()` 以原 session id 继续运行，再通过 `_init_session()` 把内存态会话接回 TUI。

对话主流程在 `@method("prompt.submit")` 及其内部的 `_run_prompt_submit()`。它会检查 session 是否 busy，整理历史、附件图片和当前输入，触发 `message.start`，调用 `agent.run_conversation()`，通过 stream callback 发出 `message.delta`，最后发出 `message.complete`，并处理 usage、reasoning、auto title、goal continuation、TTS、通知队列等后置逻辑。

工具和状态事件的主位置在 `_agent_cbs()`、`_on_tool_start()`、`_on_tool_complete()`、`_on_tool_progress()`。这些回调被传给 `AIAgent`，再通过 `_emit()` 转成 TUI 可消费的 `tool.*`、`reasoning.delta`、`status.update` 等事件。

slash command 流程在 `server.py` 的 `_SlashWorker` 和 `tui_gateway/slash_worker.py`。TUI 发 `slash.exec` 后，网关把命令送进持久 `HermesCLI` 子进程，捕获 Rich/CLI 输出，再把文本结果返回给前端。

## 推荐阅读顺序

建议先读 `tui_gateway/entry.py`，理解 stdio 网关如何启动、如何收发 JSON-RPC。第二步读 `tui_gateway/transport.py`，明确为什么 server 逻辑不直接写 stdout。第三步读 `tui_gateway/server.py` 顶部的 dispatch、`method()`、`write_json()`、`_emit()` 等基础设施。第四步跳到 `session.create`、`session.resume`、`_make_agent()`、`_init_session()`，建立 session 生命周期模型。第五步读 `prompt.submit` 和 `_run_prompt_submit()`，这是用户输入到 agent 输出的核心链路。最后再看 `slash_worker.py`、`ws.py`、`event_publisher.py`，分别理解 CLI 命令复用、WebSocket 复用和 dashboard 旁路事件。

## 常见误区

不要把 `tui_gateway` 理解成 TUI 前端。真正的终端界面在 `ui-tui/src`，这里负责 Python 后端和协议桥接。

不要在 dashboard 中重写聊天主界面来绕过它。根据仓库说明，dashboard 的 `/chat` 嵌入真实 `hermes --tui`，主 transcript、composer、slash 行为属于 Ink/TUI 与 `tui_gateway` 这条链路。

不要认为 stdio 和 WebSocket 是两套协议。根据当前片段推断，`ws.py` 明确复用 `server.dispatch()`，wire protocol 也保持 newline-delimited JSON-RPC；差异主要是 transport。

不要把 slash command 当成 `server.py` 里完全重写的命令。它通过 `slash_worker.py` 持久化一个 `HermesCLI`，目的是复用 CLI 命令注册和输出行为。

不要忽视异步事件和控制请求的并发关系。`prompt.submit` 这类长任务会进入线程，`session.interrupt`、approval 响应等控制通道需要保持可处理；这也是 `server.py` 里长耗时方法集合和 transport context 存在的原因。
