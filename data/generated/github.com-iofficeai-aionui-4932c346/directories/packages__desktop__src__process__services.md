# 子系统：packages/desktop/src/process/services

## 解决什么问题

`packages/desktop/src/process/services` 是桌面端 **Main Process 服务层**。它负责承载那些不属于 UI、但又需要被多个主进程模块复用的能力：比如国际化初始化、自动更新状态与诊断、SQLite 数据库迁移与驱动封装。根据当前片段推断，这一层的定位是“进程级单例服务”，让 `process` 下的启动逻辑、桥接层、工具模块都能通过统一入口拿到稳定能力，而不是各自重复实现。

这也解释了它为什么放在 `process` 目录里，而不是 `renderer`：这里处理的是 Electron 主进程中的长期运行逻辑，通常会被 `process/index.ts` 在启动时拉起，并被 `process/bridge/*`、`process/utils/*` 间接消费。

## 相关目录和文件

- `packages/desktop/src/process/services/i18n/index.ts`：主进程国际化入口，负责把语言资源装配进来，并对外提供语言切换能力。
- `packages/desktop/src/process/services/autoUpdaterService.ts`：自动更新服务核心，供更新桥接层读取状态或触发更新相关动作。
- `packages/desktop/src/process/services/autoUpdateDiagnostics.ts`：自动更新诊断信息，通常用于排查更新链路问题。
- `packages/desktop/src/process/services/database/schema.ts`：数据库结构定义。
- `packages/desktop/src/process/services/database/migrations.ts`：迁移执行逻辑。
- `packages/desktop/src/process/services/database/runLegacyDatabaseMigrations.ts`：旧数据库迁移入口，负责兼容历史数据。
- `packages/desktop/src/process/services/database/drivers/ISqliteDriver.ts`：SQLite 驱动接口。
- `packages/desktop/src/process/services/database/drivers/BetterSqlite3Driver.ts`：具体 SQLite 驱动实现。
- `packages/desktop/src/process/services/database/IConversationRepository.ts`：会话仓储接口，说明数据库层还承载业务持久化抽象。
- 相邻依赖目录：`packages/desktop/src/process/index.ts`、`packages/desktop/src/process/bridge/`、`packages/desktop/src/process/utils/`、`packages/desktop/src/renderer/services/i18n/`。

## 核心对象

- `i18n`：主进程国际化实例。`process/index.ts` 会显式初始化它，`tray.ts`、`petManager.ts`、`petConfirmManager.ts`、`systemSettingsBridge.ts` 等模块都依赖它。
- `changeLanguage`：语言切换的核心动作，既被主进程桥接层调用，也会和渲染层语言切换保持一致。
- `autoUpdaterService`：更新服务单例，提供更新状态管理，`process/bridge/updateBridge.ts` 直接依赖它。
- `AutoUpdateStatus`：更新状态类型，说明更新服务对外暴露的是明确的状态机，而不是松散对象。
- `ISqliteDriver` / `BetterSqlite3Driver`：数据库驱动抽象与实现，体现出数据库访问被做了适配层。
- `schema` / `migrations` / `runLegacyDatabaseMigrations`：分别对应结构定义、迁移集合、历史迁移执行入口，是数据库初始化链路的核心。
- `IConversationRepository`：会话数据访问的接口边界，提示这里不只是“存储工具”，而是承接业务持久化契约。

## 运行流程

1. 主进程启动时，`packages/desktop/src/process/index.ts` 先导入 `./services/i18n`，把语言能力提前初始化。
2. 启动存储相关逻辑时，`packages/desktop/src/process/utils/initStorage.ts` 会调用 `runLegacyDatabaseMigrations`，把旧数据库逐步升级到当前 schema。
3. 数据库迁移时，`runLegacyDatabaseMigrations.ts` 通过 `ISqliteDriver` 和 `migrations.ts` 协作，必要时动态加载 `BetterSqlite3Driver`，说明驱动可能是按需、延迟加载的。
4. 更新相关流程由 `process/bridge/updateBridge.ts` 接入 `autoUpdaterService`，并缓存 `i18n`，用于输出状态、提示和诊断信息。
5. 其他主进程功能模块，如托盘、宠物交互、系统设置桥接，也会复用这里的服务，而不是自行持有一套实现。

## 上下游依赖

上游主要是主进程启动链和各类桥接层：`process/index.ts`、`process/bridge/updateBridge.ts`、`process/bridge/systemSettingsBridge.ts`、`process/utils/initStorage.ts`、`process/utils/tray.ts`、`process/pet/*`。这些模块把“需要复用的能力”下沉到 services 层。

下游主要是基础设施和共享资源：SQLite 原生驱动、迁移脚本、数据库 schema、以及渲染层共享的语言包。特别是 `services/i18n/index.ts` 直接导入 `@renderer/services/i18n/locales/*`，这说明主进程和渲染进程在语言资源上是共享的，但初始化逻辑仍分属两个进程域。

## 修改时最容易踩的坑

- 误跨进程边界：`process/services` 只能放主进程逻辑，不能混入 DOM 相关代码。
- 破坏语言一致性：主进程的 `i18n` 和渲染层语言资源是联动的，改 key、改 locale 文件时要同步检查两侧。
- 迁移兼容性问题：`runLegacyDatabaseMigrations` 处理的是历史数据，随便改 schema 或 migration 顺序很容易把老用户数据弄坏。
- 破坏单例时序：`process/index.ts` 在启动阶段就初始化 i18n，新增服务如果依赖它，必须考虑加载顺序。
- 更新服务副作用：`autoUpdaterService` 被桥接层直接消费，改状态字段或返回结构会向上传播到 UI 和通知逻辑。
- 驱动实现耦合：`ISqliteDriver` 和 `BetterSqlite3Driver` 之间是契约关系，扩展功能时要先看接口，再看实现。

## 推荐阅读顺序

1. `packages/desktop/src/process/index.ts`
2. `packages/desktop/src/process/services/i18n/index.ts`
3. `packages/desktop/src/process/services/database/schema.ts`
4. `packages/desktop/src/process/services/database/migrations.ts`
5. `packages/desktop/src/process/services/database/runLegacyDatabaseMigrations.ts`
6. `packages/desktop/src/process/services/autoUpdaterService.ts`
7. `packages/desktop/src/process/bridge/updateBridge.ts`
8. `packages/desktop/src/process/utils/initStorage.ts`
9. `packages/desktop/src/process/utils/tray.ts` 与 `packages/desktop/src/process/pet/*`

这条顺序先看启动入口，再看国际化和数据库，再看更新与桥接，能比较快建立这个子系统在主进程里的完整位置感。
