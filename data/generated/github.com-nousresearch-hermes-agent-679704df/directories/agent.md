# 目录：agent

## 它负责什么

`agent` 是 Hermes Agent 的内部运行层，不是最外层用户入口。外部通常从 `run_agent.py` 的 `AIAgent`、`cli.py` 的交互 CLI、`gateway/` 的消息平台或 `batch_runner.py` 进入；进入后，大量真正的初始化、对话循环、模型请求构造、工具执行、上下文压缩、凭证恢复、provider 适配、技能与记忆辅助逻辑会下沉到 `agent` 目录。

从 `agent/__init__.py` 的说明看，这个目录承接了原先嵌在 `run_agent.py` 中的内部模块，目标是让 `run_agent.py` 更像 `AIAgent` 编排器，而不是把所有细节塞在一个巨型文件里。当前实现仍保留很多 `run_agent.py` forwarder：例如 `AIAgent.__init__` 转发到 `agent.agent_init.init_agent`，`AIAgent.run_conversation` 转发到 `agent.conversation_loop.run_conversation`，工具并发/串行执行转发到 `agent.tool_executor`。因此阅读时要把 `run_agent.py` 和 `agent` 看成一个整体：`run_agent.py` 提供兼容的公共壳，`agent` 提供主要运行部件。

这个目录的职责大致可分为六组：主循环与运行时状态、模型/provider 适配、工具调用执行与防护、上下文/记忆/技能管理、凭证与安全处理、辅助能力注册与后台任务。

## 直接子目录地图

`agent/lsp` 是语言服务器协议相关能力。它包含 `client.py`、`manager.py`、`servers.py`、`workspace.py`、`reporter.py`、`install.py` 等模块，用来管理 LSP server、工作区、诊断、安装和事件日志。它更像代码智能/诊断子系统，不是主对话循环本身。

`agent/secret_sources` 是密钥来源适配层。目前直接看到 `bitwarden.py`，说明这里用于把外部 secret manager 接入凭证读取链路。它和 `credential_sources.py`、`credential_pool.py`、`credential_persistence.py` 一起构成凭证来源、借用、持久化和恢复相关能力。

`agent/transports` 是 provider 通讯格式抽象层。`base.py` 定义 `ProviderTransport`，核心接口是 `convert_messages`、`convert_tools`、`build_kwargs`、`normalize_response`；`types.py` 定义跨 provider 的 `NormalizedResponse`、`ToolCall`、`Usage`。具体实现包括 `chat_completions.py`、`anthropic.py`、`bedrock.py`、`codex.py`、`codex_app_server.py` 等。根据当前片段推断，这一层负责把 Hermes 内部接近 OpenAI 格式的消息和工具定义转换为各后端需要的协议，再把响应统一回标准结构。

## 关键入口

`agent/agent_init.py` 是初始化入口。`init_agent(agent, ...)` 接收大量参数，负责给 `AIAgent` 填充模型、provider、API mode、toolsets、callbacks、session、iteration budget、context engine、credential pool、checkpoint、平台信息等状态。`run_agent.py` 中的 `AIAgent.__init__` 是薄包装，会直接调用这里。

`agent/conversation_loop.py` 是单轮或多轮 agent 主循环的核心位置。`run_conversation(agent, user_message, ...)` 负责准备消息历史、设置当前运行时主模型、恢复 primary runtime、清理输入、建立 task id、重置重试计数、处理 memory/todo hydration、执行 API 调用与工具调用循环，并最终返回 `final_response` 和 messages。它是理解“用户输入如何变成模型调用、工具调用、最终回答”的第一主线。

`agent/chat_completion_helpers.py` 是模型请求/响应辅助层。它包含 `build_api_kwargs`、`interruptible_api_call`、`interruptible_streaming_api_call`、`build_assistant_message`、`try_activate_fallback`、`handle_max_iterations` 等函数，负责构造请求参数、处理中断、streaming、fallback、assistant message 归一化和最大迭代收尾。

`agent/tool_executor.py` 是工具调用执行入口。`execute_tool_calls_concurrent` 和 `execute_tool_calls_sequential` 分别处理并发和串行工具调用，包含 JSON 参数解析、`tool_search` 解包、toolset scope 校验、plugin pre-tool hook、guardrail、checkpoint 前置判断和结果消息追加。真正调用工具的更底层函数在 `agent.agent_runtime_helpers.invoke_tool`，再接到 `model_tools.handle_function_call` 和 `tools/registry.py` 体系。

`agent/auxiliary_client.py` 是辅助 LLM 客户端中心，文件体量最大。它处理 text/vision 辅助任务的 provider 选择、OpenRouter/Nous/custom/Codex/Anthropic 等客户端包装、缓存、fallback、异步调用、任务级配置和 `call_llm`/`async_call_llm`。它不是主 agent 的唯一请求路径，但大量压缩、标题、视觉、插件 LLM 等“旁路模型调用”会经过这里。

## 主流程位置

