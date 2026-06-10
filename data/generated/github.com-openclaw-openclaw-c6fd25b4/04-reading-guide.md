# 源码阅读指南

本指南面向刚接触 OpenClaw 的中文读者，目标是把阅读顺序排清楚：哪些文件必须先看，哪些模块适合后读，哪些目录可以暂时跳过。依据来自当前仓库真实结构和入口调用链，不使用外部网页。

## 第一轮：建立主线

第一步读 `README.md`。重点不是安装命令，而是项目定位：本地运行的 personal AI assistant、Gateway 是控制面、多 channel、agent、tool、skills、voice、Canvas、companion apps、安全默认值。读完后只需记住一句：OpenClaw 的核心不是一个聊天 API wrapper，而是一个本地 Gateway 驱动的多入口 AI assistant runtime。

第二步读 `package.json` 和 `pnpm-workspace.yaml`。看 `bin.openclaw`、`exports`、`engines`、`scripts`、`dependencies`、workspace packages。这样你会知道源码由根包、`ui`、`packages/*`、`extensions/*` 组成，Node 版本要求是 22.19+，源码开发使用 pnpm，测试/构建/文档/插件 SDK 都有脚本入口。

第三步读 `openclaw.mjs` 和 `src/entry.ts`。只追启动包装逻辑：Node 版本检查、source checkout 判断、compile cache、argv/profile/container、help/version fast path、动态导入 CLI。不要在这里寻找所有命令实现。

第四步读 `src/cli/gateway-cli/run.ts` 和 `src/cli/gateway-cli/run-loop.ts`。它们解释 Gateway 启动前做什么：读取配置快照、解析端口/bind/auth/tailscale、阻止危险启动、处理 service marker、force free port、启动 server、持有 Gateway lock、处理重启和信号。

第五步读 `src/gateway/server.ts`，再读 `src/gateway/server.impl.ts` 的 `startGatewayServer`。这个文件很大，不建议一次读完。第一遍只标记阶段：startup config、auth/secrets、runtime config、plugin bootstrap、method registry、request context、WebSocket attach、HTTP listen、post-attach runtime、config reloader、maintenance、close。

## 第二轮：读边界和扩展点

读 `src/gateway/server-startup-plugins.ts` 和 `src/gateway/server-plugin-bootstrap.ts`。这两个文件能解释插件如何进入 Gateway：自动启用、plugin lookup table、startup plugin ids、deferred channel plugins、subagent/node runtime、gateway handlers、channel registry、configured binding registry。读完后再看 `src/plugins/plugin-lookup-table.ts`、`src/plugins/registry.ts`、`src/plugins/loader.ts`。

读 `src/gateway/methods/registry.ts`、`src/gateway/server-request-context.ts`、`src/gateway/server-ws-runtime.ts`。这三处是请求流的骨架：method name 如何归一化、scope 如何绑定、handler 如何查找、运行时上下文里有什么对象、WebSocket handler 如何接收 context。

读 `src/agents/agent-command.ts`。第一遍只看 imports 和高层函数，不要被细节淹没。它告诉你 agent run 依赖哪些概念：session key、agent id、workspace、model selection、auth profile、skills、ACP、attempt execution、delivery、sandbox/tool policy。然后按兴趣继续读 `src/agents/command/**`、`src/acp/**`、`src/sessions/**`。

读 `src/channels/message/receive.ts`、`src/channels/message/runtime.ts`、`src/channels/message/send.ts`、`src/channels/message/reply-pipeline.ts`、`src/channels/message-access/**`、`src/channels/plugins/registry.ts`。这些文件比具体平台插件更适合初学者，因为它们定义 channel 的通用生命周期和安全策略。

## 第三轮：选择专题下钻

如果你关注消息平台，选择一个插件读到底，例如 `extensions/telegram`、`extensions/slack` 或 `extensions/discord`。先看 `openclaw.plugin.json`，再看 `index.ts` 和 `src/**` runtime。对照 `src/channels/plugins/**`，理解插件提供哪些 channel capability、setup、message action、target parsing、auth 或 HTTP route。

如果你关注模型/provider，先读 `src/agents/model-selection.ts`、`src/agents/model-catalog.ts`、`src/provider-runtime/**`、`src/model-catalog/**`，再选 `extensions/openai`、`extensions/anthropic`、`extensions/google`、`extensions/ollama` 或 `extensions/lmstudio`。注意 auth profile 相关逻辑在 `src/agents/auth-profiles/**`，不要只看 provider 插件。

如果你关注 UI，先读 `ui/package.json`，再读 `ui/src/**` 的入口和 controllers，同时读 `src/gateway/control-ui.ts`、`src/gateway/control-ui-routing.ts`、`src/gateway/control-ui-csp.ts`。UI 的数据来源不是独立后端，而是 Gateway protocol、HTTP route 和 WebSocket。

如果你关注移动/桌面节点，先读 `apps/macos/README.md`、`apps/ios/README.md`、`apps/android/README.md`，再回到 `src/gateway/node-*.ts`、`src/pairing/**`、`extensions/device-pair/**`。这些模块需要先理解 Gateway、device pairing 和 node registry。

## 可暂时跳过的模块

初学第一轮可以跳过 `test/**`、大量 `*.test.ts`、`scripts/e2e/**`、release 脚本、Docker/Parallels/live 测试脚本、`docs/.generated/**`、`.agents/**` 技能文件、具体 provider/channel 的长尾插件、平台 app 的具体 UI 细节。它们重要，但不是理解主架构的第一入口。

也可以暂时跳过 `apps/**`，除非你的目标就是移动或桌面 app。Gateway、agent、channel、plugin 四条主线不依赖你先读完 Swift/Kotlin 工程。

## 继续下钻顺序

推荐下钻顺序是：入口启动 -> Gateway 服务 -> plugin bootstrap -> method registry/request context -> agent command -> channel message -> 具体插件 -> UI/app。每次遇到一个复杂功能，先回答四个问题：它从哪个入口被调用；它使用哪个 config/runtime snapshot；它是否依赖 plugin registry 或 channel registry；它最终调用 agent、provider、tool、HTTP route 还是外部平台。用这四个问题能避免在大仓库中迷路。

遇到“根据当前文件推断”的地方，应继续找同名 test 或 runtime 文件验证。例如 Gateway post-attach 具体启动哪些 sidecar，要读 `src/gateway/server-post-attach-runtime.ts`；agent attempt 如何调用模型，要读 `src/agents/command/attempt-execution.runtime.ts`；某个 channel 如何处理入站消息，要读对应插件的 runtime 与 `src/channels/message/**`。
