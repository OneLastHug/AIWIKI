# 目录：extensions/lobster

## 它负责什么

`extensions/lobster` 是 OpenClaw 的内置插件目录之一，负责把外部包 `@clawdbot/lobster` 提供的 typed workflow 能力接入 OpenClaw agent tool 体系。它注册的工具名是 `lobster`，插件 manifest 中描述为 “Typed workflow tool with resumable approvals”，也就是面向 JSON-first 工作流、可恢复审批、以及可被 agent 调用的本地工作流执行入口。

从 `openclaw.plugin.json` 看，这个插件 `id` 为 `lobster`，`activation.onStartup` 为 `true`，并声明 `contracts.tools` 包含 `lobster`。同时 `toolMetadata.lobster.optional` 为 `true`，说明它不是默认无条件暴露给所有 agent 的基础工具，而是需要经过工具策略或 allowlist 启用。`README.md` 也强调该工具可能触发带副作用的 workflow，因此应以较窄的 `tools.allow` 控制可用范围。

边界上，`extensions/AGENTS.md` 要求插件生产代码通过 `openclaw/plugin-sdk/*` 和本插件本地 barrel 访问 SDK，不应深度导入 core 内部。`extensions/lobster` 基本遵循这个形态：入口从 `openclaw/plugin-sdk/plugin-entry` 定义插件，运行时类型和少量 SDK facade 集中在 `runtime-api.ts`。

## 直接子目录地图

这个目录不是大目录，直接子目录只有一个：

`extensions/lobster/src`：插件的主要实现区。这里放置 Lobster runner、taskflow 集成、tool 参数解析、AJV 编译缓存补丁，以及对应的单元测试和测试 helper。学习时可以把它看成三层：工具入口层、工作流管理层、底层 Lobster runtime 适配层。

根目录文件承担插件元数据和导出职责：

`extensions/lobster/openclaw.plugin.json` 描述插件 id、启动时激活、工具 contract、可选工具标记和空配置 schema。

`extensions/lobster/package.json` 描述 npm 包名 `@openclaw/lobster`、依赖 `@clawdbot/lobster`、`ajv`、`typebox`，以及 OpenClaw 插件安装、兼容版本、发布元数据。

`extensions/lobster/index.ts` 是插件入口，负责注册 tool factory。

`extensions/lobster/runtime-api.ts` 是本插件面对 SDK 的本地 facade，转出核心类型和 Windows spawn policy 工具。

`extensions/lobster/README.md` 是面向使用者的说明，解释如何启用 `lobster`，以及 Lobster 工作流通过 `openclaw.invoke` 回调 OpenClaw 工具时的安全边界。

`extensions/lobster/SKILL.md` 根据当前片段推断是与 Lobster 使用或 agent 工作流相关的技能说明文件；本次概览没有展开其内容，因此只把它标为辅助说明入口。

## 关键入口

最核心入口是 `extensions/lobster/index.ts`。它调用 `definePluginEntry`，声明插件 `id: "lobster"`，并在 `register(api)` 中调用 `api.registerTool(...)`。这里的 tool factory 会先检查 `ctx.sandboxed`，如果当前上下文是 sandboxed，就返回 `null`，表示不提供该工具；如果可用，则通过 `createLobsterTool(api, { taskFlow })` 创建实际 agent tool。

`taskFlow` 的取得也发生在 `index.ts`：当 `api.runtime?.tasks.managedFlows` 存在且 `ctx.sessionKey` 存在时，入口会通过 `api.runtime.tasks.managedFlows.fromToolContext(ctx)` 绑定一个当前会话相关的 managed flow runtime。根据当前片段推断，这就是 Lobster 审批等待和恢复能力接入 OpenClaw 会话任务系统的位置，依据是 `src/lobster-taskflow.ts` 中存在 `runManagedLobsterFlow`、`resumeManagedLobsterFlow`，而 `src/lobster-tool.ts` 中存在 `parseRunFlowParams`、`parseResumeFlowParams`、`requireTaskFlowRuntime` 等函数。

`extensions/lobster/src/lobster-tool.ts` 是 agent 工具的用户态入口。它导出 `createLobsterTool`，并负责读取、校验、整理工具参数。函数名显示它会处理可选字符串、数字、布尔值、flow state JSON，并区分 run flow 与 resume flow 参数。它还负责把 managed flow 的执行结果格式化为工具返回值。

`extensions/lobster/src/lobster-runner.ts` 是底层执行入口。它导出 `createEmbeddedLobsterRunner`、`loadEmbeddedToolRuntimeFromPackage`、`resolveLobsterCwd` 等能力，负责定位并加载 `@clawdbot/lobster/core` 运行时、解析 workflow 文件、构建 embedded tool context、控制 stdout/stderr 上限、处理 timeout，并把 Lobster 的 envelope 标准化为插件内部结果。

## 主流程位置

主流程可以按“注册、调用、执行、审批恢复”四段理解。

