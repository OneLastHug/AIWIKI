# 目录：packages

## 它负责什么

`packages` 是 OpenClaw 仓库里的共享包与发布包集中区，主要承载“被核心、插件、外部调用方复用的稳定接口”。它不像 `src/` 那样直接放核心运行时主逻辑，也不像 `extensions/` 那样放具体插件实现，而是把若干跨边界能力拆成独立 package：客户端 SDK、插件 SDK、插件包元数据契约、memory host 相关运行时能力。

从当前片段看，这里有两类角色。第一类是对外或准对外的 API 边界，例如 `packages/sdk` 暴露 `OpenClaw` 客户端、命名空间对象、事件与传输类型；`packages/plugin-sdk` 暴露插件作者或插件运行时会使用的入口、provider 类型、runtime helpers。第二类是内部共享契约，例如 `packages/plugin-package-contract` 用来解析和校验外部 code plugin 的 `package.json` 兼容性字段；`packages/memory-host-sdk` 则组织 memory host 的 runtime、engine、query、storage、secret、status 等能力。

根规则强调 core 保持 plugin-agnostic，插件跨入 core 应通过 `openclaw/plugin-sdk/*`、manifest metadata、runtime helpers 和 documented barrels。因此学习 `packages` 时，应把它理解成“边界层”和“契约层”，不是具体产品功能的唯一实现位置。

## 直接子目录地图

`packages/sdk`：OpenClaw 客户端 SDK。入口聚合在 `packages/sdk/src/index.ts`，导出 `OpenClaw`、`Agent`、`Session`、`Run`、各类 namespace、事件归一化、transport，以及大量请求/结果类型。它面向“程序如何连接 OpenClaw gateway、创建 session/run、调用 tools、订阅事件”等场景。

`packages/plugin-sdk`：插件 SDK 与插件运行时共享接口。`packages/plugin-sdk/package.json` 中有大量子路径 exports，例如 `./plugin-entry`、`./plugin-runtime`、`./provider-entry`、`./provider-auth`、`./provider-http`、`./provider-model-types`、`./provider-tools`、`./runtime-doctor` 等。当前抽样看到 `packages/plugin-sdk/src/plugin-entry.ts`、`packages/plugin-sdk/src/provider-entry.ts`、`packages/plugin-sdk/src/plugin-runtime.ts` 实际上从根部 `src/plugin-sdk/*` 再导出，说明这里更像 package 化的公开门面，真正实现或原始定义可能仍在 `src/plugin-sdk`。这是根据当前片段推断，依据是这几个入口文件只有 `export * from "../../../src/plugin-sdk/..."`。

`packages/plugin-package-contract`：外部 code plugin 包描述契约。`packages/plugin-package-contract/src/index.ts` 定义 `ExternalPluginCompatibility`、`ExternalCodePluginValidationResult`，并提供 `normalizeExternalPluginCompatibility`、`listMissingExternalCodePluginFieldPaths`、`validateExternalCodePluginPackageJson`。它关心 `openclaw.compat.pluginApi`、`openclaw.build.openclawVersion`、`openclaw.build.pluginSdkVersion`、`openclaw.compat.minGatewayVersion` 等字段。

`packages/memory-host-sdk`：memory host 相关 SDK/运行时包。`packages/memory-host-sdk/package.json` 暴露 `./runtime`、`./runtime-core`、`./runtime-cli`、`./runtime-files`、`./engine`、`./engine-foundation`、`./engine-storage`、`./engine-embeddings`、`./engine-qmd`、`./multimodal`、`./query`、`./secret`、`./status`。从命名看，它把 memory 的执行入口、底层 engine、存储、embedding、QMD 查询、多模态处理和状态检查拆成模块。

## 关键入口

`packages/sdk/src/index.ts` 是学习客户端 SDK 的第一入口。它不实现全部细节，而是把 `client.ts`、`event-hub.ts`、`normalize.ts`、`transport.ts`、`types.ts` 的能力集中导出。想理解外部代码怎么使用 OpenClaw，应先看这里，再进入 `packages/sdk/src/client.ts` 和 `packages/sdk/src/transport.ts`。

`packages/plugin-sdk/package.json` 的 `exports` 是插件 SDK 的入口地图。因为它暴露的子路径很多，阅读时不要从文件列表逐个展开，而应先按能力分组：插件声明入口看 `plugin-entry`；provider 声明看 `provider-entry`；运行时能力看 `plugin-runtime`、`config-runtime`、`gateway-method-runtime`、`security-runtime`；模型/provider 能力看 `provider-model-types`、`provider-stream-shared`、`provider-tools`、`provider-web-search`。

