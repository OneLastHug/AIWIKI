# 架构分层与模块边界

OpenClaw 的架构可以从 workspace 和 `src/` 内部分层两个角度理解。`pnpm-workspace.yaml` 说明仓库由根包、`ui`、`packages/*`、`extensions/*` 组成；根 `package.json` 的 `files`、`exports`、`scripts` 又说明根包发布 CLI、dist、docs、plugin SDK 子路径、脚本和部分插件资源。源码不是按单一 MVC 分层组织，而是围绕 Gateway 控制面、agent runtime、channel framework、plugin system、SDK、UI/app 这几类运行面组织。

## 顶层目录分层

`src/` 是核心 TypeScript 代码，包含 CLI、Gateway、agent、channel、plugin loader、config、sessions、tools、MCP/ACP、memory、media、web search、security、daemon 等模块。它是阅读架构的 P0 目录。

`extensions/` 是插件目录。每个插件通常包含 `openclaw.plugin.json`、`package.json`、`index.ts`、provider/channel/tool/runtime 文件和测试。插件包括 channel 类、provider 类、工具类、媒体类、诊断类、memory 类等。根据根规则和源码结构，插件应通过 SDK/public barrels 与 core 交互，不应把 core 内部实现当成普通依赖。

`packages/` 是共享 workspace 包。`packages/plugin-sdk` 暴露插件作者使用的 SDK 类型和运行时 helper；`packages/plugin-package-contract` 处理插件包契约；`packages/memory-host-sdk` 等包提供可复用能力。它们比 `src/plugin-sdk/**` 更像可独立消费的包面。

`ui/` 是 Control UI 前端。它有独立 `package.json`，使用 Vite/Lit/Vitest，构建后由 Gateway 服务或集成。阅读 UI 时要同时看 `src/gateway/control-ui*.ts`，因为路由、CSP、asset root、HTTP 入口在 Gateway 侧。

`apps/` 包含 macOS、iOS、Android 和共享 app kit。它们不是核心 Gateway 启动所必需的源码，但体现 companion app、node、voice、canvas、device pairing 等能力。

`docs/` 是用户文档源。`docs/docs.json` 是文档导航配置，`docs/cli/**`、`docs/channels/**`、`docs/concepts/**` 对理解产品概念有帮助，但源码结论仍需回到代码验证。

`scripts/` 是构建、测试、生成、发布、质量检查和开发工具脚本集合。`package.json` 大量脚本都指向这里，说明工程自动化是架构的一部分。

## Core 内部主要层

入口层由 `openclaw.mjs`、`src/entry.ts`、`src/cli/**` 构成。`openclaw.mjs` 做 Node 版本检查、source checkout 判断、compile cache respawn 和 packaged cache；`src/entry.ts` 做 argv/profile/container 解析、help/version fast path、环境规范化、compile cache 和 CLI 动态导入；`src/cli/run-main.ts` 和具体 `src/cli/*-cli.ts` 负责命令注册与执行。

Gateway 层由 `src/gateway/**` 构成。`src/gateway/server.ts` 只是懒加载入口，`src/gateway/server.impl.ts` 是主要实现。它读取 startup config，准备 auth/secrets，构造 runtime config，初始化 plugin bootstrap，创建 Gateway method registry，创建 WebSocket/HTTP runtime，启动 post-attach services，设置 config reloader，并在关闭时运行 plugin stop hook 和 close prelude。`src/gateway/protocol/**` 是协议 schema 与类型；`src/gateway/methods/**` 是 method registry；`src/gateway/server-methods/**` 是具体请求处理面。

Agent 层由 `src/agents/**` 和 `src/acp/**` 构成。`src/agents/agent-command.ts` 是核心聚合点，依赖 model selection、auth profile、skills、session store、ACP manager、attempt execution、delivery runtime、sandbox/tool policy 等。`src/acp/**` 处理 Agent Client Protocol 相关控制面、runtime registry、session 映射、translator、permission relay 等。

Channel 层由 `src/channels/**` 构成。它定义通用消息能力、ack policy、receive/send、reply pipeline、allowlist、message access、conversation/session meta、plugin channel registry、setup helper、状态和 binding。它不应承载某个平台的全部业务细节；平台细节应更多在 `extensions/<channel>`。

