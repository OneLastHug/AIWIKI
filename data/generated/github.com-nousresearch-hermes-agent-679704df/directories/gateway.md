# 目录：gateway

## 它负责什么

`gateway` 是 Hermes Agent 的“消息平台网关”层，负责把 Telegram、Slack、WhatsApp、Matrix、Email、Webhook、API Server 等外部消息平台接入统一的 Agent 会话循环。它不实现核心 LLM 推理本身，而是处理平台连接、消息接收、鉴权、会话归属、命令分流、上下文注入、流式/草稿回复、媒体投递、重启/停止、运行状态和跨平台投递。

从职责上看，它处在三层之间：上游是各个平台的 webhook、polling 或长连接；中间是 `gateway.platforms.base.BasePlatformAdapter` 和 `gateway.run.GatewayRunner`；下游是 `AIAgent`、工具系统、会话数据库和发送工具。一个外部消息进入后，会先被平台适配器规范化为 `MessageEvent`，再由 `GatewayRunner._handle_message()` 进入统一处理管线，最终通过平台适配器把结果发回原聊天或转发到配置的目标平台。

这个目录还承担“长期运行进程”的工程工作：PID 文件、运行锁、计划停止标记、系统信号、内存监控、cron ticker、MCP discovery、平台 fatal error 处理、重启接管、旧 gateway 替换，以及 gateway 专用日志。

## 直接子目录地图

`gateway/assets` 存放网关相关静态辅助资源，目前可见的是 Telegram BotFather 线程设置截图，用于配置或文档辅助，不是运行主路径。

`gateway/builtin_hooks` 是内置 gateway hooks 的扩展点。当前目录很轻，主要表示框架预留了“总是注册”的 gateway hook 位置，真正的插件 hook 调用集中在 `gateway/run.py` 与通用插件系统交互处。

`gateway/platforms` 是各平台适配器集合，也是阅读 gateway 时最重要的子目录。`gateway/platforms/base.py` 定义统一抽象：`MessageEvent`、`MessageType`、`SendResult`、`EphemeralReply`、`BasePlatformAdapter`，以及媒体缓存、发送重试、typing 状态、忙碌会话队列、后台消息处理等通用能力。具体平台文件如 `telegram.py`、`slack.py`、`whatsapp.py`、`email.py`、`api_server.py`、`webhook.py`、`dingtalk.py`、`feishu.py`、`wecom.py`、`weixin.py`、`signal.py`、`matrix.py`、`bluebubbles.py`、`yuanbao.py` 等负责把各自平台事件转换成统一事件，并实现平台原生发送、编辑、删除、媒体处理或鉴权策略。`gateway/platforms/qqbot` 是一个更复杂的平台子包。

## 关键入口

`gateway/run.py` 是进程入口和主控制器所在地。文件顶部说明了两种启动方式：`python -m gateway.run` 或 CLI 的 gateway 模式。关键函数是 `start_gateway()` 和 `main()`；关键类是 `GatewayRunner`。`main()` 只做参数解析和配置加载，然后用 `asyncio.run(start_gateway(config))` 启动。`start_gateway()` 负责环境准备、日志、PID/运行锁、signal handler、MCP discovery、cron ticker、内存监控、启动和关闭流程。`GatewayRunner.start()` 负责根据 `GatewayConfig.platforms` 创建并连接各个平台适配器。

`gateway/config.py` 是配置入口。它定义 `Platform`、`PlatformConfig`、`GatewayConfig`、`HomeChannel`、`SessionResetPolicy`、`StreamingConfig`，并通过 `load_gateway_config()` 从环境变量、`config.yaml`、遗留 `gateway.json` 和默认值合并出运行配置。平台是否“已连接”的判断也在这里集中处理：通用 token/api_key、平台特定 checker、以及插件平台注册项都会参与判断。

`gateway/session.py` 是会话入口。`SessionSource` 描述消息来自哪个平台、聊天、线程和用户；`build_session_key()` 是会话隔离规则的单一来源；`SessionStore` 维护 session key 到 session id 的映射、过期/重置策略、转录记录读写；`build_session_context()` 和 `build_session_context_prompt()` 把平台来源、可用平台、home channel 等信息注入给 Agent。

`gateway/platforms/base.py` 是适配器入口。新平台通常需要理解 `BasePlatformAdapter.connect()`、`disconnect()`、`send()`、`handle_message()` 这些方法。平台收到消息后一般构造 `MessageEvent`，调用 `adapter.handle_message(event)`，随后 base 层会做会话 key 计算、忙碌状态检查、命令绕过、文本 debounce、排队和后台任务创建。

`gateway/platform_registry.py` 是插件平台入口。内置平台仍有部分 legacy 创建逻辑，但插件平台通过 `PlatformEntry` 注册 adapter factory、配置校验、依赖检查、YAML 到 env 桥接、独立发送函数等元数据，再由 gateway 发现和创建。

## 主流程位置

