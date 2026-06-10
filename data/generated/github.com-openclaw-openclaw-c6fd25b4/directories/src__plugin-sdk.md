# 目录：src/plugin-sdk

## 它负责什么

`src/plugin-sdk` 是 OpenClaw 的插件公共契约层，职责是在核心系统和插件之间提供稳定、类型化、可打包的 API 边界。插件作者通常通过 `openclaw/plugin-sdk/*` 这样的 subpath 引入这里的能力，而不是直接依赖 `src/channels/**`、`src/plugins/**`、`src/agents/**` 等核心内部实现。

从 `src/plugin-sdk/AGENTS.md`、`docs/plugins/sdk-overview.md` 和 `docs/plugins/sdk-entrypoints.md` 看，这个目录的核心定位不是“实现所有插件逻辑”，而是把核心已有能力整理成窄入口：插件入口定义、channel 注册、provider 注册、配置 schema、runtime helper、setup 流程、测试契约、媒体/语音/记忆/审批/网关等能力面。这里的 API 一旦暴露，就会影响 bundled plugins 和第三方插件，因此它比普通内部模块更接近发布契约。

这个目录规模很大，但结构上主要是“扁平 subpath 文件 + 少量测试辅助目录”。大量 `*-runtime.ts` 文件表示运行期才需要的窄能力，避免把重依赖挂到宽 barrel 上，减少插件加载、channel 启动和循环依赖风险。

## 直接子目录地图

`src/plugin-sdk` 下面直接子目录很少：

`src/plugin-sdk/test-helpers`：测试辅助工具集合。这里放 provider、channel、plugin registration、HTTP mock、fixture、public surface loader 等测试专用能力，用于合同测试和插件边界验证。它不是插件生产代码的常规入口。

`src/plugin-sdk/test-helpers/agents`：位于测试辅助目录下的 agent 相关 fixture 或 helper。根据当前片段推断，它服务于 agent runtime、subagent hooks 或 harness 相关测试，依据是同级存在 `agent-runtime-test-contracts.ts`、`agent-harness-runtime.test.ts`、`test-helpers/subagent-hooks.ts` 等测试契约文件。

除这两个目录外，大部分 SDK 面都是 `src/plugin-sdk/*.ts` 的扁平文件；这也是本目录最重要的地图特征：路径名本身就是 package subpath 和能力边界的提示。

## 关键入口

`src/plugin-sdk/entrypoints.ts` 是 SDK 出口清单的核心代码。它读取 `scripts/lib/plugin-sdk-entrypoints.json`，计算 `pluginSdkEntrypoints`、`publicPluginSdkEntrypoints`、`privateLocalOnlyPluginSdkEntrypoints`，并生成 package export、dist artifact、specifier 等派生信息。想理解“哪些 subpath 真正是 SDK 表面”，先看这里和 `scripts/lib/plugin-sdk-entrypoints.json`。

`src/plugin-sdk/plugin-entry.ts` 是普通插件入口定义的核心。文档中 `definePluginEntry` 就来自这里，适合 provider、tool、hook、service、gateway method 等非 channel 插件。它还集中导出大量 `OpenClawPluginApi` 相关类型，让插件在 `register(api)` 中注册能力。

`src/plugin-sdk/core.ts` 是更宽的 umbrella surface，包含 channel、provider、配置、outbound、routing 等共享 helper 和类型。它方便但也更重，因此新代码通常更推荐使用具体 subpath，例如 channel 入口走 `channel-core`，普通插件入口走 `plugin-entry`。

`src/plugin-sdk/channel-core.ts` 是 channel 插件的关键入口，承载 `defineChannelPluginEntry`、`defineSetupPluginEntry` 这一类 channel 专用封装。它把 channel plugin 注册到 `api.registerChannel(...)`，并区分 discovery、cli-metadata、full 等注册模式。

`src/plugin-sdk/provider-entry.ts` 是 provider 插件的便利入口之一，尤其是 `defineSingleProviderPluginEntry`。它把单 provider 常见结构，如 auth、catalog、unified model catalog 投影、config schema 和 `definePluginEntry` 组合起来，减少 provider 插件重复样板。

`src/plugin-sdk/index.ts` 是共享 root surface，但文档明确建议优先从具体 subpath 引入。它更像兼容和汇总入口，不应被当成新插件的默认进口。

`src/plugin-sdk/api-baseline.ts` 是 API 基线生成/校验相关代码，产物指向 `docs/.generated/plugin-sdk-api-baseline.*`。它用于把公开 SDK 导出变成可审计的文档和状态文件，帮助控制公共 API 漂移。

## 主流程位置

