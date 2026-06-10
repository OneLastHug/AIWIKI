# 目录：src

## 它负责什么

`src` 是 OpenClaw 核心 TypeScript 源码目录，承担产品运行时、CLI、网关、通道抽象、插件加载、Agent 执行、配置、会话、模型目录、工具能力和若干媒体/网络能力的主体实现。根据 `package.json` 片段可以看出，包名是 `openclaw`，发布入口指向 `dist/index.js`，命令行入口是 `openclaw.mjs`，而 `src/index.ts` 是源码层面的核心导出入口。也就是说，`src` 不是某个单一服务目录，而是整个核心包从命令行、后台服务、插件 SDK 到运行时协议的集合。

从根规则可知，OpenClaw 的架构强调“core stays plugin-agnostic”：核心目录应保持插件无关，插件通过 `src/plugin-sdk/*`、manifest、runtime helpers 和公开 barrel 与核心交互。`extensions/` 是插件实现区域，`src` 主要提供通用框架、运行时、协议、加载器和 SDK 边界。

## 直接子目录地图

`src/cli`、`src/commands` 是命令行层。前者更像 CLI 程序结构和子命令装配区，包含 `program`、`daemon-cli`、`gateway-cli`、`node-cli`、`send-runtime` 等；后者放具体命令能力，如 `doctor`、`setup`、`models`、`channels`、`migrate`、`gateway-status`、`status-all`。学习 CLI 行为时通常先看 `src/cli` 怎么接线，再看 `src/commands` 的具体实现。

`src/gateway` 是网关服务与协议中心，含 `server`、`methods`、`server-methods`、`protocol`、`test`，并且有 scoped `AGENTS.md`。它是客户端、插件、通道、运行时之间交换消息和控制面的关键区域。`src/acp` 也包含 `control-plane`、`runtime` 和 `server.ts`，根据当前片段推断，它与 Agent Client Protocol 或控制平面运行有关，依据是其目录名和 `control-plane/runtime/server.ts` 结构。

`src/agents` 是 Agent 运行域，包含 `harness`、`tools`、`skills`、`schema`、`sandbox`、`auth-profiles`、`runtime-plan`、`cli-runner`、`command`、`pi-*` 辅助/runner/hooks 等。它看起来负责模型代理执行、工具调用、技能管理、沙箱、认证配置和运行计划。

`src/channels` 是通道抽象层，含 `transport`、`message`、`turn`、`status`、`plugins`、`allowlists`、`inbound-event`、`message-access`。根规则说明 channels 是 core 内部实现，插件作者通过 SDK seam 访问，因此这里应理解为 Slack、Telegram 等具体插件之上的通用消息通道合同与调度层，而不是具体插件实现。

`src/plugins`、`src/plugin-sdk` 是插件边界的两侧。`src/plugin-sdk/index.ts` 及多个导出面向插件作者；`src/plugins` 则更偏核心内的插件发现、加载、运行时合同、兼容层和测试辅助。`src/plugins/cli.ts` 暗示插件相关 CLI 也在这里接入。两者都有 scoped `AGENTS.md`，说明这是架构敏感区域。

`src/config`、`src/secrets`、`src/security`、`src/sessions`、`src/plugin-state` 是状态与配置基础设施。`src/config/sessions` 说明会话配置可能有独立子域；`src/secrets` 管凭据读取/存储边界；`src/security` 放安全策略或校验；`src/plugin-state` 处理插件状态持久化或运行期状态。

`src/provider-runtime`、`src/model-catalog`、`src/routing` 组成模型和 provider 路由相关能力。`src/model-catalog/index.ts` 是可见入口，`provider-index` 子目录说明模型目录会按 provider 建索引；`routing` 负责选择模型、provider 或能力路线；`provider-runtime` 则更靠近 provider 执行期。

`src/context-engine`、`src/memory`、`src/memory-host-sdk`、`src/trajectory`、`src/tasks` 组成上下文、记忆、任务与执行轨迹相关能力。`src/memory-host-sdk/host` 表明记忆能力可能也有宿主 SDK 边界。

`src/tools`、`src/mcp`、`src/web-fetch`、`src/web-search`、`src/link-understanding` 是工具和外部信息能力。`src/tools/index.ts` 是工具导出入口；`src/mcp` 对接 Model Context Protocol；`web-fetch`、`web-search`、`link-understanding` 分别覆盖网页获取、搜索和链接理解。

`src/media`、`src/image-generation`、`src/media-generation`、`src/media-understanding`、`src/music-generation`、`src/video-generation`、`src/realtime-transcription`、`src/tts` 是多媒体能力族。根据当前片段推断，它们是按能力拆分的通用服务或插件调用适配层，依据是目录名与 OpenClaw 多通道 AI gateway 的包描述。

`src/tui`、`src/interactive`、`src/wizard`、`src/chat`、`src/talk` 是交互界面与对话体验层。`src/tui/components`、`src/tui/theme` 说明终端 UI 有组件和主题；`src/wizard/i18n` 与 `src/i18n` 表示安装/引导流程可能支持多语言。