第一段在 `extensions/lobster/index.ts`：OpenClaw 启动加载插件，插件注册 optional tool。这里决定工具是否在当前上下文可用，并把 OpenClaw runtime 的 managed flow 能力传入 `createLobsterTool`。

第二段在 `extensions/lobster/src/lobster-tool.ts`：agent 调用 `lobster` 后，工具层解析参数。根据当前片段推断，它支持至少两类动作：启动一个 managed Lobster flow，以及恢复已有 flow。依据是文件中有 `parseRunFlowParams`、`parseResumeFlowParams`、`resolveManagedFlowToolResult`，测试文件也有 `createRunFlowParams`、`createResumeFlowParams`。

第三段在 `extensions/lobster/src/lobster-taskflow.ts` 和 `extensions/lobster/src/lobster-runner.ts` 之间：`lobster-taskflow.ts` 把 Lobster runner 的执行结果接入 OpenClaw 的 managed task flow。它关注 approval wait state、flow state 的 JSON 化、错误 envelope 的转换，以及 run/resume 两条路径。`lobster-runner.ts` 则更靠近 `@clawdbot/lobster` 包本身，负责真正加载 runtime、解析 workflow 参数、执行 workflow、归一化返回 envelope。

第四段是审批等待和恢复：当 Lobster workflow 需要 approval 时，`lobster-taskflow.ts` 会根据 envelope 构造 wait state；恢复时再通过 `resumeManagedLobsterFlow` 继续执行。这里是 “resumable approvals” 的关键位置，而不是在插件入口层完成。

另一个横切点是 `extensions/lobster/src/lobster-ajv-cache.ts`。它导出 `installLobsterAjvCompileCache`，从函数名看用于给 Lobster 相关 AJV schema 编译加缓存，减少重复 schema 编译成本。它不是主业务入口，但会影响 runner 执行性能和重复 workflow schema 的处理。

## 推荐阅读顺序

1. 先读 `extensions/lobster/openclaw.plugin.json`，确认插件 id、启动方式、工具 contract、optional 标记和配置面。这个文件能最快回答“它作为插件暴露了什么”。

2. 再读 `extensions/lobster/package.json`，确认它依赖的是 `@clawdbot/lobster`，并了解它是可发布到 npm 和 ClawHub 的插件包，而不是只存在于 core 内部的临时代码。

3. 然后读 `extensions/lobster/index.ts`，抓住注册路径：`definePluginEntry`、`api.registerTool`、`ctx.sandboxed`、`managedFlows.fromToolContext(ctx)`、`createLobsterTool`。

4. 接着读 `extensions/lobster/src/lobster-tool.ts`，理解 agent tool 参数如何被解析为 run/resume 行为，以及返回值如何格式化。

5. 再读 `extensions/lobster/src/lobster-taskflow.ts`，重点看 managed flow、approval wait state、resume 的关系。

6. 最后读 `extensions/lobster/src/lobster-runner.ts` 和 `extensions/lobster/src/lobster-ajv-cache.ts`，前者解释如何嵌入并调用 `@clawdbot/lobster`，后者解释 schema 编译缓存这种支撑性优化。

测试可以作为反向索引阅读：`extensions/lobster/src/lobster-tool.test.ts` 看工具参数与返回行为，`extensions/lobster/src/lobster-taskflow.test.ts` 看 run/resume 和审批状态，`extensions/lobster/src/lobster-runner.test.ts` 看底层 runtime 适配、cwd、envelope、缓存和错误处理。

## 常见误区

不要把 `lobster` 当成 core 内建工具。它位于 `extensions/` 下，是插件边界内的实现；入口通过 Plugin SDK 注册，元数据也由 `openclaw.plugin.json` 和 `package.json` 描述。

不要以为 `activation.onStartup` 等于所有 agent 默认可用。manifest 和 README 都显示 `lobster` 是 optional tool；实际可用性还要受 agent tool allow/deny 策略影响。

不要绕过 `extensions/lobster/index.ts` 直接理解 `src/lobster-runner.ts`。runner 只是底层执行适配，真正接入 OpenClaw 的工具注册、sandbox 判断、managed flow 绑定发生在 `index.ts`。

不要把审批恢复逻辑理解成普通同步工具调用。`lobster-taskflow.ts` 的存在说明它和 OpenClaw managed flows 有耦合：workflow 可以进入等待状态，再由 resume 路径继续。

不要把 `openclaw.invoke` 理解成 Lobster 自动拥有所有 OpenClaw 工具权限。README 明确说明回调 OpenClaw 工具要经过 Gateway auth 和 tool policy；如果工具未被允许，会被视为不可用。

不要在学习时逐个叶子文件平均用力。这个目录的主线很集中：`index.ts` 注册，`lobster-tool.ts` 解析工具调用，`lobster-taskflow.ts` 管理审批型 flow，`lobster-runner.ts` 调外部 Lobster runtime。测试和缓存文件是验证与支撑面。