插件注册主流程从插件自己的默认导出开始：普通插件调用 `definePluginEntry(...)`，channel 插件调用 `defineChannelPluginEntry(...)`，简单工具插件通常走 `tool-plugin.ts` 的 `defineToolPlugin(...)`。这些入口最终围绕 `OpenClawPluginApi` 展开，插件在 `register(api)` 中声明 provider、channel、tool、command、hook、service、gateway route、session workflow 等能力。

SDK 出口维护流程是另一条主线：`scripts/lib/plugin-sdk-entrypoints.json` 定义入口清单，`src/plugin-sdk/entrypoints.ts` 计算公共/私有/废弃入口，`package.json` 的 `./plugin-sdk/*` exports 与 dist 文件保持对齐，`src/plugins/contracts/plugin-sdk-package-contract-guardrails.test.ts`、`src/plugins/contracts/plugin-sdk-index.test.ts` 等测试负责守住 package contract。根据当前片段推断，新增公开 subpath 需要同步这些清单、exports、文档和 API baseline，依据是 `src/plugin-sdk/AGENTS.md` 的 “Expanding The Boundary” 规则。

运行期 helper 主流程分散在多个 `*-runtime.ts` 文件里。例如 `config-runtime.ts`、`setup-runtime.ts`、`gateway-runtime.ts`、`plugin-runtime.ts`、`provider-auth-runtime.ts`、`channel-ingress-runtime.ts`、`reply-runtime.ts`、`media-runtime.ts`、`ssrf-runtime.ts` 等。这些文件通常不是总入口，而是按能力给插件或 bundled plugin 暴露一个窄的运行时工具。

测试主流程集中在两类文件：一类是本目录内的 `*.test.ts`，验证具体 SDK helper；另一类是 `plugin-test-contracts.ts`、`provider-test-contracts.ts`、`channel-contract-testing.ts` 和 `test-helpers/**`，用于给插件实现套合同测试。

## 推荐阅读顺序

1. 先读 `src/plugin-sdk/AGENTS.md`，理解这里是公共 SDK 边界，不是随意重导出核心内部的便利层。
2. 再读 `docs/plugins/sdk-overview.md` 和 `docs/plugins/sdk-entrypoints.md`，建立插件作者视角：应该 import 哪些 subpath，`register(api)` 能注册什么。
3. 接着看 `scripts/lib/plugin-sdk-entrypoints.json` 和 `src/plugin-sdk/entrypoints.ts`，理解公开 subpath、私有本地 subpath、package exports 和 dist artifact 的生成关系。
4. 然后按插件类型选择入口：普通插件读 `src/plugin-sdk/plugin-entry.ts`，channel 插件读 `src/plugin-sdk/channel-core.ts`，provider 插件读 `src/plugin-sdk/provider-entry.ts`，工具插件读 `src/plugin-sdk/tool-plugin.ts`。
5. 最后按能力专题阅读窄文件：配置看 `config-*`，channel 流程看 `channel-*`，provider 流程看 `provider-*`，运行期工具看 `*-runtime.ts`，合同测试看 `plugin-test-contracts.ts`、`provider-test-contracts.ts`、`test-helpers/**`。

## 常见误区

误区一：把 `src/plugin-sdk` 当成核心内部工具箱。实际这里是公共契约层，不能随手把 `src/channels/**` 或 `src/plugins/**` 的便利函数重导出来。能留在插件本地的逻辑，应通过插件自己的 `api.ts`、`runtime-api.ts` 或更窄的 generic SDK seam 解决。

误区二：优先从 `openclaw/plugin-sdk` 或 `core` 宽入口导入。文档更推荐具体 subpath，例如 `openclaw/plugin-sdk/plugin-entry`、`openclaw/plugin-sdk/channel-core`。这样可以减少启动成本和循环依赖。

误区三：看到 `discord`、`telegram-account`、`lmstudio-runtime` 这类 branded subpath，就认为新插件也应该添加品牌专属 SDK 文件。根据目录规则，这些多是 bundled-plugin 维护、兼容或过渡入口；新增能力应优先抽象为通用行为，例如 provider auth、catalog、stream、tool schema、channel runtime helper。

误区四：忽略 `*-runtime.ts` 的边界含义。很多 runtime helper 是为了把重逻辑留到异步或完整运行期，不应被重新挂到热启动入口上。

误区五：只改源码文件而不同步出口清单。公开 SDK subpath 涉及 `scripts/lib/plugin-sdk-entrypoints.json`、`src/plugin-sdk/entrypoints.ts`、`package.json` exports、API baseline、docs 和合同测试；漏掉任何一处都可能导致构建产物、文档和实际 API 不一致。