`packages/plugin-package-contract/src/index.ts` 是外部插件包校验入口。它的主线很集中：先用 `readOpenClawBlock` 从 `package.json` 里取 `openclaw`、`compat`、`build`、`install`；再用 `normalizeExternalPluginCompatibility` 归一化兼容性信息；最后用 `validateExternalCodePluginPackageJson` 返回兼容信息和缺失字段列表。

`packages/memory-host-sdk/package.json` 的 `exports` 是 memory host 的入口地图。由于当前只读取到文件名和导出表，主入口可先从 `packages/memory-host-sdk/src/runtime.ts`、`packages/memory-host-sdk/src/engine.ts`、`packages/memory-host-sdk/src/query.ts` 这三个方向进入。

## 主流程位置

客户端调用主流程大致在 `packages/sdk/src/client.ts`、`packages/sdk/src/transport.ts`、`packages/sdk/src/event-hub.ts`、`packages/sdk/src/normalize.ts` 之间展开：`client.ts` 提供面向调用方的 `OpenClaw` 与各 namespace；`transport.ts` 负责连接/请求传输；`event-hub.ts` 处理 gateway event；`normalize.ts` 负责把 gateway event 归一化成 SDK 侧事件结构。具体细节需继续阅读这些文件确认。

插件开发主流程的入口不在 `extensions/` 的具体插件里，而在 `packages/plugin-sdk` 暴露的门面与根部 `src/plugin-sdk` 实现之间。当前片段显示 `packages/plugin-sdk/src/plugin-entry.ts`、`provider-entry.ts`、`plugin-runtime.ts` 只是再导出，因此追主流程时要从 package export 名称进入，再跳到对应的 `src/plugin-sdk/*.ts` 看真实类型和运行时契约。

外部插件安装/兼容性校验流程可从 `packages/plugin-package-contract/src/index.ts` 读起。这个包不执行安装，而是提供判断 package metadata 是否满足 OpenClaw 外部 code plugin 要求的纯函数。它特别关注必填字段 `openclaw.compat.pluginApi` 和 `openclaw.build.openclawVersion`。

memory host 流程根据当前片段推断分为 runtime 与 engine 两层：`runtime*` 文件更靠近命令行、文件、运行上下文；`engine*` 文件更靠近存储、embedding、QMD、foundation 能力；`query.ts`、`multimodal.ts`、`secret.ts`、`status.ts` 是支撑查询、多模态、密钥和状态的侧向模块。

## 推荐阅读顺序

1. 先读 `packages/*/package.json`，只看 `name` 和 `exports`。这一步能建立“哪些路径是正式入口”的边界感，避免被 `src` 文件列表带偏。

2. 再读 `packages/sdk/src/index.ts`。它最短、最集中，适合快速理解 OpenClaw SDK 对外暴露的对象模型：client、namespace、transport、event、types。

3. 接着读 `packages/plugin-sdk/package.json` 的 exports 分组。先不要逐文件看实现，先把插件入口、provider 入口、runtime helpers、模型相关能力、配置/安全/doctor 能力分开。

4. 然后读 `packages/plugin-package-contract/src/index.ts`。这个文件逻辑独立，能帮助理解外部插件 package metadata 的兼容性字段如何被归一化和校验。

5. 最后读 `packages/memory-host-sdk`。建议从 `runtime.ts`、`engine.ts`、`query.ts` 三条主线开始，再按需要进入 `engine-storage.ts`、`engine-embeddings.ts`、`engine-qmd.ts` 等支撑模块。

## 常见误区

不要把 `packages/plugin-sdk` 当成所有插件逻辑的实现目录。当前片段显示它至少有部分文件只是对 `src/plugin-sdk` 的 package 门面再导出；具体插件行为仍可能在 `extensions/` 或核心插件运行时里。

不要绕过 package exports 直接依赖内部文件。`packages` 的价值就在于定义稳定子路径，如 `@openclaw/plugin-sdk/provider-entry` 或 `@openclaw/sdk` 这类入口；直接读内部实现可以学习，但不等于推荐调用方式。

不要把 `packages/sdk` 和 `packages/plugin-sdk` 混为一谈。前者面向 OpenClaw 客户端调用 gateway；后者面向插件/provider 作者和插件运行时契约。一个是“使用 OpenClaw”，一个是“扩展 OpenClaw”。

不要期望 `plugin-package-contract` 负责完整安装流程。它只根据 `package.json` 片段归一化和校验兼容性字段；插件发现、加载、安装记录、运行时解析应继续去 `src/plugins/*` 等位置寻找。

不要在 overview 阶段逐叶子文件展开。`packages` 是边界目录，优先理解四个子包的角色、exports、入口和跨目录关系，比逐个解释 `provider-*`、`engine-*` 文件更有效。
