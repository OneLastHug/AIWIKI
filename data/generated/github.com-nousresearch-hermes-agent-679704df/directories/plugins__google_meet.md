# 目录：plugins/google_meet

## 它负责什么

`plugins/google_meet` 是 Hermes 的 Google Meet 会议插件，目标是让 agent 在用户显式提供会议入口的前提下加入会议、抓取实时字幕、读取会议转录，并在 realtime 模式下把 agent 生成的语音送回会议。它不是日历集成，也不做自动拨入；从 `README.md`、`plugin.yaml` 和 `tools.py` 看，它强调“explicit-by-design”：只处理用户传入的 Meet 地址，不扫描日历，不自动同意或自动播报同意声明。

这个目录同时覆盖三层能力：第一层是 v1 转录模式，核心是 Playwright 启动 Chromium，进入会议，开启/观察 Meet 字幕 DOM，把字幕写入 `transcript.txt`；第二层是 v2 realtime 语音模式，通过 `AudioBridge`、`RealtimeSession`、`RealtimeSpeaker` 将文本转为 PCM 音频，再输入到 Chrome 的虚拟麦克风；第三层是 v3 remote node host，让 Meet bot 可以运行在另一台机器上，例如 gateway 在 Linux 服务器上，而登录了 Google 的 Chrome 配置在用户 Mac 上。

插件整体遵循 Hermes 通用 plugin 机制：`register(ctx)` 注册工具、CLI 命令和生命周期 hook；agent 侧通过 `meet_join`、`meet_status`、`meet_transcript`、`meet_leave`、`meet_say` 这组工具操作会议；CLI 侧通过 `hermes meet ...` 做安装、登录、启动、状态查看、远端 node 管理等运维动作。

## 直接子目录地图

`plugins/google_meet` 本身是插件主体目录，放置 manifest、注册入口、agent 工具、CLI、进程管理、Playwright bot 和音频桥接代码。

`plugins/google_meet/node` 是远端节点子包，负责 gateway 到 node host 的 WebSocket RPC。它包含协议封装、客户端、服务端、本地节点注册表和 `hermes meet node ...` CLI 子命令。这个子包的角色是把原本本地调用 `process_manager` 的动作，转发到另一台真正运行 Chrome/Playwright 的机器上。

`plugins/google_meet/realtime` 是 realtime 语音子包，当前关键文件是 `openai_client.py`。它负责连接 OpenAI Realtime WebSocket，把待说文本变成音频流，并通过文件队列与 bot 进程协作。这里不负责会议加入，也不负责音频设备创建；设备层在 `audio_bridge.py`。

## 关键入口

`plugins/google_meet/plugin.yaml` 是插件 manifest，描述能力、模式和边界。它对理解插件定位很重要，尤其是“transcribe-only 默认、realtime 可选、remote node 可选”的分层。

`plugins/google_meet/__init__.py` 是 Hermes 插件加载入口。`register(ctx)` 会先按平台过滤，只在 Linux 和 macOS 注册；然后把五个工具注册到 `google_meet` toolset：`meet_join`、`meet_status`、`meet_transcript`、`meet_leave`、`meet_say`；再注册 `meet` CLI 命令；最后注册 `on_session_end` hook，用于会话结束时尽量清理仍在运行的 Meet bot。

`plugins/google_meet/tools.py` 是 agent 面向的主入口。它定义五个 tool schema 和对应 handler。handler 里有一个重要分岔：如果参数里指定 `node`，会通过 `NodeRegistry` 找节点、构造 `NodeClient`，把操作发给远端；如果没有 `node`，就走本地 `process_manager`。所以阅读 agent 行为时，`tools.py` 是第一站。

`plugins/google_meet/cli.py` 是用户命令行入口，挂在 `hermes meet` 下。它负责 setup/install/auth/join/status/transcript/say/stop，以及把 `node` 子命令接入进来。它和 `tools.py` 使用同一套底层 `process_manager`，只是面向人工操作。

`plugins/google_meet/process_manager.py` 是本地生命周期中心。它负责单活会议语义、启动 `python -m plugins.google_meet.meet_bot` 子进程、维护 `$HERMES_HOME/workspace/meetings/.active.json`、读取 `status.json` 和 `transcript.txt`、向 `say_queue.jsonl` 追加待说文本、以及停止进程。

`plugins/google_meet/meet_bot.py` 是真正加入会议的 bot 程序入口，主函数是 `run_bot()`。它从环境变量读取会议 URL、输出目录、模式、guest name、duration、realtime 参数，启动 Playwright Chromium，尝试进入会议，注入字幕观察 JS，循环抓取字幕并写状态文件。realtime 模式下，它还会创建音频桥、启动 speaker 线程，并支持检测人声插话时取消正在生成的音频。

## 主流程位置

