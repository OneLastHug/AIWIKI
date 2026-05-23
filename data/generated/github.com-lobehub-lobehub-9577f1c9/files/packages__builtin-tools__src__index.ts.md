# 文件：packages/builtin-tools/src/index.ts

## 一句话定位

`packages/builtin-tools/src/index.ts` 是 LobeHub 内置工具的总注册表：它集中导出“有哪些 builtin tool、默认启用哪些、哪些永远启用、哪些受运行时托管、哪些在 chat mode 可用”等核心名单，供前端工具商店、聊天工具引擎、服务端 agent 工具引擎和执行链路共同消费。

## 它暴露/定义了什么

这个文件主要暴露六类常量。

`defaultToolIds` 定义默认会加入工具列表的内置工具标识，例如 `lobe-activator`、`lobe-skills`、`lobe-web-browsing`、`lobe-knowledge-base`、`lobe-memory`、`lobe-local-system`、`lobe-cloud-sandbox`、`lobe-task`、`lobe-agent` 等。注释明确说明它被前端 `createAgentToolsEngine` 和服务端 `createServerAgentToolsEngine` 共享。

`alwaysOnToolIds` 定义无论用户如何选择都应启用的核心系统工具，目前包括 activator、skills、skill store。这类工具更像 agent 的基础能力，不是普通可选插件。

`manualModeExcludeToolIds` 定义手动技能激活模式下要从默认工具中排除的发现类工具，例如 activator 和 skill store，用于让用户获得更精确的控制。

`chatModeAllowedToolIds` 定义非 agent mode，也就是 `chatConfig.enableAgentMode === false` 时的严格外层白名单，目前只允许 knowledge base、memory、web browsing。实际是否启用还要继续经过各自运行时条件判断。

`runtimeManagedToolIds` 定义启用状态不由用户开关直接决定，而由系统运行条件决定的工具，例如 cloud sandbox、knowledge base、local system、memory、remote device、lobe agent、web browsing。该列表还影响聊天输入框 Tools popover 的展示逻辑。

`builtinTools` 是最核心的数据结构，类型为 `LobeBuiltinTool[]`。每一项把某个工具包导出的 `Manifest` 包装成统一的 builtin tool 元数据，字段包括 `identifier`、`manifest`、`type: 'builtin'`，以及可选的 `hidden`、`discoverable`。文件末尾还根据 `RECOMMENDED_SKILLS` 计算 `defaultUninstalledBuiltinTools`，表示“非隐藏且不在推荐列表中”的 builtin tool 默认未安装，需要用户从 Skill Store 显式安装。

## 谁调用它

前端侧，`src/helpers/toolEngineering/index.ts` 导入 `alwaysOnToolIds`、`chatModeAllowedToolIds`、`defaultToolIds`，在 `createAgentToolsEngine` 中组合当前 agent 配置、用户插件、搜索配置、知识库状态、记忆设置等，最终创建 `ToolsEngine`。同文件的 `createToolsEngine` 不直接导入 `builtinTools`，而是从 tool store 的 `builtinTools` 状态读取 manifest；这个状态来自 `src/store/tool/slices/builtin/initialState.ts` 对本文件 `builtinTools` 的初始化。

服务端侧，`src/server/modules/Mecha/AgentToolsEngine/index.ts` 导入 `builtinTools`、`defaultToolIds`、`alwaysOnToolIds`、`chatModeAllowedToolIds`，在 `createServerToolsEngine` 和 `createServerAgentToolsEngine` 中构造服务端 `ToolsEngine`。服务端还会结合设备访问权限、runtime mode、知识库、memory、web browsing 等条件决定哪些工具实际可用。

工具商店和展示侧，`src/store/tool/slices/builtin/initialState.ts` 使用 `builtinTools` 和 `defaultUninstalledBuiltinTools` 初始化 Zustand 状态；`src/store/tool/slices/builtin/selectors.ts` 使用 `runtimeManagedToolIds` 过滤或标记运行时托管工具；`src/features/SkillStore/*`、`src/routes/(main)/settings/skill/*`、社区 agent 详情页等通过 store 或直接查询 builtin tool 元数据来展示能力信息。

执行与安全侧，`src/server/services/aiAgent/deviceToolRegistry.ts` 会基于 `builtinTools` 做设备工具的物理过滤；`src/server/services/aiAgent/index.ts` 也会使用 `builtinTools` 和 `manualModeExcludeToolIds` 构建 agent 可用工具范围。根据当前片段推断，这些调用共同保证“模型看到的 manifest”和“运行时真正允许执行的工具”尽量一致，依据是 server engine 中对 `buildAllowedBuiltinTools`、`excludeIdentifiers`、`allowExplicitActivation` 的注释。

## 它调用谁

这个文件本身不执行复杂逻辑，主要依赖各个 `@lobechat/builtin-tool-*` 包导出的 manifest，例如 `WebBrowsingManifest`、`KnowledgeBaseManifest`、`LocalSystemManifest`、`MemoryManifest`、`TaskManifest`、`CalculatorManifest` 等。它还依赖 `@lobechat/const` 的 `isDesktop`、`RECOMMENDED_SKILLS`、`RecommendedSkillType`，以及 `@lobechat/types` 的 `LobeBuiltinTool` 类型。

