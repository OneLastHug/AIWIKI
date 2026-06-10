# 文件：packages/coding-agent/src/core/settings-manager.ts

## 一句话定位

`packages/coding-agent/src/core/settings-manager.ts` 是 `coding-agent` 的运行时设置中心，负责定义用户配置结构、读取全局/项目级 `settings.json`、合并默认值与覆盖项，并向主流程、会话、资源加载和交互界面提供类型化的配置读写入口。

## 它暴露/定义了什么

这个文件主要定义三类东西。

第一类是设置数据模型：`Settings` 及其子配置接口，例如 `CompactionSettings`、`BranchSummarySettings`、`RetrySettings`、`TerminalSettings`、`ImageSettings`、`ThinkingBudgetsSettings`、`MarkdownSettings`、`WarningSettings`。这些字段覆盖默认 provider/model、thinking level、传输方式、主题、压缩策略、重试策略、终端显示、图片处理、资源路径、技能命令、session 目录、HTTP/WebSocket 超时等。

第二类是存储抽象：`SettingsStorage`、`FileSettingsStorage`、`InMemorySettingsStorage`。`FileSettingsStorage` 面向真实文件系统，管理全局设置文件和项目设置文件；`InMemorySettingsStorage` 主要服务测试或临时构造，避免落盘。

第三类是核心管理器：`SettingsManager`。根据当前片段和调用点推断，它提供 `create()`、`inMemory()`、`applyOverrides()`、`drainErrors()` 以及大量 `get...` / `set...` 方法，例如 `getDefaultProvider()`、`getDefaultModel()`、`getTheme()`、`getEnabledModels()`、`getSessionDir()`、`getHttpIdleTimeoutMs()`、`getImageAutoResize()`、`setExtensionPaths()`、`setSkillPaths()` 等。

## 谁调用它

主要入口在 `packages/coding-agent/src/main.ts`。启动阶段会创建 `startupSettingsManager`，用于 session 查找、默认信任策略和启动诊断；进入实际运行后再创建 `runtimeSettingsManager`，并把它注入服务集合。`main.ts` 还通过它初始化主题、配置 HTTP dispatcher、选择默认 provider/model、读取 enabled models、图片 resize 策略和 session 目录。

`packages/coding-agent/src/core/agent-session.ts` 持有 `settingsManager`，让会话逻辑读取压缩、队列、模型、thinking、bash、图片等运行偏好。

`packages/coding-agent/src/modes/interactive/interactive-mode.ts` 通过 `session.settingsManager` 读取 TUI 行为设置，例如硬件光标、显示偏好、主题相关状态，并可能通过命令修改持久化设置。

`packages/coding-agent/src/core/resource-loader.ts` 相关测试显示它会读取 `packages`、`extensions`、`skills`、`prompts`、`themes` 等资源配置；项目设置是否可信会影响本地资源加载。

测试中，`SettingsManager.inMemory()` 被用于验证图片阻断、资源路径、压缩配置等行为。

## 它调用谁

文件系统层面调用 Node `fs` 的 `existsSync`、`mkdirSync`、`readFileSync`、`writeFileSync`，以及 `path` 的 `dirname`、`join`。

并发写入保护依赖 `proper-lockfile`。`FileSettingsStorage.withLock()` 会在读写设置文件时尝试获取锁，遇到 `ELOCKED` 会短暂同步重试。

路径和配置目录来自 `../config.ts` 的 `CONFIG_DIR_NAME`、`getAgentDir`，以及 `../utils/paths.ts` 的 `resolvePath`、`normalizePath`。超时字段校验复用 `./http-dispatcher.ts` 的 `parseHttpIdleTimeoutMs` 和 `DEFAULT_HTTP_IDLE_TIMEOUT_MS`。

类型层面还引用 `@earendil-works/pi-ai` 的 `Transport`，让 `Settings.transport` 与底层 AI 传输设置保持一致。

## 核心流程

