# 文件：packages/desktop/src/process/utils/initStorage.ts

## 一句话定位

`packages/desktop/src/process/utils/initStorage.ts` 是主进程启动阶段的本地持久化初始化入口，负责确定 AionUi 的配置目录、数据目录与若干业务子目录，并把旧版文件式存储、环境配置、会话配置以及旧数据库迁移串起来，为后续主进程服务提供统一的存储访问点。

## 它暴露/定义了什么

从当前片段可以确认，它定义了默认导出的 `initStorage`，以及一组会被其他主进程模块复用的存储相关对象或路径函数。调用关系搜索显示，外部会使用 `ProcessConfig`、`ProcessEnv`、`getSystemDir`、`getAssistantsDir`、`getBuiltinMcpScriptPath` 等导出项；这些导出项在当前读取片段之后继续定义，具体实现细节根据当前片段推断主要围绕 `ConfigStorage`、`EnvStorage` 和本文件构造出的 JSON 文件存储适配器展开。

文件内部还定义了 `STORAGE_PATH`，集中声明旧文件存储名称，例如 `aionui-config.txt`、`aionui-chat-message.txt`、`aionui-chat.txt`、`.aionui-env`、`assistants`、`skills`、`cron-skills`。`LEGACY_BUILTIN_SKILLS_DIR` 用于启动时清理旧版 builtin skills 缓存目录。

## 谁调用它

最直接的调用者是 `packages/desktop/src/process/index.ts`：主进程启动时导入 `initStorage` 并 `await initStorage()`，随后记录 `mark('initStorage')`。这说明它属于应用启动链路中的早期基础设施初始化，必须在依赖配置、环境变量、用户目录、数据库迁移的服务之前完成。

其他模块不一定调用默认函数，但会依赖本文件导出的运行期配置能力，例如 `packages/desktop/src/process/utils/zoom.ts`、`packages/desktop/src/process/utils/closeToTraySetting.ts`、`packages/desktop/src/process/utils/webuiConfig.ts`、`packages/desktop/src/process/utils/migrateAssistants.ts`、`packages/desktop/src/process/utils/runBackendMigrations.ts`、`packages/desktop/src/process/bridge/applicationBridgeCore.ts`、`packages/desktop/src/process/services/i18n/index.ts`、`packages/desktop/src/process/bridge/systemSettingsBridge.ts`、`packages/desktop/src/process/bridge/applicationBridge.ts`、`packages/desktop/src/process/bridge/notificationBridge.ts` 等。由此可见，它既是启动初始化入口，也是主进程配置读取的共享模块。

## 它调用谁

它依赖 Node 文件系统能力：`fs`、`fs/promises`、`path`，用于创建目录、读写文件、复制迁移、清理旧目录。它调用 `./utils` 中的 `copyDirectoryRecursively`、`ensureDirectory`、`getConfigPath`、`getDataPath`、`getTempPath`、`hasElectronAppPath`、`verifyDirectoryFiles`，这些函数承担平台相关路径解析和文件夹操作。

它还依赖 `@/common/config/storage` 中的 `ConfigStorage`、`EnvStorage` 及相关类型，把底层文件读写包装成业务配置存储；依赖 `@/common/platform` 的 `getPlatformServices` 和 `@/common/adapter/ipcBridge` 的 `application`，用于与平台服务和 IPC 桥接层协作；依赖 `@process/services/database/runLegacyDatabaseMigrations` 的 `runLegacyDatabaseMigrations`，把旧数据迁移到当前数据库结构；并引用 `BUILTIN_IMAGE_GEN_ID` 处理内置 MCP 或内置能力相关路径。

## 核心流程

启动时，文件首先根据 `getConfigPath()`、`getTempPath()` 等路径函数确定新旧存储位置。`migrateLegacyData()` 会检查旧版 temp 目录是否存在、 新配置目录是否为空；只有在“旧目录存在且新目录为空”的条件下才复制数据，复制后通过 `verifyDirectoryFiles()` 校验，校验通过且源目标不是同一路径时才删除旧目录。这个条件设计降低了覆盖新配置的风险。

