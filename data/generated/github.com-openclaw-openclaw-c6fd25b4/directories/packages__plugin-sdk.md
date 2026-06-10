# 目录：packages/plugin-sdk

## 它负责什么

`packages/plugin-sdk` 是 OpenClaw 插件 SDK 的包装层，用来把核心仓库里的插件 SDK 能力以包入口形式暴露给插件侧代码使用。它本身不是主要业务实现目录，更像一个“包级导出门面”：`package.json` 定义 `@openclaw/plugin-sdk` 的大量子路径导出，`src/*.ts` 文件再把实现从仓库核心位置 `src/plugin-sdk/*.js` 重新导出。

从当前片段看，真正的类型、运行时逻辑、协议对象和工具函数大多位于仓库根部的 `src/plugin-sdk`，而 `packages/plugin-sdk` 负责提供稳定的 import surface，例如插件可以写 `openclaw/plugin-sdk/plugin-entry`、`openclaw/plugin-sdk/provider-http`、`openclaw/plugin-sdk/provider-auth-runtime` 等，而不需要直接依赖核心内部路径。这个设计符合根规则里“插件通过 `openclaw/plugin-sdk/*`、manifest metadata、runtime helper、documented barrels 跨入 core”的边界要求。

因此，学习这个目录时不要把它当成完整 SDK 源码本体，而要把它看成 SDK 包出口清单、能力分组索引和插件与核心之间的公共边界。

## 直接子目录地图

`packages/plugin-sdk` 当前只有一个直接源码子目录：

`packages/plugin-sdk/src`：包导出文件所在目录。这里的文件多为短 re-export，例如 `packages/plugin-sdk/src/plugin-entry.ts` 导出 `src/plugin-sdk/plugin-entry.js`，`packages/plugin-sdk/src/provider-entry.ts` 导出 `src/plugin-sdk/provider-entry.js`。按当前片段推断，它不承载复杂实现，而是把核心 SDK 文件映射成包可导入路径。

目录根部还有两个关键配置文件：

`packages/plugin-sdk/package.json`：最重要的地图文件。它声明包名 `@openclaw/plugin-sdk`、`type: module`，并通过 `exports` 暴露大量子路径，如 `./plugin-entry`、`./plugin-runtime`、`./provider-entry`、`./provider-auth`、`./provider-http`、`./provider-model-types`、`./provider-web-search`、`./runtime-doctor`、`./security-runtime`、`./testing` 等。学习时优先看这里，因为它定义了插件作者和内部插件实际能 import 的 SDK 面。

`packages/plugin-sdk/tsconfig.json`：该包的 TypeScript 编译配置。overview 阶段只需要知道它约束这个包如何参与类型检查和构建即可，不必深入编译细节。

## 关键入口

第一类入口是插件注册入口：`packages/plugin-sdk/src/plugin-entry.ts`、`packages/plugin-sdk/src/plugin-runtime.ts`。从插件使用片段看，多个插件的 `index.ts` 会导入 `definePluginEntry`，例如 `extensions/perplexity/index.ts`、`extensions/tokenjuice/index.ts`、`extensions/vydra/index.ts`。这说明 `plugin-entry` 是插件向 OpenClaw 注册自身能力、声明入口对象的关键表面；`plugin-runtime` 则偏运行时对象、API、上下文能力。

第二类入口是 provider 相关入口：`packages/plugin-sdk/src/provider-entry.ts`、`provider-auth.ts`、`provider-auth-runtime.ts`、`provider-http.ts`、`provider-model-types.ts`、`provider-model-shared.ts`、`provider-stream-shared.ts`、`provider-tools.ts`、`provider-web-search.ts`、`provider-web-search-config-contract.ts`、`provider-onboard.ts`。这些文件对应模型、认证、HTTP 请求、流式响应、工具调用、web search、onboarding 等 provider 插件常见能力。比如 `extensions/vydra` 使用 `provider-auth-runtime`、`provider-http`、`video-generation`；`extensions/perplexity` 使用 `provider-web-search` 和 web search config contract。

第三类入口是运行时与安全辅助：`config-runtime.ts`、`gateway-method-runtime.ts`、`runtime-doctor.ts`、`runtime-env.ts`、`security-runtime.ts`、`secret-input.ts`、`text-runtime.ts`。这些更像插件运行时可复用的基础设施，覆盖配置读取、gateway 方法、doctor 修复契约、环境日志、敏感输入、文本处理等。

