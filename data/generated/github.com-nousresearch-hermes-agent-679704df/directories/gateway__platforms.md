# 目录：gateway/platforms

## 它负责什么

`gateway/platforms` 是 Hermes gateway 的“平台适配层”。它把 Telegram、Slack、WhatsApp、Email、Matrix、API Server、Webhook、企业微信/微信、飞书、钉钉、QQBot、Yuanbao 等外部消息入口，统一转换成 gateway 内部能处理的标准事件，再把 agent 的回复转换回各平台自己的发送 API。

这个目录不负责核心对话推理，也不负责会话数据库本身；它的主要职责是：

- 连接和认证外部平台，例如长轮询、Webhook、WebSocket、HTTP API、IMAP/SMTP 等。
- 把平台消息规范化为 `MessageEvent`，并用 `SessionSource` 标记来源平台、chat、thread、sender 等。
- 调用 `BasePlatformAdapter.handle_message()` 把消息交给 `gateway/run.py` 的 `GatewayRunner._handle_message()`。
- 实现平台侧发送能力，例如 `send()`、`edit_message()`、`delete_message()`、`send_image()`、`send_document()`、`send_voice()`、`send_typing()`。
- 处理平台特有细节，例如消息长度限制、Markdown/纯文本格式差异、附件缓存、自消息过滤、授权策略、线程/话题、回执、临时提示、平台级重连等。

从架构上看，这里是“边界适配器”目录：对外贴近平台 SDK/API，对内贴近 `gateway.platforms.base` 定义的统一协议。

## 直接子目录地图

当前 `gateway/platforms` 下只有一个直接子目录：

- `gateway/platforms/qqbot`：QQBot 的多文件实现。它比普通单文件平台更复杂，所以拆成 `adapter.py`、`chunked_upload.py`、`constants.py`、`crypto.py`、`keyboards.py`、`onboard.py`、`utils.py` 等模块。主类是 `QQAdapter`，仍然继承 `BasePlatformAdapter`。

其余平台大多是单文件 adapter，直接放在 `gateway/platforms/*.py`。可以按角色粗略分组：

- 通用基础：`base.py`、`helpers.py`、`_http_client_limits.py`。
- HTTP/Webhook/API 入口：`api_server.py`、`webhook.py`、`msgraph_webhook.py`。
- 即时通讯平台：`telegram.py`、`slack.py`、`whatsapp.py`、`signal.py`、`matrix.py`、`bluebubbles.py`。
- 企业/国内平台：`dingtalk.py`、`feishu.py`、`feishu_comment.py`、`feishu_comment_rules.py`、`wecom.py`、`wecom_callback.py`、`wecom_crypto.py`、`weixin.py`、`yuanbao.py` 及其 `yuanbao_*` 辅助文件。
- 传统消息通道：`email.py`、`sms.py`、`homeassistant.py`。
- 开发说明：`ADDING_A_PLATFORM.md`。

## 关键入口

最重要的入口是 `gateway/platforms/base.py`。它定义了所有 adapter 必须遵守的公共模型和基类，包括：

- `MessageEvent`：平台入站消息的规范化表示。
- `MessageType`、`SendResult`、`EphemeralReply` 等通用结构。
- `BasePlatformAdapter`：所有平台 adapter 的基类。
- `BasePlatformAdapter.connect()`、`disconnect()`、`send()`：抽象方法，具体平台必须实现。
- 一批默认能力和扩展点，例如 `edit_message()`、`delete_message()`、`send_image()`、`send_document()`、`send_voice()`、`create_handoff_thread()`、`get_chat_info()`、`send_typing()` 等。
- 附件缓存与媒体类型支持，例如图片、音频、视频、文档的缓存与 MIME/扩展名处理。
- 消息发送的通用包装逻辑，例如分块、编辑、原生媒体发送、打字指示、临时消息、pending message 合并等。

每个平台文件通常有两个关键符号：

- `<Platform>Adapter` 类，例如 `TelegramAdapter`、`SlackAdapter`、`WhatsAppAdapter`、`APIServerAdapter`、`WebhookAdapter`、`YuanbaoAdapter`。
- `check_<platform>_requirements()` 函数，用来检查依赖包、环境变量或配置是否满足。

adapter 的实例化入口不在本目录，而在 `gateway/run.py` 的 `GatewayRunner._create_adapter()`。该函数先查 `gateway/platform_registry.py` 中插件注册的平台；如果没有命中，再走内置平台的 `if/elif` 分支，按 `Platform` 枚举导入对应 adapter。

平台枚举和配置结构在 `gateway/config.py`。其中 `Platform` 定义内置平台名，也通过 `_missing_()` 支持插件平台的动态枚举成员；`PlatformConfig`、`GatewayConfig` 和配置加载逻辑负责把 `config.yaml`、环境变量和插件平台配置合并成 gateway 可用的平台配置。

## 主流程位置

主流程可以从启动和消息收发两条线理解。

启动流程位于 `gateway/run.py` 的 `GatewayRunner.start()` 附近。它遍历 `self.config.platforms` 中启用的平台，对每个平台调用 `_create_adapter(platform, platform_config)`。创建成功后，runner 会给 adapter 注入多个回调和依赖：

