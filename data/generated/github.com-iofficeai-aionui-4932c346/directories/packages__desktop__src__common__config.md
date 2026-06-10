# 子系统：packages/desktop/src/common/config

## 解决什么问题

这个目录是桌面端的“通用配置层”，负责把分散在主进程、渲染器、WebUI 和迁移脚本里的配置读写规则统一起来。它解决的不是单一业务设置，而是三类基础问题：第一，定义哪些配置键是合法的，以及每个键对应什么类型；第二，提供一套跨进程、跨运行模式可复用的读写入口；第三，处理旧配置到新配置的迁移、语言归一化、环境变量映射和默认常量。

根据当前片段推断，它更像是“配置领域的公共协议层”。渲染器页面会通过它读写主题、语言、系统设置、工具配置；主进程则用它做启动迁移、路径隔离和后端初始化。

## 相关目录和文件

这个目录的骨架很清楚：

`configService.ts` 是运行时读写入口，向 `/api/settings/client` 取值并写回。  
`storage.ts` 定义 `ConfigStorage`、`EnvStorage` 以及超大的 `IConfigStorageRefer`，是本地持久化字段的类型中心。  
`configKeys.ts` 把配置键收敛成 `ConfigKeyMap` 和 `ConfigKey`，供 `configService` 做强类型访问。  
`configMigration.ts` 负责把旧的本地配置、旧 MCP 配置和 provider 配置迁到后端。  
`i18n.ts` 提供语言归一化、资源合并和国际化辅助函数。  
`imageGenerationMcpEnv.ts` 把图片生成模型选择转换成 MCP 进程环境变量。  
`fontSizes.ts` 管理聊天、Markdown、代码三类字号的默认值、范围和配置键映射。  
`constants.ts` 放通用常量，如 `WEBUI_DEFAULT_PORT`、`GOOGLE_AUTH_PROVIDER_ID`。  
`appEnv.ts` 处理开发/打包环境下的目录命名。  
`storageKeys.ts` 则是局部 `localStorage` 键的集中定义。  
`i18n-config.json` 提供支持语言和默认语言的静态配置。

## 核心对象

最核心的是 `configService`。它内部维护缓存、订阅者和初始化状态，提供 `get`、`set`、`setBatch`、`remove`、`setLocal`、`subscribe`、`whenReady` 等能力。它的关键点不是“能读写”，而是“模块加载阶段也能稳定拿到缓存值”，并且在主题迁移时自动补一次旧键到新键的转换。

第二个核心对象是 `ConfigStorage` 和 `EnvStorage`。它们不是普通对象，而是基于 `@office-ai/platform` 的存储适配器，分别对应 `agent.config` 和 `agent.env`。前者承载用户配置，后者承载运行环境信息。

第三个核心对象是 `ConfigKeyMap`。它把每个配置键的真实结构写死，避免渲染器侧把字符串当任意值乱存。像 `theme.activeId`、`theme.userThemes`、`acp.cachedModes`、`assistant.weixin.agent` 这类字段，都是通过它统一约束的。

## 运行流程

启动时，主进程先在 `initStorage.ts` 里构建本地 JSON 存储文件，再把 `ConfigStorage.interceptor(configFile)` 和 `EnvStorage.interceptor(envFile)` 挂上去。之后迁移任务会通过 `runBackendMigrations.ts` 把旧配置导入后端，必要时还会用 `resolveImageGenerationMcpEnv` 生成图片生成 MCP 的环境变量。

渲染器启动时，`renderer/main.tsx` 会先调用 `configService.initialize()`。它通过 HTTP 拉取 `/api/settings/client`，把结果装进内存缓存；如果发现旧主题字段，还会做一次 `migrateThemeConfig`。随后 `renderer/services/i18n/index.ts` 会等待 `configService.whenReady()`，用配置里的 `language` 作为唯一真值，再同步到 `i18next` 和 `localStorage`。

配置写回也很直接：`configService.set()` 和 `remove()` 都会先更新本地缓存并通知订阅者，再通过 `PUT /api/settings/client` 持久化。`setLocal()` 则只改内存，不触发远端写入，适合乐观更新或短暂 UI 状态。

## 上下游依赖

上游依赖主要来自三处：主进程的存储初始化和迁移流程、渲染器的页面与 hooks、以及 i18n 启动链路。比如 `process/utils/runBackendMigrations.ts` 调用 `migrateConfigStorage`、`migrateLegacyMcpConfigToDb`、`resolveImageGenerationMcpEnv`；`process/utils/utils.ts` 依赖 `getEnvAwareName` 做开发环境目录隔离；`common/adapter/browser.ts` 依赖 `WEBUI_DEFAULT_PORT` 选择 WebUI 的默认连接端口。

下游则是大量功能页和状态钩子。主题、语言、系统设置、MCP catalog、speech 输入、各类聊天渠道配置页、技能市场、宠物设置、团队默认模型选择等，都直接读取或写入这里的配置。也就是说，这个目录不是“基础工具集合”，而是全局状态的公共入口。

## 修改时最容易踩的坑

第一，`configKeys.ts`、`storage.ts`、`configService.ts` 三者必须同步。只改类型不改映射，或者只加存储字段不加服务层键，都会造成运行时与类型系统脱节。  
第二，`configService.setLocal()` 不会落盘，适合临时 UI 状态，不适合真正要持久化的设置。  
第三，语言和主题都有迁移逻辑，改动时要保证幂等，否则用户重复启动会被反复覆盖。  
第四，`configMigration.ts` 明确避免覆盖后端已存在的键，新增迁移时要延续这个策略。  
第五，WebUI 与 Electron 的 base URL、端口和 `window.__backendPort` 逻辑要保持一致，否则浏览器模式会连错服务。  
第六，`i18n-config.json`、`SUPPORTED_LANGUAGES` 和配置里的 `language` 必须同步，否则会出现“配置写入了但界面无法切换”的问题。

## 推荐阅读顺序

建议先读 `storage.ts`，建立这个目录到底存哪些键的全景。  
然后读 `configKeys.ts` 和 `configService.ts`，理解类型约束和运行时读写模型。  
接着看 `configMigration.ts`，把旧配置如何迁移到新后端串起来。  
再看 `i18n.ts`、`appEnv.ts`、`fontSizes.ts`、`constants.ts`，这些是高频基础能力。  
最后补 `imageGenerationMcpEnv.ts` 和 `storageKeys.ts`，把专项配置和浏览器本地键收口。
