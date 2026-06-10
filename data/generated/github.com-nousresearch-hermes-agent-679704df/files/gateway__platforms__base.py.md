# 文件：gateway/platforms/base.py

## 一句话定位

`gateway/platforms/base.py` 是 Hermes Gateway 的平台适配器基类和消息收发公共层：它把 Telegram、Discord、Slack、WeCom、Matrix、API Server 等不同平台的输入统一成 `MessageEvent`，把 Agent 返回的文本、图片、音频、视频、文档再按平台能力分发出去。

## 它暴露/定义了什么

该文件主要定义四类内容。

第一类是平台无关的数据模型：`MessageType` 表示文本、图片、语音、文件等消息类型；`ProcessingOutcome` 表示处理成功、失败、取消；`MessageEvent` 是所有平台入站消息的标准形态，包含 `text`、`source`、`message_id`、`media_urls`、`reply_to_*`、`auto_skill`、`channel_prompt` 等；`SendResult` 是所有发送动作的统一返回值；`EphemeralReply` 是可自动删除的系统提示回复。

第二类是 `BasePlatformAdapter` 抽象基类。子类必须实现 `connect()`、`disconnect()`、`send()`、`get_chat_info()`，可按平台能力覆写 `send_image_file()`、`send_voice()`、`send_video()`、`send_document()`、`edit_message()`、`delete_message()`、`send_draft()` 等。

第三类是通用工具函数：代理解析 `resolve_proxy_url()`、`proxy_kwargs_for_aiohttp()`，媒体缓存 `cache_image_from_url()`、`cache_audio_from_url()`、`cache_document_from_bytes()`，媒体路径安全校验 `validate_media_delivery_path()`，消息切分 `truncate_message()`，以及 `extract_media()`、`extract_images()`、`extract_local_files()` 等响应内容解析器。

第四类是会话并发控制逻辑：活跃会话锁、pending 消息队列、文本 debounce、typing 指示器、取消和后台任务清理都集中在基类里，避免每个平台重复实现。

## 谁调用它

最直接的调用者是各平台适配器，例如 `gateway/platforms/telegram.py`、`slack.py`、`discord` 相关实现、`weixin.py`、`wecom.py`、`feishu.py`、`matrix.py`、`api_server.py` 等都继承 `BasePlatformAdapter`。

`gateway/run.py` 的 `GatewayRunner._create_adapter()` 根据 `Platform` 创建具体 adapter，并通过 `set_message_handler()` 把网关的消息处理函数注入 adapter。之后每个平台在收到真实平台事件时构造 `MessageEvent`，调用 `handle_message()` 进入统一处理流。

`gateway/stream_consumer.py` 也依赖这个基类判断 adapter 是否支持 draft streaming、edit streaming、delete preview、附件过滤等能力。

## 它调用谁

入站侧，它调用 `gateway.session.build_session_key()` 根据 `SessionSource` 建立会话粒度，调用注入的 `_message_handler`，也就是 `GatewayRunner` 侧的 Agent/命令处理入口。

出站侧，它最终调用子类实现的 `send()`、`send_image_file()`、`send_voice()`、`send_video()`、`send_document()` 等平台 API 封装。媒体下载调用 `httpx`，SSRF 防护依赖 `tools.url_safety.is_safe_url`。自动 TTS 路径调用 `tools.tts_tool`。clarify fallback 会调用 `tools.clarify_gateway.mark_awaiting_text()`。运行状态和平台锁会调用 `gateway.status`。配置读取涉及 `gateway.config`、`hermes_cli.config`、`hermes_constants`。

## 核心流程

平台子类收到外部消息后，先把平台原始事件转换为 `MessageEvent`，再调用 `handle_message(event)`。`handle_message()` 会先把少数 DM 文本管理短语转换成 slash command，再执行 topic recovery，随后通过 `build_session_key()` 得到会话键。

如果该 session 已有 Agent 正在处理，基类不会再并发启动一个 Agent，而是进入 active-session 分支：`/stop`、`/new`、`/reset`、`/approve`、`/deny`、`/status` 等可绕过忙碌保护；clarify 等待文本时也会直通；普通文本和图片则合并进 pending 队列，等待当前轮结束后级联处理。