主流程可以按调用链理解：外层创建 `AIAgent`，`run_agent.py` 的 `AIAgent.__init__` 调 `agent.agent_init.init_agent` 完成状态搭建；用户发起请求时，`AIAgent.run_conversation` 调 `agent.conversation_loop.run_conversation`；对话循环在每次模型调用前通过 `agent.chat_completion_helpers.build_api_kwargs` 和 `agent/transports` 相关适配构造请求；模型返回后通过 `build_assistant_message` 或 transport normalize 逻辑转成内部 assistant message；如果包含 tool calls，则交给 `agent.tool_executor` 执行；工具结果作为 `tool` role message 追加回 messages，再进入下一轮模型调用；直到没有工具调用、达到迭代上限、被中断或触发 fallback/错误处理。

围绕主流程还有几条重要支线。上下文压缩由 `context_compressor.py`、`conversation_compression.py`、`context_engine.py`、`context_references.py` 参与；系统提示词由 `prompt_builder.py`、`system_prompt.py`、`subdirectory_hints.py`、`skill_preprocessing.py` 等参与；记忆由 `memory_manager.py`、`memory_provider.py` 参与；失败分类和恢复由 `error_classifier.py`、`retry_utils.py`、`rate_limit_tracker.py`、`credential_pool.py`、`agent_runtime_helpers.py` 参与；多媒体和生成类 provider 通过 `image_gen_provider.py`、`image_gen_registry.py`、`tts_provider.py`、`transcription_provider.py`、`video_gen_provider.py`、`web_search_provider.py` 等抽象与 registry 接入。

## 推荐阅读顺序

第一步读 `run_agent.py` 中 `AIAgent` 的 forwarder 区域，重点看 `__init__`、`run_conversation`、`chat`、`_execute_tool_calls`、`_interruptible_api_call` 如何指向 `agent` 模块。这样能先建立“外壳和内部模块”的关系。

第二步读 `agent/agent_init.py`，只看 `init_agent` 的参数和主要状态赋值，不需要陷入每个 provider 分支。目标是知道一个 agent 实例启动时有哪些核心属性：model、provider、api_mode、toolsets、callbacks、session、memory、guardrails、budget、credential、compression。

第三步读 `agent/conversation_loop.py` 的 `run_conversation`。建议先按大块注释和阶段跳读：turn 初始化、history/todo/memory hydration、API 调用、tool call 处理、错误/fallback、收尾持久化。这里是最值得反复看的文件。

第四步读 `agent/chat_completion_helpers.py` 和 `agent/transports/base.py`、`agent/transports/types.py`。前者解释请求怎么构造、响应怎么变成 assistant message；后者解释为什么不同 provider 最终能进入同一套对话循环。

第五步读 `agent/tool_executor.py`、`agent/tool_dispatch_helpers.py`、`agent/tool_guardrails.py`、`agent/agent_runtime_helpers.py` 中与 `invoke_tool` 相关的部分，再连接到仓库根部的 `model_tools.py` 和 `tools/registry.py`。这条线解释“模型发出 tool call 后到底如何变成实际工具执行”。

第六步按兴趣补读专题：上下文压缩看 `context_compressor.py`、`conversation_compression.py`；辅助模型看 `auxiliary_client.py`；凭证恢复看 `credential_pool.py`、`credential_sources.py`；LSP 看 `agent/lsp`；Codex/Anthropic/Gemini 等 provider 看相应 adapter 和 `agent/transports` 实现。

## 常见误区

不要把 `agent` 误认为完整应用入口。它更像运行时内核，外部入口仍在 `run_agent.py`、`cli.py`、`gateway/`、`tui_gateway/` 等位置。单看 `agent` 会缺少 CLI 配置加载、平台消息分发、工具注册发现等上下文。

不要以为 `run_agent.py` 已经被完全掏空。当前大量方法仍保留在 `run_agent.py`，有些是兼容测试 monkeypatch 的 re-export 或 forwarder，有些仍承载实际编排逻辑。阅读时应关注 forwarder 注释，看到 “Forwarder — see `agent.xxx`” 再跳转。

不要把 `agent/transports` 和老式 adapter 混为一谈。`anthropic_adapter.py`、`bedrock_adapter.py`、`gemini_native_adapter.py`、`codex_responses_adapter.py` 等更偏客户端、认证或协议细节；`transports` 更偏统一消息/工具/响应转换抽象。两者可能同时参与一个 provider 的请求链路。

不要从文件大小判断唯一重要性。`auxiliary_client.py` 最大，但它主要服务辅助 LLM 路径；主对话链路的核心仍是 `agent_init.py`、`conversation_loop.py`、`chat_completion_helpers.py`、`tool_executor.py` 和 `transports`。

不要逐个叶子文件背诵。`agent` 是大目录，overview 阶段应先掌握路径角色和主流程，再按问题进入专题模块。对于具体行为，例如某个 provider fallback、某类工具是否并发、某种压缩何时触发，应回到对应函数和调用链验证。