之后，本文件通过 `JsonFileBuilder()` 为配置、环境、聊天记录等文件提供统一的读写抽象。旧格式不是裸 JSON，而是 `base64(encodeURIComponent(JSON))`，所以读写都保留编码兼容逻辑。读取采用首次访问时同步加载到内存；写入时先更新内存缓存，再通过 promise 链串行落盘，避免并发写入导致文件内容损坏。

根据当前片段推断，`initStorage()` 的后续流程会创建必要目录，例如 config/data、assistants、skills、cron-skills、系统目录或内置脚本目录；初始化 `ProcessConfig`、`ProcessEnv` 等全局存储对象；执行旧数据库迁移；并清理或迁移历史目录。依据是文件已导入 `ensureDirectory`、`getDataPath`、`runLegacyDatabaseMigrations`，且外部模块使用了多个路径 getter 与配置对象。

## 关键函数的高层作用

`migrateLegacyData()` 负责旧版本地文件位置迁移。它的重点不是转换格式，而是把旧 temp 目录中的文件和子目录复制到新的 userData/config 目录，并在校验成功后清理旧目录。它对异常采取记录日志并返回 `false` 的策略，避免迁移失败直接阻断应用启动。

`JsonFileBuilder<S>()` 是本文件最重要的底层抽象。它把单个文件包装成一个内存 JSON store，提供 `toJson`、`setJson`、`get`、`set`、`remove`、`clear`、`getSync`、`update`、`backup` 等方法。它的关键设计是“懒加载缓存 + 串行写入 + 旧编码格式兼容”。这让上层 `ConfigStorage`、`EnvStorage` 可以像操作对象一样操作磁盘文件，同时保持旧版本数据可读。

`WriteFile()` 只是安全写文件辅助函数，写入前确保父目录存在，防止首次写入时报 `ENOENT`。

`mkdirSync()` 是对 Node `mkdirSync` 的轻量包装，统一使用 `{ recursive: true }`。

`initStorage()` 是启动编排函数。根据当前片段和调用关系推断，它主要负责串联目录创建、旧数据迁移、配置对象初始化和数据库迁移，而不是承载具体业务规则。

## 修改风险

第一类风险是兼容性风险。`JsonFileBuilder()` 明确保留 `base64(encodeURIComponent(JSON))` 的磁盘格式，随意改成明文 JSON 或其他编码会导致用户已有配置、聊天记录、环境配置无法读取。即使要迁移格式，也应做双读兼容和备份策略。

第二类风险是启动顺序风险。`packages/desktop/src/process/index.ts` 在主进程启动早期等待 `initStorage()`，而多个 bridge、service、utils 模块直接依赖 `ProcessConfig`、`ProcessEnv` 或路径 getter。若把初始化改成异步懒加载，可能引入模块加载时拿到未初始化配置的问题。`configureChromium.ts` 和 `common/platform/index.ts` 的注释也提示过模块加载顺序与 `initStorage` chunk 有耦合。

第三类风险是数据覆盖风险。`migrateLegacyData()` 只有在新目录为空时才迁移，避免旧数据覆盖新数据。调整迁移条件、删除校验、或在失败时继续删除旧目录，都可能造成用户数据丢失。

第四类风险是并发写风险。当前写入通过 `writeChain` 串行化，并且失败不会阻断后续写入链。若改为直接并发 `writeFile`，配置文件和聊天文件在高频更新时可能出现覆盖、截断或顺序错乱。

第五类风险是路径边界风险。本文件处在主进程 `packages/desktop/src/process/`，可以使用 Node 文件系统 API，但它导出的能力会被 bridge 和服务层广泛使用。修改 `getSystemDir`、`getAssistantsDir`、`getBuiltinMcpScriptPath` 等路径语义时，需要同步检查后端迁移、助手迁移、WebUI 配置、通知、i18n、系统设置等调用方。