- `adapter.set_message_handler(self._handle_message)`：入站消息最终进入 `GatewayRunner._handle_message()`。
- `adapter.set_fatal_error_handler(...)`：平台连接失败或运行中致命错误交给 gateway 统一处理。
- `adapter.set_session_store(self.session_store)`：让 adapter 能访问会话状态。
- `adapter.set_busy_session_handler(...)`：处理同一 session 正在运行时的新消息。
- 其他 topic recovery、busy mode、voice mode 等运行时状态。

之后 runner 调用 `_connect_adapter_with_timeout(adapter, platform)`，实际进入平台自己的 `connect()`。例如 Telegram 会启动 bot 接收更新，Webhook/API Server 会启动 aiohttp 服务，Email 会连接邮箱，Signal/QQBot/Yuanbao 等会启动各自的轮询或长连接逻辑。

入站消息流程通常是：

1. 平台 SDK/API 收到原始消息。
2. adapter 过滤自消息、无权限用户、无效事件、重复事件等。
3. adapter 构造 `MessageEvent(text=..., source=..., raw_message=..., media_urls=...)`。
4. adapter 调用 `self.handle_message(event)`。
5. `BasePlatformAdapter.handle_message()` 做会话并发、pending 合并、typing、附件和一些通用生命周期处理。
6. 消息进入 `GatewayRunner._handle_message()`，再由 gateway 建立/恢复 session、组装 prompt、调用 `AIAgent`。
7. agent 输出通过 runner 找回对应 adapter，再调用 adapter 的 `send()`、`edit_message()` 或媒体发送方法交付到平台。

出站流程的公共能力多数也在 `BasePlatformAdapter`，具体平台只覆盖必要部分。比如某些平台支持编辑消息，某些只能发新消息；某些平台支持 thread/topic，某些只能靠 `chat_id`；某些平台支持原生图片/文件，某些需要退化为链接或文本。

## 推荐阅读顺序

1. 先读 `gateway/platforms/base.py`：理解 `MessageEvent`、`BasePlatformAdapter`、`send()`、`handle_message()` 和媒体发送的公共协议。
2. 再读 `gateway/run.py` 的 `GatewayRunner.__init__()`、`GatewayRunner.start()`、`GatewayRunner._create_adapter()`、`GatewayRunner._handle_message()`：看 adapter 如何被创建、连接和接入 agent 主循环。
3. 接着读 `gateway/config.py` 的 `Platform`、平台配置加载、`get_connected_platforms()`：理解平台启用条件来自哪里。
4. 选择一个相对典型的平台读完整实现。建议先看 `gateway/platforms/webhook.py` 或 `gateway/platforms/email.py`，它们比 Telegram/Yuanbao 简单；再看 `gateway/platforms/telegram.py` 或 `gateway/platforms/slack.py` 了解复杂平台的线程、编辑、媒体和授权细节。
5. 如果关心扩展新平台，读 `gateway/platforms/ADDING_A_PLATFORM.md` 和 `gateway/platform_registry.py`。当前设计推荐插件路径：通过 `ctx.register_platform()` 注册，而不是直接改核心 `gateway/platforms`。
6. 最后再读 `gateway/platforms/qqbot/adapter.py` 或 `gateway/platforms/yuanbao.py` 这类复杂实现，它们适合理解大型平台集成的拆分方式，不适合入门。

## 常见误区

- 不要以为新增平台只要写一个 `gateway/platforms/<name>.py`。内置平台还要接入 `Platform` 枚举、`GatewayRunner._create_adapter()`、授权映射、系统提示、工具集等；更推荐走插件平台注册机制。
- 不要把平台原始消息直接传给 agent。所有 adapter 都应先转换成 `MessageEvent` 和 `SessionSource`，否则 session key、授权、附件、thread、回复上下文都会不稳定。
- 不要在 adapter 中重写核心对话流程。adapter 只做平台边界处理；agent 调用、session 管理、slash command、大部分 busy/interrupt 逻辑属于 `gateway/run.py` 和基类。
- 不要假设所有平台都支持同样的消息能力。`edit_message()`、`delete_message()`、thread、voice、document、typing、ephemeral notice 都可能在不同平台上退化为 no-op 或普通发送。
- 不要忽略 `check_<platform>_requirements()`。`_create_adapter()` 会用它决定平台是否可创建；依赖缺失或配置不完整时，应返回 `False` 并给日志留下清晰原因。
- 不要把 `gateway/platforms/base.py` 只看成抽象接口。它包含大量真实共享逻辑：附件缓存、分块发送、媒体发送降级、typing 生命周期、pending 消息合并、runtime status、平台锁等。很多“平台行为”其实已经在基类里实现。
- 根据当前片段推断，`gateway/platforms` 正在从硬编码内置平台逐步过渡到 `platform_registry` 插件化模式；依据是 `_create_adapter()` 先查 `platform_registry`，`Platform._missing_()` 支持插件平台，且 `ADDING_A_PLATFORM.md` 明确推荐插件路径。