启动主流程在 `gateway/run.py` 的 `start_gateway()`：加载配置和日志，处理旧进程替换，写 PID，发现 MCP tools，实例化 `GatewayRunner`，调用 `runner.start()`，再等待 shutdown。`GatewayRunner.start()` 遍历启用的平台配置，为每个平台创建 adapter，绑定 `adapter.set_message_handler(self._handle_message)`、fatal error handler、session store、busy session handler，然后执行连接。

入站消息主流程分两段。第一段在 `gateway/platforms/base.py` 的 `BasePlatformAdapter.handle_message()`：把平台事件归一化，计算 session key，判断该会话是否已有运行中的任务；若有运行中任务，则对 `/stop`、`/new`、`/reset`、`/approve`、`/deny` 等命令走绕过路径，对普通文本做排队或 debounce；若没有运行中任务，则调用 `_start_session_processing()` 创建后台处理任务。

第二段在 `gateway/run.py` 的 `GatewayRunner._handle_message()` 和 `_handle_message_with_agent()`：先执行插件 `pre_gateway_dispatch` hook，再做用户授权和配对逻辑，处理 update prompt、slash command、quick command、控制命令；如果不是命令，则设置 running-agent sentinel，进入 `_handle_message_with_agent()`。这里会创建或恢复 session，加载 transcript，准备入站文本和媒体信息，构造 session context，实例化或复用 `AIAgent`，运行对话，保存结果，再交由 adapter 发送回平台。

出站投递相关逻辑分散在 `gateway/platforms/base.py`、`gateway/delivery.py` 和具体平台 adapter 中。`DeliveryRouter` 负责按平台和 home channel 路由；具体发送、编辑、媒体附件、语音、文档、重试和分片主要由 `BasePlatformAdapter` 及各平台子类完成。

## 推荐阅读顺序

1. 先读 `gateway/run.py` 文件头、`GatewayRunner` 类注释、`start_gateway()` 和 `main()`，建立“这是一个长期运行 daemon”的整体印象。

2. 再读 `gateway/config.py` 的 `Platform`、`GatewayConfig`、`load_gateway_config()`，理解平台配置如何从 `config.yaml`、环境变量和插件注册合并出来。

3. 接着读 `gateway/session.py` 的 `SessionSource`、`build_session_key()`、`SessionStore.get_or_create_session()`、`build_session_context()`，这是理解“同一个用户/群/线程为什么进入同一个或不同会话”的关键。

4. 然后读 `gateway/platforms/base.py` 的 `MessageEvent`、`BasePlatformAdapter.handle_message()`、`_process_message_background()` 和 `send()` 系列方法，理解所有平台共享的消息排队、打字状态、发送重试、媒体处理和后台任务模式。

5. 最后按需要挑一个具体平台读，例如 `gateway/platforms/telegram.py` 或 `gateway/platforms/slack.py`。不要一开始就逐个平台看，否则容易陷入 API 细节，看不清统一抽象。

6. 如果关注扩展性，再读 `gateway/platform_registry.py` 和 `gateway/platforms/ADDING_A_PLATFORM.md`，理解插件平台如何注册，而不是直接改核心分发代码。

## 常见误区

误区一：把 `gateway` 当成 Agent 核心。实际上它主要是平台接入和会话调度层，真正的模型循环在 `run_agent.py`，工具调度在 `model_tools.py`。`gateway` 只是把平台消息变成 Agent 可处理的用户输入，再把 Agent 输出送回平台。

误区二：以为每个平台都各自完整处理会话。会话规则集中在 `gateway/session.py`，尤其是 `build_session_key()`；平台 adapter 只提供 `SessionSource` 的原始字段。群聊是否按用户隔离、线程是否共享，都由统一规则决定。

误区三：忽略 `BasePlatformAdapter.handle_message()`。很多“为什么消息被排队”“为什么 `/stop` 可以打断运行中任务”“为什么照片会合并”等行为，不在具体平台文件里，而在 base adapter 的共享管线里。

误区四：认为 slash command 都会进入 Agent。`GatewayRunner._handle_message()` 里有大量命令分流，很多命令直接由 gateway 处理，例如 `/status`、`/reset`、`/restart`、`/model`、`/approve`、`/deny`、`/sethome` 等。只有未被识别或显式允许落入对话的内容才进入 `_handle_message_with_agent()`。

误区五：新增平台时直接修改核心枚举和 if/elif。根据当前片段推断，项目正在向插件平台注册机制迁移，依据是 `Platform._missing_()` 支持动态平台、`platform_registry.py` 提供 `PlatformEntry`、并且注释说明插件 adapter 会先被查找。新增非核心平台应优先走插件注册路径。

误区六：只看 `gateway/platforms` 而不看 `gateway/config.py`。平台能否启动不仅取决于 adapter 文件存在，还取决于 `PlatformConfig.enabled`、token/api_key、平台特定 `extra` 字段、插件 `check_fn` 和 `validate_config`。配置没合并对，adapter 代码本身可能完全不会运行。