如果 session 空闲，`handle_message()` 会同步登记 active guard，然后启动 `_process_message_background()`。后台任务会启动 typing 指示器，调用 `_message_handler(event)` 获取 Agent 或命令响应，然后解析响应中的文本、图片 URL、`MEDIA:<path>`、本地文件路径和 TTS 指令。文本通过 `_send_with_retry()` 发送；图片、视频、音频、文档按扩展名和平台能力路由到对应发送方法。最后执行 post-delivery callback、停止 typing、清理会话锁，并处理期间积压的 pending 消息。

## 关键函数的高层作用

`handle_message()` 是入站总入口，核心职责是会话串行化、忙碌时命令绕过、pending 消息排队和后台任务启动。

`_process_message_background()` 是真正的处理管线，负责调用 Agent/命令处理器、发送文本和附件、处理自动 TTS、运行生命周期 hook，并在 finally 阶段清理任务和接续 pending 消息。

`_send_with_retry()` 为子类 `send()` 加一层通用可靠性：连接类错误会指数退避重试，格式类失败会尝试纯文本 fallback，超时类错误默认不重试以避免重复发消息。

`extract_media()`、`extract_images()`、`extract_local_files()` 把 Agent 输出里的附件意图提取出来，并返回清理后的可见文本。`filter_media_delivery_paths()` 和 `filter_local_delivery_paths()` 再统一做本地路径安全校验。

`validate_media_delivery_path()` 是出站附件安全边界，阻止模型把 `/etc`、`/proc`、`~/.ssh`、Hermes 凭据等敏感路径作为文件上传；非 strict 模式允许普通现有文件，strict 模式要求来自缓存、allowlist 或近期生成。

`truncate_message()` 负责长消息拆分，尽量保留换行、空格、代码块和 inline code 边界；平台可用 `message_len_fn` 改变长度计量方式，例如 Telegram 使用 UTF-16 code units。

`_keep_typing()` 周期性刷新 typing 状态，并支持 approval 等场景暂停 typing，防止平台 UI 被“正在输入”状态阻塞。

`send_draft()`、`supports_draft_streaming()`、`edit_message()`、`delete_message()` 是流式输出能力扩展点；默认实现保守，支持的平台自行覆写。

辅助函数如 `resolve_channel_prompt()`、`resolve_channel_skills()`、`merge_pending_message_event()`、`cache_*()`、`safe_url_for_log()` 主要服务配置解析、消息合并、媒体缓存和日志安全，不改变主流程结构。

## 修改风险

最大风险是会话并发。`_active_sessions`、`_session_tasks`、`_pending_messages`、文本 debounce 和 finally 中的 late-arrival drain 共同保证同一 session 不会并发跑多个 Agent。随意改动锁释放、任务 ownership 或 pending drain，容易造成重复回复、消息丢失、`/approve` 死锁、`/stop` 不生效，甚至旧 gateway 退出后仍继续处理消息。

第二个风险是附件安全。`MEDIA_DELIVERY_EXTS`、`MEDIA_TAG_CLEANUP_RE`、`extract_media()`、`extract_local_files()` 和 `validate_media_delivery_path()` 是联动的；只改其中一个可能导致文件被静默吞掉、未知扩展被错误清理，或让模型输出的敏感路径被上传到聊天平台。

第三个风险是平台兼容性。基类默认 fallback 很多，子类只覆写必要能力；如果改变 `send()`、`SendResult`、`reply_to`、`metadata`、`thread_id` 约定，会影响 Telegram topics、Slack threads、Feishu replies、streaming edit、ephemeral delete 等多个平台。

第四个风险是重试语义。发送超时可能已经到达平台，所以 `_send_with_retry()` 特意不把 read/write timeout 当作安全重试；放宽这里会带来重复消息。相反，把 retryable 判断改得过窄，会让临时网络抖动直接表现为回复丢失。

第五个风险是把新平台逻辑塞进基类。这个文件已经承担大量公共职责，新增平台特例应优先放在对应 adapter；只有跨平台语义、统一安全边界或所有 adapter 都需要的能力，才适合进入 `gateway/platforms/base.py`。