`src/daemon`、`src/cron`、`src/process`、`src/node-host`、`src/bootstrap` 是后台运行和进程生命周期相关区域。`src/process/supervisor` 表明有进程监督；`src/cron/service`、`src/cron/isolated-agent` 指向定时任务服务和隔离 Agent 任务。

`src/infra`、`src/shared`、`src/utils`、`src/types`、`src/logging`、`src/status` 是横向基础库。`src/infra/net`、`src/infra/tls`、`src/infra/outbound` 处理网络/TLS/出站请求；`src/shared/net`、`src/shared/text` 是更泛用的共享工具；`src/logging/test-helpers` 说明日志也有测试辅助。

## 关键入口

源码级最重要的入口是 `src/index.ts`，它对应包主入口的源码侧聚合位置。插件作者相关入口主要是 `src/plugin-sdk/index.ts`，并且 `package.json` 片段显示发布包还导出 `./plugin-sdk`、`./plugin-sdk/core`、`./plugin-sdk/runtime`、`./plugin-sdk/routing`、`./plugin-sdk/health`、`./plugin-sdk/runtime-doctor` 等多个 SDK 子路径。

服务入口方面，`src/gateway/server.ts` 是网关服务器入口，`src/acp/server.ts` 是 ACP 服务入口，`src/plugins/cli.ts` 是插件命令入口。模型目录入口是 `src/model-catalog/index.ts`，工具导出入口是 `src/tools/index.ts`。如果只想建立核心地图，这些文件比深入叶子实现更值得先读。

## 主流程位置

命令行主流程大致分布在 `src/cli` 到 `src/commands`：`src/cli/program` 负责命令装配，具体行为落到 `src/commands/*`，再调用配置、网关、插件或 agent 运行时模块。

消息/通道主流程大致位于 `src/channels`、`src/gateway`、`src/agents` 之间：通道层接收或规范化外部消息，网关层承接协议与服务方法，Agent 层调用模型、工具、技能和沙箱执行，再通过通道或网关返回状态与结果。根据当前片段推断，`src/channels/inbound-event`、`src/channels/turn`、`src/channels/transport` 是理解消息进入、回合处理和发送传输的关键位置。

插件主流程在 `src/plugins` 与 `src/plugin-sdk` 之间：核心侧通过 `src/plugins/runtime`、`src/plugins/contracts`、`src/plugins/compat` 等加载和约束插件；插件作者通过 `src/plugin-sdk` 的公开导出接入能力。根规则要求核心不要依赖插件内部实现，因此阅读时要特别分清“核心加载插件”和“插件实现业务”两个方向。

配置与修复主流程在 `src/config`、`src/commands/doctor`、`src/secrets`、`src/security`。根规则强调配置变更、迁移、doctor 修复是兼容性敏感面，因此这些路径常常决定升级行为，而不只是普通工具代码。

## 推荐阅读顺序

1. 先读 `src/index.ts` 和 `package.json` 的 `exports`，建立发布入口与源码入口的对应关系。
2. 再读 `src/cli`、`src/commands`，理解用户从 `openclaw` 命令进入系统后会走到哪里。
3. 接着读 `src/gateway/server.ts`、`src/gateway/protocol`、`src/gateway/server-methods`，掌握核心服务边界和协议形状。
4. 然后读 `src/channels` 的 `message`、`turn`、`transport`、`plugins`，理解外部通道如何被抽象成内部消息流。
5. 再读 `src/agents` 的 `harness`、`tools`、`skills`、`sandbox`、`auth-profiles`，理解 Agent 执行、工具和认证配置。
6. 最后读 `src/plugins` 与 `src/plugin-sdk`，把核心插件加载逻辑和插件作者 API 分开看；需要查模型/provider 时再补 `src/model-catalog`、`src/provider-runtime`、`src/routing`。

## 常见误区

不要把 `src/channels` 当作具体聊天平台插件目录。根规则说明具体插件在 `extensions/`，`src/channels` 更像核心通道抽象和消息流合同。

不要从 `src/plugins` 直接推断某个插件的业务实现。核心插件加载器可以知道 manifest、registry、runtime contract，但不应该依赖 `extensions/*/src/**` 的深层实现。

不要把 `src/plugin-sdk` 和 `src/plugins` 混成一个层。前者是对外 SDK surface，后者是核心内部插件系统；修改 SDK 通常意味着公开 API 兼容性，风险比普通内部改动更高。

不要只看 CLI 命令实现就判断运行时行为。许多命令只是入口，真实行为可能下沉到 `src/gateway`、`src/agents`、`src/config`、`src/plugins` 或 `src/provider-runtime`。

不要忽略 scoped `AGENTS.md`。当前片段显示 `src/agents/AGENTS.md`、`src/channels/AGENTS.md`、`src/gateway/AGENTS.md`、`src/plugin-sdk/AGENTS.md`、`src/plugins/AGENTS.md`、`src/tui/AGENTS.md` 存在；进入这些子树做修改或深读时，应先读取对应规则。
