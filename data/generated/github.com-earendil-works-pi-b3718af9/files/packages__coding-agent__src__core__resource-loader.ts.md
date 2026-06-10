# 文件：`packages/coding-agent/src/core/resource-loader.ts`

## 一句话定位
这个文件定义了 coding agent 的“资源装配层”：把扩展、skills、prompts、themes、agents context files、system prompt 等分散来源统一加载、合并、去重、打诊断，并对外提供一个可重载的 `ResourceLoader` 接口。根据当前片段推断，它是 agent 启动和重载配置时的中枢入口之一。

## 它暴露/定义了什么
它主要暴露三块内容：`ResourceLoader` 接口、`DefaultResourceLoader` 默认实现，以及 `loadProjectContextFiles()` 这类独立工具函数。接口层把外部关心的能力固定成几组读取方法：`getExtensions()`、`getSkills()`、`getPrompts()`、`getThemes()`、`getAgentsFiles()`、`getSystemPrompt()`、`getAppendSystemPrompt()`，再加上 `extendResources()` 和 `reload()` 这两个控制入口。文件里还导出了 `ResourceDiagnostic`、`ResourceCollision`，说明它不只是“读资源”，还负责把冲突和错误向上游暴露。

## 谁调用它
从引用关系看，直接调用者很多，但职责最集中的是 `packages/coding-agent/src/core/agent-session-services.ts`、`packages/coding-agent/src/core/agent-session.ts`、`packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/package-manager-cli.ts`。其中 `sdk.ts` 和 `agent-session-services.ts` 会直接实例化 `DefaultResourceLoader`；`agent-session.ts` 通过 `ResourceLoader` 依赖它的结果；`package-manager-cli.ts` 也会在命令行流程里创建它。测试侧大量使用 `packages/coding-agent/test/resource-loader.test.ts`、`packages/coding-agent/test/utilities.ts` 和若干回归测试来验证它的行为。

## 它调用谁
它依赖的下游模块比较清晰：`settings-manager.ts` 提供设置读取和默认构造参数，`package-manager.ts` 负责解析包和资源位置，`extensions/loader.ts` 负责加载扩展，`skills.ts`、`prompt-templates.ts` 分别加载技能与提示模板，`source-info.ts` 用来记录来源信息，`event-bus.ts` 负责事件分发，`config.ts` 提供配置目录名，`paths.ts` 负责路径规范化。文件头部还引入了 `loadThemeFromPath` 和 `Theme`，说明 themes 的来源解析也在这里收口。另有 `chalk` 和 `fs/path` 这类基础设施用于文件读取、告警和路径处理。

## 核心流程
主流程可以概括成“收集源 -> 解析资源 -> 合并结果 -> 生成诊断 -> 暴露给上层”。`DefaultResourceLoader` 构造时先规范化 `cwd`、`agentDir`，再初始化 `SettingsManager`、`EventBus`、`DefaultPackageManager`，同时接收一批开关和 override 钩子，比如 `noSkills`、`noPromptTemplates`、`extensionsOverride`、`systemPromptOverride` 等。`loadProjectContextFiles()` 会沿着当前工作目录向上找 `AGENTS.md`、`CLAUDE.md` 一类上下文文件，并把 `agentDir` 下的全局上下文放在前面，最后按祖先顺序合并，确保上下文加载有稳定优先级。

真正的资源加载逻辑在 `reload()` 中展开，虽然当前片段没有完整展示实现，但从字段命名和引用关系看，它会分别刷新 extensions、skills、prompts、themes、agentsFiles，再应用 override 和禁用开关，最终把结果缓存到实例字段里，供各个 `get*()` 方法直接读取。也就是说，它既是加载器，也是一个带缓存的资源快照对象。

## 关键函数的高层作用
`resolvePromptInput()` 用来把 system prompt 这类输入按“文件路径或直接文本”两种形态兼容处理。`loadContextFileFromDir()` 负责在单个目录里探测上下文文件并读取内容。`loadProjectContextFiles()` 负责跨目录向上聚合 context files，是整个资源加载链里最明显的规则函数。`DefaultResourceLoader` 的构造函数主要做依赖注入和默认值初始化；`reload()` 负责把所有资源重新同步一遍；`extendResources()` 则给外部一个在已有资源集合上追加额外路径的入口。

## 修改风险
这个文件改动风险高，因为它是 agent 启动期的资源总入口。最容易出问题的是资源优先级变化、重复资源去重逻辑、diagnostic 语义、`no*` 开关行为，以及 reload 后缓存是否一致。另一个风险是路径处理：`resolvePath()`、`canonicalizePath()`、祖先目录遍历、以及 `agentDir`/`cwd` 的相对关系，一旦改错会直接影响上下文文件、skills 和 prompt 的可见性。还有一类风险是回归测试覆盖不到的“看似能跑、实际少加载资源”问题，尤其涉及 extensions 和 overrides 时，建议把修改范围控制在单一加载分支里，并优先用现有 `resource-loader.test.ts` 和相关回归测试验证。