其中 `isDesktop` 用于决定 `LocalSystemManifest` 是否 `discoverable`；`RECOMMENDED_SKILLS` 用来反推哪些非隐藏 builtin tool 默认未安装；各 Manifest 的 `identifier` 是所有名单的基础键。

## 核心流程

启动或初始化 tool store 时，`builtinTools` 被写入前端状态，成为内置工具的元数据来源。随后前端 `createToolsEngine` 从 store 中提取所有 builtin manifest，并与用户安装插件、Klavis 工具、LobeHub skills、额外 manifest 合并，传给 `ToolsEngine`。

进入具体聊天时，`createAgentToolsEngine` 会根据当前是否 chat mode 选择 `defaultToolIds` 或 `chatModeAllowedToolIds`。在 agent mode 下，它会把用户选择的插件、运行时解析出的插件和 `alwaysOnToolIds` 放入 enable rules；在 chat mode 下，它只保留白名单内的 knowledge base、memory、web browsing，并关闭显式激活，避免 activator 绕过限制。

服务端流程与前端对齐。`createServerAgentToolsEngine` 同样依据 chat mode 选择默认工具列表，并结合服务端上下文判断 cloud sandbox、local system、remote device、memory、knowledge base、web browsing 是否满足运行条件。对于设备类工具，服务端还会先通过 `buildAllowedBuiltinTools` 过滤 `builtinTools`，再通过 enable checker 做防御式判断。

Skill Store 相关流程则使用 `defaultUninstalledBuiltinTools` 决定哪些 builtin tool 初始呈现为未安装状态；`hidden`、`discoverable` 和 `runtimeManagedToolIds` 共同影响用户是否能看见、安装或手动切换某个工具。

## 关键函数的高层作用

这个文件没有函数，关键逻辑由常量和一个派生集合承担。

`builtinTools` 是全局注册表，新增 builtin tool 最终必须出现在这里，才能进入前端 store、manifest 合并、Skill Store 展示和部分服务端过滤流程。

`defaultToolIds` 是默认工具入口，决定未显式选择时 agent 会自动携带哪些 builtin 能力。它不是最终启用结果，还会被 `ToolsEngine` 和 enable checker 继续过滤。

`alwaysOnToolIds` 是 agent mode 下的强制启用核心工具列表，修改它会直接改变 activator、skills、skill store 这类基础能力是否稳定可用。

`chatModeAllowedToolIds` 是 chat mode 的安全边界。它不是普通默认列表，而是严格白名单；加入新工具意味着非 agent mode 也可能暴露该工具 manifest。

`runtimeManagedToolIds` 是 UI 与运行时规则之间的约定列表。注释要求它与 `src/server/modules/Mecha/AgentToolsEngine/index.ts` 的 rules map、`src/helpers/toolEngineering/index.ts` 的前端规则保持同步。

`defaultUninstalledBuiltinTools` 根据 `builtinTools` 和 `RECOMMENDED_SKILLS` 自动派生默认未安装工具。辅助变量 `recommendedBuiltinIds` 只是把推荐 builtin id 转成 `Set` 方便过滤。

## 修改风险

最大风险是注册表与执行器、UI、i18n、服务端规则不同步。新增工具只改 `builtinTools` 还不够，通常还要同步 `packages/builtin-tools/src/inspectors.ts`、`renders.ts`、`placeholders.ts`、`streamings.ts`、`interventions.ts`、`portals.ts`，以及 `src/store/tool/slices/builtin/executors/index.ts`。否则可能出现 manifest 能被模型看见，但前端无法执行、无法渲染，或工具调用卡在 loading 状态。

第二个风险是 identifier 稳定性。`identifier` 来自各 tool manifest，并会进入消息历史、工具选择、执行路由和权限判断。重命名内置工具会破坏历史消息和已有配置，通常需要兼容别名或迁移策略。

第三个风险是 chat mode 越权。`chatModeAllowedToolIds` 的注释说明 chat mode 会丢弃用户插件和 always-on 工具，并禁止显式激活。把高权限工具加入该列表，可能让普通聊天模式暴露不应出现的工具 schema。

第四个风险是 runtime-managed 列表漂移。`runtimeManagedToolIds` 和前后端 enable rules 不一致时，用户界面可能显示可切换，但运行时强制启用或禁用；反过来也可能 UI 隐藏了实际可用能力，导致排查困难。

第五个风险是 `hidden`、`discoverable`、`RECOMMENDED_SKILLS` 的产品语义变化。它们不只是展示字段，还会影响 Skill Store、默认未安装列表、桌面环境下 local system 的可发现性。比如错误地取消 `hidden` 可能让系统工具出现在用户可安装列表中；错误地设置 `discoverable` 可能在不支持的平台展示不可用能力。

第六个风险是服务端安全过滤遗漏。设备相关工具不仅依赖本文件，还依赖 `deviceToolRegistry` 和 server engine 的双重过滤。新增类似 local/remote/device 权限的工具时，如果只加入 `builtinTools` 而没有加入运行时规则，可能出现 manifest 暴露、执行不可达，或更严重的权限边界不清。