第四类入口是测试入口：`packages/plugin-sdk/src/testing.ts`，以及 `package.json` 中还列出若干测试相关子路径。插件测试会通过 SDK 的测试工具构造 plugin API、环境变量、契约测试等。根据当前片段推断，测试工具实际实现仍在 `src/plugin-sdk`，此目录只提供包导出路径。

## 主流程位置

插件接入主流程可以从 `plugin-entry` 开始理解：插件包里的 `index.ts` 调用 SDK 暴露的定义函数，声明插件身份、能力和注册内容；核心插件加载器读取 manifest 或入口后，通过 SDK 契约识别这些能力。`packages/plugin-sdk/src/plugin-entry.ts` 是这个流程在包层的入口，实际行为要继续看 `src/plugin-sdk/plugin-entry.ts`。

provider 主流程可以从 `provider-entry` 与具体能力文件看：provider 插件声明模型、认证、请求、流式输出、工具、web search、图片/视频/语音等能力；运行时再通过核心 provider 路由和插件加载机制调用这些能力。这里的主流程位置不是 `packages/plugin-sdk` 内部实现，而是由 `packages/plugin-sdk/package.json` 暴露的子路径连接到 `src/plugin-sdk/provider-*.ts`，再连接到 `extensions/*` 的 provider 实现。

配置与修复流程可以从 `config-runtime`、`provider-auth-runtime`、`runtime-doctor` 看：插件读取 OpenClaw 配置、解析 provider 凭据、检查或修复运行时状态。根规则强调“Runtime reads canonical config only”以及 config 变更需要 doctor 迁移，所以这些入口属于兼容性和升级风险较高的表面。

测试流程则从 `testing` 以及 `package.json` 中的测试导出开始。插件测试不应深挖其他插件或核心内部实现，而应通过 SDK 测试 facade 构造公共契约证明。

## 推荐阅读顺序

1. 先读 `packages/plugin-sdk/package.json` 的 `exports`。这是 SDK 对外地图，能快速知道当前包承诺了哪些 import 子路径，以及哪些能力是公开表面。

2. 再抽样读 `packages/plugin-sdk/src/plugin-entry.ts`、`packages/plugin-sdk/src/provider-entry.ts`、`packages/plugin-sdk/src/provider-http.ts`。你会发现这里主要是 re-export，从而确认本目录的定位是“包出口”，不是实现中心。

3. 接着转到实际实现目录 `src/plugin-sdk`，按能力线阅读：插件注册看 `plugin-entry`、`plugin-runtime`；provider 看 `provider-entry`、`provider-auth-runtime`、`provider-http`、`provider-model-types`；web search 看 `provider-web-search` 与 `provider-web-search-config-contract`；doctor 与配置看 `runtime-doctor`、`config-runtime`。

4. 最后回到使用方验证理解：读 `extensions/perplexity/index.ts`、`extensions/vydra/index.ts`、`extensions/slack/src/runtime-api.ts`、`extensions/telegram/runtime-api.ts` 这类插件入口和 runtime facade。它们展示插件如何通过 `openclaw/plugin-sdk/*` 访问公共 SDK。

## 常见误区

不要误以为 `packages/plugin-sdk/src` 里的文件越短就越不重要。它们短是因为职责是稳定导出路径；对插件作者来说，import path 本身就是公共 API 的一部分，改动可能影响大量插件。

不要从插件生产代码直接 import `src/plugin-sdk/*` 或核心 `src/**`。根规则明确要求插件通过 `openclaw/plugin-sdk/*` 等公开边界进入核心。`packages/plugin-sdk` 正是为了维护这个边界。

不要只看 `packages/plugin-sdk/src` 就判断 SDK 支持范围。`package.json` 的 `exports` 中列出的子路径比当前浅层文件列表更能代表包级 API 面；同时，根据当前片段推断，部分导出可能映射到根部 `src/plugin-sdk` 的文件，学习时需要结合两边看。

不要把 provider、channel、plugin runtime 混成一条线。`plugin-entry` 负责插件注册表面；`provider-*` 面向模型/provider 能力；channel 插件通常还会使用 channel contract、runtime API、message pipeline 等 SDK 子路径。overview 阶段应先按能力分组理解。

不要把测试 helper 当作生产依赖。`testing`、contract test、test env 这类入口服务于插件测试和契约验证；生产插件应优先依赖 `plugin-entry`、`provider-*`、`runtime-*`、`config-*` 等运行时入口。

不要在文档或用户可见描述里说 `extensions` 是产品概念。按根规则，用户可见表达应使用 “plugin/plugins”；`extensions/` 只是仓库内部路径。
