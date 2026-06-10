# 文件：plugins/google_meet/README.md

## 一句话定位

`plugins/google_meet/README.md` 是 `google_meet` 插件的架构说明和运维入口文档，用来解释 Hermes 如何加入 Google Meet、抓取字幕、可选地通过实时音频发言，以及如何把执行位置从 gateway 转移到远程 node host。

## 它暴露/定义了什么

这个文件本身不暴露 Python API，也不参与运行时加载；它定义的是插件使用者和维护者需要理解的“能力边界”。README 把插件拆成三层版本能力：v1 是 Playwright/Chromium 加入会议并抓取 captions 写入 transcript；v2 是 `mode='realtime'` 下接入 OpenAI Realtime 和虚拟音频设备，让 `meet_say` 能把文本转成会议内语音；v3 是通过 node 模式，把真正运行浏览器和音频桥的机器从 Hermes gateway 分离出去。

它还列出插件的文件分工：`__init__.py` 负责注册工具、CLI 和生命周期 hook；`tools.py` 是 agent-facing tool handler；`process_manager.py` 管理本地 bot 子进程；`meet_bot.py` 是实际运行 Playwright 的 bot；`cli.py` 提供 `hermes meet ...` 命令；`node/*` 处理远程节点注册、协议、client/server；`audio_bridge.py` 和 `realtime/openai_client.py` 支撑 realtime 发声链路。换句话说，README 是这组文件的总目录和设计合同。

## 谁调用它

严格来说，运行时没有代码“调用” `README.md`。根据当前片段推断，它的消费者主要是三类：开发者阅读插件架构和修改边界；用户按其中的 CLI 命令完成安装、授权、加入、发言、停止和 node 配置；agent/插件作者参考其中的工具名和参数理解 `meet_join`、`meet_status`、`meet_transcript`、`meet_leave`、`meet_say` 的语义。

真正被插件系统调用的是 `plugins/google_meet/__init__.py` 里的 `register(ctx)`，而不是 README。README 描述的内容需要和 `register(ctx)`、`tools.py`、`cli.py` 保持一致，否则会造成文档承诺与实际工具面不匹配。

## 它调用谁

`README.md` 不调用任何模块。它描述的运行链路中，实际调用关系是：Hermes 插件加载器调用 `register(ctx)`；`register(ctx)` 调用 `ctx.register_tool` 注册 5 个工具，并调用 `ctx.register_cli_command` 注册 `hermes meet` CLI，同时注册 `on_session_end` hook。工具 handler 在 `tools.py` 中根据是否传入 `node` 分流：本地路径调用 `process_manager.py`，远程路径通过 `node/client.py` 调用 node server。`process_manager.py` 再启动 `python -m plugins.google_meet.meet_bot`，由 `meet_bot.py` 负责 Playwright 浏览器、字幕抓取和 realtime speaker。

## 核心流程

本地 transcribe 流程是：用户或 agent 发起 `meet_join`，`tools.py` 校验 URL、mode 和本地依赖，然后调用 `process_manager.start()`。该函数保证单活会议语义，必要时先停止旧 bot，再创建 `$HERMES_HOME/workspace/meetings/<meeting-id>/`，清理旧的 `transcript.txt` 和 `status.json`，通过环境变量把会议链接、输出目录、guest name、duration、mode 等配置传给 `meet_bot.py`，最后用 detached subprocess 启动 bot，并写入 `.active.json`。之后 `meet_status` 读 `.active.json` 和 `status.json`，`meet_transcript` 读 `transcript.txt`，`meet_leave` 终止子进程并清理 active pointer。

Realtime 流程在本地流程上额外启用音频桥。README 描述 Linux 使用 PulseAudio null-sink，macOS 使用 BlackHole；`meet_say` 不直接对浏览器说话，而是把文本追加到 `say_queue.jsonl`，由 bot 内的 `RealtimeSpeaker` 读取队列，连接 OpenAI Realtime，生成 PCM，再送入虚拟麦克风。

Remote node 流程中，gateway 不直接运行 Chromium。`meet_join(..., node='name')` 经 `_resolve_node_client()` 从 `NodeRegistry` 找到 node 配置，再用 `NodeClient.start_bot()` 通过 WebSocket 请求 node host 上的 `NodeServer`。node server 收到请求后在远程机器调用同一套 `process_manager.start()`/`meet_bot.py` 链路。status、transcript、say、stop 也走同一套 RPC 转发。

## 关键函数的高层作用

`register(ctx)` 是插件入口，决定当前平台是否支持，并把工具、CLI 和 session-end 清理 hook 注入 Hermes。这里的平台 no-op 很关键，因为 Windows 音频和浏览器路径未被支持。

`handle_meet_join()` 是 agent 工具的主要入口，负责参数校验、node 分流和本地依赖检查。它不直接操作浏览器，而是把启动交给 `process_manager.start()` 或远程 `NodeClient.start_bot()`。

`process_manager.start()` 是本地生命周期核心：做 URL 安全门、单活替换、输出目录准备、环境变量组装和 detached subprocess 启动。它是 README 中“bot runs in parallel with the agent loop”的实际实现点。

`process_manager.status()`、`transcript()`、`stop()` 分别对应查询状态、读取字幕、结束会议；`enqueue_say()` 对应 realtime 模式下的发言队列写入。辅助函数如 `_read_active()`、`_write_active()`、`_pid_alive()` 只服务于状态文件和进程存活判断。

`NodeClient`、`NodeServer`、`NodeRegistry` 构成远程节点能力：registry 保存 gateway 可用节点，client 发送带 token 的请求，server 校验后执行本地 bot 管理动作。`AudioBridge` 和 `RealtimeSpeaker` 则构成发声链路的底层支撑。

## 修改风险

最大风险是 README 与代码行为漂移。比如 README 声称注册 5 个工具、支持 `mode='realtime'` 和 `node='<name>'`，实际必须与 `__init__.py`、`tools.py`、`cli.py`、`node/cli.py` 的参数和命令保持一致；否则用户会按文档执行但工具失败，agent 也可能基于错误能力描述规划动作。

安全边界也不能随意弱化。README 明确强调只接受显式 Google Meet 链接、不扫描日历、不自动拨号、不自动同意公告、node server 只做 bearer-token auth 且不内置 TLS。修改 URL gate、node 认证、自动加入策略或 consent 行为，都属于高风险改动，会影响隐私和会议安全。

生命周期风险集中在单活会议和清理逻辑。`process_manager` 依赖 `.active.json`、pid 检测、SIGTERM/SIGKILL 和 session-end hook 避免遗留浏览器进程；如果 README 或代码鼓励多会议并发，就需要重新设计状态文件、输出目录、队列和 stop/status 语义。

Realtime 风险更高，因为它跨 OpenAI Realtime、PCM 文件、系统虚拟音频设备和浏览器 fake mic。README 中对 Linux/macOS 的差异说明不是装饰性文字，特别是 macOS 不自动切换系统输入设备这一点，修改时要避免产生惊讶副作用。Remote node 还涉及 token 保存、LAN 暴露和一端 gateway 一端 host 的故障定位，文档应继续清楚标注其信任边界。
