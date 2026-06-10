# 项目整体介绍

OpenClaw 是一个以本地 Gateway 为控制面的个人 AI assistant 项目。这个判断来自 `README.md` 的开头说明、`package.json` 的 `description`、`bin.openclaw` 和大量 `src/gateway/**`、`src/channels/**`、`src/agents/**`、`extensions/**` 文件。它不是单一聊天机器人，也不是只有一个模型调用封装层；当前仓库同时包含 CLI、Gateway 服务、agent runtime、多 channel 消息接入、插件系统、Control UI、桌面和移动 companion app 相关代码。外部网址在本文中统一省略为 `[URL已移除]`。

## 它解决的问题

项目要解决的核心问题是：把一个个人 AI assistant 运行在用户自己的设备和工作区里，让它能通过不同消息渠道、CLI、Web/Control UI、节点设备和插件能力工作。`README.md` 明确把 Gateway 描述为控制面，并列出多种 channel、agent、tool、skill、voice、Canvas、cron、webhook、node 等能力；`package.json` 将包描述为 “Multi-channel AI gateway with extensible messaging integrations”。因此，源码阅读时应把 OpenClaw 看成一个“本地优先的 AI 助手运行平台”，而不是只看成一个 model provider SDK。

它的能力主要分四层。第一层是入口和运维层：`openclaw.mjs`、`src/entry.ts`、`src/cli/**`、`src/daemon/**` 负责命令行、daemon/service、启动参数、版本和配置检查。第二层是 Gateway 层：`src/gateway/**` 提供 HTTP/WebSocket 服务、认证、协议、方法注册、Control UI 路由、node 连接、健康状态、配置热重载和插件运行环境。第三层是 agent 和会话层：`src/agents/**`、`src/acp/**`、`src/sessions/**` 负责 agent 命令、模型选择、auth profile、sandbox、工具、ACP runtime、session key、transcript 和尝试执行。第四层是扩展层：`src/plugins/**`、`src/plugin-sdk/**`、`packages/plugin-sdk/**`、`extensions/**` 支撑 provider、channel、tool、web search、media generation、memory、diagnostics 等扩展能力。

## 核心能力

从仓库结构看，OpenClaw 支持多 channel 消息接入。`README.md` 列出 WhatsApp、Telegram、Slack、Discord 等 channel；源码里 `src/channels/**` 提供通用 channel policy、message lifecycle、allowlist、session 路由、plugin channel registry；真实 channel 实现大量分布在 `extensions/**`，例如 `extensions/telegram`、`extensions/slack`、`extensions/discord` 等。由此可以看出，core 更像 channel 框架和策略层，具体平台集成更多放在插件目录。

项目也支持多 provider/model 路由。证据包括 `src/agents/model-selection.ts`、`src/agents/model-catalog.ts`、`src/model-catalog/**`、`src/provider-runtime/**`、`extensions/openai`、`extensions/anthropic`、`extensions/google`、`extensions/ollama`、`extensions/lmstudio`、`extensions/amazon-bedrock` 等 provider 插件。`package.json` 里也能看到 `openai`、`@google/genai`、`@agentclientprotocol/sdk`、`@modelcontextprotocol/sdk` 等依赖。读者需要注意：模型能力不只由一个文件决定，它由配置、auth profile、插件 manifest、provider catalog、agent runtime 和 fallback 共同决定。

项目有完整的插件机制。根规则和源码都强调 core 与插件边界：插件通过 `openclaw.plugin.json`、SDK facade、runtime helpers 和 registry 接入；`src/gateway/server-startup-plugins.ts` 负责启动期插件准备，`src/gateway/server-plugin-bootstrap.ts` 负责插件 runtime 环境、gateway binding 和 channel registry 绑定，`src/plugins/plugin-lookup-table.ts`、`src/plugins/registry.ts`、`src/plugins/loader.ts` 是继续下钻的种子。`package.json` 的 `exports` 暴露大量 `./plugin-sdk/*` 子路径，说明插件 SDK 是公开 API 面之一。

项目还包含 Control UI 和 companion apps。`ui/package.json` 显示 Control UI 是 private package，使用 Vite、Lit、Vitest、Playwright 相关依赖；`src/gateway/control-ui.ts`、`src/gateway/control-ui-routing.ts` 等文件说明 Gateway 负责服务或代理 UI 资源。`apps/macos/Package.swift`、`apps/ios/project.yml`、`apps/android/build.gradle.kts` 说明仓库里也包含 macOS、iOS、Android 应用或节点代码。初学者读 core 时可以先跳过 apps，除非目标是移动/桌面集成。