配置读取流程大致是：`SettingsManager.create(cwd, agentDir, options)` 构造文件存储，定位全局设置和项目设置。全局设置位于 agent 目录下的 `settings.json`；项目设置位于当前工作目录下 `CONFIG_DIR_NAME/settings.json`。项目设置只有在 `projectTrusted` 允许时才应参与加载；根据当前片段推断，这是为了防止不可信仓库通过本地配置影响工具行为或加载任意资源。

读取到 JSON 后会解析为 `Settings`。解析失败不会直接让整个程序崩溃，而是记录为 `SettingsError`，由 `drainErrors()` 交给上层收集诊断并展示。`main.ts` 中的 `collectSettingsDiagnostics()` 就是这一用途。

合并流程由 `deepMergeSettings(base, overrides)` 支撑：项目配置或运行时覆盖项优先，嵌套对象做一层浅合并，数组和基本类型整体替换。也就是说 `terminal`、`images`、`retry` 这类对象可以局部覆盖；但 `packages`、`extensions`、`enabledModels` 这类数组不会拼接，而是以后者为准。

写入流程通过 `SettingsStorage.withLock(scope, fn)` 完成。调用方传入当前 JSON 到新 JSON 的转换函数；如果返回 `undefined` 则不写入，如果返回字符串则创建目录、加锁并写回。这样 `SettingsManager` 可以把各种 `set...` 方法统一落到全局或项目作用域。

## 关键函数的高层作用

`deepMergeSettings()` 是配置优先级规则的核心：保留 base，跳过 `undefined`，对象字段合并，数组和标量覆盖。修改它会影响所有设置项的继承语义。

`parseTimeoutSetting()` 负责把 HTTP/WebSocket 超时类字段交给统一解析器，并在非法值出现时抛出带字段名的错误。它让配置错误能被明确定位。

`FileSettingsStorage.withLock()` 是文件持久化的关键路径：它负责判断文件是否存在、读取当前内容、按需创建目录、获取锁、写入新内容并释放锁。它是同步实现，因此调用方不需要改成 async。

`FileSettingsStorage.acquireLockSyncWithRetry()` 是并发保护的辅助函数：针对 `ELOCKED` 做有限次同步等待重试，避免多个进程同时更新设置时直接失败。

`InMemorySettingsStorage.withLock()` 是测试版存储：保持同样接口，但只在内存中读写 global/project 字符串。

`SettingsManager.create()` 根据当前片段推断是生产入口，负责组装 `FileSettingsStorage`、读取配置并处理项目可信状态。`SettingsManager.inMemory()` 是测试和构造场景入口。各种 `get...` 方法承担“返回用户配置或默认值”的职责；各种 `set...` 方法承担“更新 JSON 并持久化”的职责；`applyOverrides()` 用于把 CLI 参数或运行时选择覆盖到当前设置视图。

## 修改风险

新增设置项时，不能只往 `Settings` 里加字段。通常还要补 getter 默认值、必要的 setter、解析/校验逻辑、调用方接入，以及相关测试。否则字段可能能被 JSON 读取，但运行时永远不用，或非法值静默进入核心流程。

合并规则风险较高。当前对象是一层浅合并，数组是整体替换；如果把数组改成拼接，`packages`、`extensions`、`skills` 等资源加载行为会变化，可能引入重复加载或不可信路径问题。如果把对象改成深层递归，也可能改变已有用户配置的覆盖结果。

项目级设置涉及信任边界。任何让未信任项目设置生效的改动，都可能影响模型、shell、资源加载、插件/技能路径、命令前缀或 session 存储位置，安全面较大。

文件锁和同步 I/O 是启动与交互命令的基础设施。调整 `withLock()`、重试次数或写入时机时，要考虑多进程同时运行 `pi`、设置文件不存在、目录不存在、JSON 损坏、锁文件残留等情况。

超时、重试、图片阻断、shell 前缀、资源路径这类字段会直接影响外部 provider、终端执行和本地文件访问。修改默认值可能不是局部行为变化，而是整个 agent 的运行策略变化，应配合 `main.ts`、`agent-session.ts`、`resource-loader.ts` 的调用点一起审查。