Plugin 层由 `src/plugins/**`、`src/plugin-sdk/**`、`packages/plugin-sdk/**` 和 `extensions/**` 联合组成。`src/plugins/**` 是 core 内部加载与运行管理；`src/plugin-sdk/**` 是 core 中暴露给插件的 facade；`packages/plugin-sdk/**` 是 workspace SDK 包；`extensions/**` 是实际插件。`src/gateway/server-startup-plugins.ts` 和 `src/gateway/server-plugin-bootstrap.ts` 是插件进入 Gateway runtime 的关键桥。

配置层由 `src/config/**` 构成。`src/config/config.ts` 统一 re-export IO、mutation、paths、runtime snapshot、validation、recovery policy 等能力。Gateway 启动依赖 `readConfigFileSnapshotWithPluginMetadata`、`setRuntimeConfigSnapshot`、`getRuntimeConfig` 等函数。配置不是静态 JSON 读取后丢弃，而是参与 runtime snapshot、last-known-good、hot reload、plugin metadata 和 secrets activation。

## 关键依赖方向

从源码和根规则看，推荐的依赖方向是：CLI 调用 Gateway/agent/config 的公开入口；Gateway 组合 config、plugins、channels、agents、protocol、server-methods；channels 使用通用 contract 和 plugin registry；plugins 通过 SDK/facade 接入 core；extensions 通过 `openclaw.plugin.json`、`index.ts` 和 SDK 暴露能力；UI/app 通过 Gateway protocol、HTTP、WebSocket、node/device 接口与 core 通信。

不推荐的方向是插件直接依赖 core 内部实现、core 写死具体插件策略、测试越过 SDK 去使用插件内部 `src/**`。根 `AGENTS.md` 明确规定 core 保持 plugin-agnostic，插件生产代码不能依赖 core `src/**` 或其他插件内部源码。这个边界也能从 lint 脚本看出：`lint:extensions:no-plugin-sdk-internal`、`lint:extensions:no-relative-outside-package`、`lint:plugins:no-extension-imports`、`lint:plugins:no-extension-src-imports` 等脚本都在守边界。

## 扩展点

第一类扩展点是 provider。Provider 插件可以提供模型、认证、catalog、runtime hooks，例如 `extensions/openai`、`extensions/anthropic`、`extensions/google`、`extensions/ollama`、`extensions/lmstudio`。核心会通过 model selection、provider runtime、auth profiles 和 plugin registry 选择能力。

第二类扩展点是 channel。Channel 插件提供消息收发、平台 auth/setup、target parsing、thread binding、message actions、DM/group policy 等能力。`src/channels/plugins/**` 是 channel plugin 的关键 contract 和 registry，真实插件在 `extensions/telegram`、`extensions/slack`、`extensions/discord` 等目录。

第三类扩展点是 Gateway method、HTTP route、node capability 和 tool。`src/gateway/methods/registry.ts` 支持 core 和 plugin descriptors；`src/plugins/registry-types.ts` 相关类型承载 plugin registry 能力；`src/gateway/server.impl.ts` 会把 plugin gateway handlers 合入 method registry，并通过 plugin HTTP route registry 提供 hosted plugin surface。

第四类扩展点是 skills、memory、media、web search 和 automation。仓库中有 `src/agents/skills/**`、`src/memory/**`、`src/media-generation/**`、`src/web-search/**`、`src/cron/**`、`extensions/skill-workshop`、`extensions/memory-*`、`extensions/duckduckgo`、`extensions/perplexity`、`extensions/fal` 等目录，说明这些能力被设计成可替换或可插件化的运行面。

## 架构阅读注意事项

不要用目录名直接推断职责边界，必须看入口和调用链。例如 `src/commands/agent.ts` 只是 re-export，真正实现是 `src/agents/agent-command.ts`；`src/gateway/server.ts` 只是懒加载，真正实现是 `src/gateway/server.impl.ts`；`README.md` 提到很多 channel，但具体 channel 能力分散在 `extensions/**`。另外，启动链路大量使用 dynamic import，静态搜索某个 symbol 可能只看到懒加载包装，需要继续打开 runtime 文件。

根据当前文件推断，OpenClaw 的架构目标是把 Gateway 当作长期运行、可热重载、可扩展、可由多端连接的控制面，把具体 provider/channel/tool 能力交给插件，把用户会话和 agent run 交给 agent 层，把公开扩展边界压到 plugin SDK 和 manifest contract。这个推断的依据是 `server.impl.ts` 的启动流程、`server-startup-plugins.ts` 的 bootstrap 逻辑、`package.json` 的 SDK exports、`extensions/*/openclaw.plugin.json` 的存在，以及根规则对 core/plugin 边界的约束。