## 主要模块

`src/entry.ts` 是源码运行入口，它处理 argv、profile/container 参数、compile cache、help fast path，然后动态导入 `src/cli/run-main.ts`。这解释了为什么很多命令不是在入口顶层静态加载：仓库里大量使用 `createLazyImportLoader` 和 dynamic import 控制启动成本。

`src/cli/**` 是命令层。它包含 `gateway-cli`、`daemon-cli`、`nodes-cli`、`config-cli`、`models-cli`、`mcp-cli`、`cron-cli` 等子模块。`src/cli/gateway-cli/run.ts` 读取 Gateway 启动参数、配置快照、端口、bind/auth/tailscale 选项，并动态导入 `src/gateway/server.js`。`src/cli/gateway-cli/run-loop.ts` 负责 Gateway lock、signal、restart、shutdown 和健康探测。

`src/gateway/**` 是服务层。`src/gateway/server.ts` 是懒加载包装，真正实现集中在 `src/gateway/server.impl.ts`。启动时会读取配置快照、准备 auth/secrets、设置 runtime config、准备插件 bootstrap、创建 Gateway method registry、创建 request context、绑定 WebSocket handler、启动 HTTP listener、启动 post-attach runtime、配置热重载和维护任务。这个判断直接来自 `startGatewayServer` 的函数体。

`src/agents/**` 是 agent 层。`src/commands/agent.ts` 只是 re-export，实际在 `src/agents/agent-command.ts`。该文件引入配置、session、model selection、skills、auth profile、ACP manager、delivery runtime、attempt execution runtime 等多个模块，说明 agent run 是一个汇聚点。它会根据 session key、agent id、workspace、模型、skills、auth profile 和执行环境来组织一次运行。

`src/channels/**` 是 channel 框架层。它定义 channel message contract、ack policy、allowlist、DM access、conversation binding、message send/receive/reply pipeline、plugin channel registry 和 setup helper。具体平台 channel 大多在 `extensions/**`。

`src/plugins/**` 与 `src/plugin-sdk/**` 是扩展边界。前者偏 core 内部加载、registry、manifest、runtime；后者偏对插件暴露的 public facade。`packages/plugin-sdk/**` 进一步表明 SDK 也以 workspace package 的方式存在。

## 初学者切入点

最好的切入点不是直接打开最大的 `src/gateway/server.impl.ts`，而是先看四个种子文件：`README.md`、`package.json`、`openclaw.mjs`、`src/entry.ts`。它们回答“项目是什么、怎么运行、二进制从哪里来、源码入口怎么转入 CLI”。然后读 `src/cli/gateway-cli/run.ts` 和 `src/cli/gateway-cli/run-loop.ts`，理解 Gateway 为什么要先读配置、检查端口和 auth，再进入可重启的运行循环。接着读 `src/gateway/server.ts` 和 `src/gateway/server.impl.ts` 的 `startGatewayServer`，只追启动阶段的关键变量，不要一开始追完所有 HTTP method。

第二阶段建议看 `src/gateway/server-startup-plugins.ts`、`src/gateway/server-plugin-bootstrap.ts`、`src/gateway/methods/registry.ts`。这三处能解释插件如何参与 Gateway 方法、channel、node capability、subagent runtime。之后根据兴趣分流：想看消息平台读 `src/channels/**` 和一个具体 `extensions/<channel>`；想看模型调用读 `src/agents/model-selection.ts`、`src/provider-runtime/**` 和 provider 插件；想看 UI 读 `ui/package.json`、`ui/src/**` 和 `src/gateway/control-ui*.ts`；想看移动节点读 `apps/ios/**`、`apps/android/**`、`src/gateway/node-*.ts`。

本文中的“根据当前文件推断”只用于源码没有集中说明但调用链显示的行为。例如 Gateway 启动后的 post-attach 服务具体包括哪些后台任务，需要继续读 `src/gateway/server-post-attach-runtime.ts`、`src/gateway/server-runtime-services.ts` 等文件才能完全确认；本总览只说明它们从 `server.impl.ts` 被调用并接管 channels、plugin services、scheduled services 和维护任务。