本地转录主流程可以从 `tools.py` 的 `handle_meet_join()` 看起：参数校验后调用 `process_manager.start()`；`start()` 校验会议地址、停止已有会议、创建会议输出目录、写环境变量，然后用 detached subprocess 启动 `plugins.google_meet.meet_bot`；`meet_bot.run_bot()` 启动浏览器、进入会议、注入 `_CAPTION_OBSERVER_JS`，主循环中调用 `window.__hermesMeetDrain()` 拉取字幕队列，交给 `_BotState.record_caption()` 写入 `transcript.txt` 和 `status.json`。随后 `meet_status`、`meet_transcript` 分别从 `process_manager.status()` 和 `process_manager.transcript()` 读取这些文件。

停止流程在 `handle_meet_leave()` 到 `process_manager.stop()`。它读取 `.active.json`，给 bot 进程发 `SIGTERM`，等待退出，必要时 `SIGKILL`，最后清除 active 指针。`__init__.py` 的 `_on_session_end()` 也会复用这条停止路径，避免会话结束后遗留 Chromium。

realtime 说话流程从 `handle_meet_say()` 到 `process_manager.enqueue_say()`，本质是把文本写入当前会议目录下的 `say_queue.jsonl`。`meet_bot.run_bot()` 在 realtime 启用时调用 `_start_realtime_speaker()`，后者使用 `realtime/openai_client.py` 里的 `RealtimeSpeaker` 轮询队列、调用 `RealtimeSession.speak()`，把 OpenAI Realtime 返回的 PCM 写到音频 sink；`audio_bridge.py` 则负责让 Chrome 的 fake mic 能读到这路音频。

远端 node 流程在 `node` 子包。gateway 侧 `tools.py` 通过 `_resolve_node_client()` 找到 `nodes.json` 中的节点，`NodeClient` 每次打开一个短连接 WebSocket，发送 `start_bot`、`status`、`transcript`、`say` 等 RPC；node host 侧 `NodeServer` 校验 token 后调用本机 `process_manager`。根据当前片段推断，远端 node 的设计意图是“远端机器本地运行同一个 bot 生命周期”，依据是 `node/server.py` 明确把 RPC dispatch 到 `plugins.google_meet.process_manager`。

## 推荐阅读顺序

建议先读 `README.md` 和 `plugin.yaml`，建立插件能力边界：默认转录、可选 realtime、可选 remote node、显式 URL 输入。

第二步读 `__init__.py`，确认它如何接入 Hermes 插件系统：注册哪些 tools、CLI 和 hook，以及平台支持限制。

第三步读 `tools.py`，这是 agent 调用的门面。重点看五个 handler 如何在本地 `process_manager` 与远端 `NodeClient` 之间分流。

第四步读 `process_manager.py`，理解状态文件、会议输出目录、单活会议、子进程启动和停止策略。这里是连接 agent 工具与 bot 子进程的核心胶水层。

第五步读 `meet_bot.py` 的 `run_bot()`，只需抓主线：读取环境变量、启动 Playwright、加入会议、注入字幕观察器、主循环写 transcript/status、realtime 时启动 speaker。overview 阶段不必逐个研究 DOM selector 辅助函数。

第六步按需求分叉：如果关注远端运行，读 `node/protocol.py`、`node/client.py`、`node/server.py`、`node/registry.py`；如果关注语音回传，读 `audio_bridge.py` 和 `realtime/openai_client.py`。

## 常见误区

不要把它理解成 Google Calendar/Meet 自动助手。代码和文档都强调不扫描日历、不自动拨入，只接受显式传入的会议入口。

不要以为 `meet_join` 会阻塞直到会议结束。它启动的是后台 bot 子进程，然后立即返回；持续状态要用 `meet_status` 轮询，字幕要用 `meet_transcript` 读取。

不要把 `meet_say` 当成普通文本消息发送。它只在 active meeting 以 `mode='realtime'` 启动后才有意义，本地路径会检查 active 记录里的 `mode`；转录模式下调用会返回“需要 realtime”的错误。

不要忽略平台限制。`__init__.py` 只在 Linux/macOS 注册插件；`audio_bridge.py` 也围绕 PulseAudio 和 BlackHole 设计。Windows 不是当前支持目标。

不要把 `node` 模式理解成多租户调度系统。当前设计是一个 node host 暴露 token 保护的 WebSocket RPC，然后在本机用同一套 `process_manager` 管一个 active meeting；README 也说明一对 gateway/node 同时只处理一个会议。

根据当前片段推断，远端 realtime 模式需要额外留意：`NodeClient.start_bot()` 会发送 `mode`，但 `NodeServer._handle_request()` 的 `start_bot` 参数白名单片段里没有把 `mode` 传给 `pm.start()`。如果实际代码未在其他位置补齐，远端 node 上可能默认按 transcribe 启动。这一点的依据是当前看到的 `node/client.py` 与 `node/server.py` 参数转发实现不完全一致。
