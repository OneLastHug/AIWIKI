# 子系统：packages/desktop/src/process/services/database

## 解决什么问题

`packages/desktop/src/process/services/database` 从路径和项目约定看，位于 Electron 主进程侧的 `services` 层，目标职责应是为桌面端提供本地数据库能力：管理数据库连接、初始化存储目录、执行迁移或建表、封装数据访问入口，并向更上层业务服务暴露稳定的持久化接口。

需要先说明证据边界：当前可读环境中没有成功暴露目标目录及其邻近 `packages/desktop/src/process` 源码，因此以下内容只能根据仓库给出的架构约束、目标路径命名和常见 Electron 主进程分层进行学习性归纳。涉及具体类名、函数名、表结构和调用链时，应以实际源码为准；本文不会把推断写成确定事实。

这个目录解决的核心问题不是“业务怎么使用某张表”，而是“主进程如何安全、统一地持有本地数据”。在 Electron 应用中，数据库通常不能直接放到 renderer 侧访问，因为 renderer 侧按项目约束不能使用 Node.js API，也不应该直接接触文件系统、SQLite 驱动或进程级资源。因此 database 子系统一般承担隔离层角色：把底层数据库驱动、文件路径、事务、迁移、错误处理收束在主进程内部，再通过服务层或 IPC 间接服务 UI。

## 相关目录和文件

目标目录是 `packages/desktop/src/process/services/database`。它的上级 `packages/desktop/src/process/services` 应该承载主进程业务服务，例如会话、配置、文件、知识库、模型或同步相关服务；database 是这些服务共同依赖的基础设施之一。

与它关系最密切的邻近区域通常包括：

`packages/desktop/src/process`：主进程入口与生命周期管理所在区域，负责在应用启动时注册服务、处理退出清理，并保证没有 DOM API 混入。

`packages/desktop/src/preload`：主进程能力向 renderer 暴露的桥接层。database 不应直接被 renderer 引用，而应通过 preload 定义的安全 API 或 IPC 通道间接访问。

`packages/desktop/src/renderer`：前端界面和状态管理所在区域。它只消费经过 preload 暴露的接口或业务 API，不直接 import database 目录。

`packages/desktop/src/common`：如果存在数据库相关的共享类型、枚举、配置键或 i18n 配置，通常会放在 common 层。需要注意 common 只能放真正跨进程安全共享的内容，不能包含 Node.js 驱动实例。

根据当前片段推断，database 目录内部可能包含类似 `index.ts`、`client.ts`、`schema.ts`、`migrations`、`repositories`、`types.ts` 这样的文件或子目录。但这只是基于目录职责的合理猜测，不能替代实际文件清单。

## 核心对象

database 子系统的第一个核心对象通常是“数据库连接或客户端”。它负责打开本地数据库文件、设置连接参数、控制单例生命周期，并为上层提供查询执行能力。如果项目使用 SQLite，这里可能会封装 `better-sqlite3`、`sqlite`、`drizzle` 或类似库；如果使用嵌入式 KV，则可能封装 LevelDB、LokiJS 或自研存储。

第二类核心对象是“schema 与 migration”。schema 描述表、字段、索引和约束；migration 负责应用升级时把用户本地旧数据迁移到新结构。桌面端数据保存在用户机器上，无法像服务端一样统一重建，因此迁移代码的兼容性非常重要。

第三类核心对象是“repository 或 DAO”。它把底层 SQL、事务和数据映射封装成面向业务的操作，例如创建记录、按 workspace 查询、更新状态、软删除、分页读取等。业务服务应尽量依赖 repository，而不是散落地拼接 SQL。

第四类核心对象是“初始化与关闭流程”。主进程启动时需要保证数据库目录存在、连接可用、迁移完成；应用退出或窗口关闭时要释放资源，避免文件锁、未提交事务或损坏数据库。

## 运行流程

典型运行流程可以理解为五步。

第一步，主进程启动。`packages/desktop/src/process` 的入口或服务容器加载 database 子系统，准备本地数据目录。数据目录一般来自 Electron 的 app userData 路径，而不是仓库目录。

第二步，创建数据库连接。database 子系统根据环境、配置或用户目录计算数据库文件位置，实例化底层客户端，并设置必要的 pragma、日志、加密或兼容选项。根据当前片段推断，如果该项目关注桌面本地数据安全，这里也可能处理密钥、备份或恢复策略。

第三步，执行 schema 初始化和 migration。新安装用户会创建完整结构；老用户会按版本顺序执行增量迁移。这个阶段应尽量在业务服务真正读写前完成，否则上层可能拿到半初始化状态。

第四步，业务服务调用 database。上层服务通过 repository 或数据库服务方法完成读写，再把结果转换成 IPC 可序列化的数据返回给 preload 和 renderer。renderer 不需要知道数据库文件、表名或 SQL 细节。

第五步，应用关闭。主进程在退出阶段 flush 待写入数据、关闭连接、释放锁。若存在后台任务或同步任务，还需要和 database 的事务边界协调，避免关闭时写入中断。

## 上下游依赖

上游调用方主要是 `packages/desktop/src/process/services` 中的业务服务，以及注册 IPC handler 的主进程模块。它们把用户行为、窗口事件或后台任务转换成持久化读写请求。

下游依赖主要是 Node.js 文件系统能力、Electron app 路径能力、数据库驱动包、迁移工具和日志系统。由于该目录在 process 层，它可以使用 Node.js API，但必须避免引入 renderer 专属内容、浏览器 DOM 对象和 React 组件。

横向依赖包括共享类型与配置。若数据库读写结果会跨 IPC 返回 renderer，返回类型应尽量定义在 `packages/desktop/src/common` 或由 preload API 明确约束，避免主进程内部类型泄漏到 UI 层后形成隐式耦合。

## 修改时最容易踩的坑

最常见的坑是跨进程边界混乱。database 代码属于主进程，不能被 `packages/desktop/src/renderer` 直接 import；renderer 想读写数据，应经过 preload 和 IPC。

第二个坑是迁移不可逆或不兼容。桌面端用户数据分散在本机，发布后很难统一修复。新增字段、改表名、删除列、重建索引时，都要考虑已有数据、空值、旧版本升级路径和失败重试。

第三个坑是把业务规则塞进底层数据库层。database 应处理持久化和基础一致性，复杂业务流程更适合放在上层 service。否则数据库层会逐渐变成难测试、难复用的业务黑箱。

第四个坑是并发与事务边界不清。Electron 主进程可能同时响应多个 IPC 请求；如果多个写操作共享同一连接，需要明确串行化、事务范围和错误回滚策略。

第五个坑是路径和环境假设。数据库文件应放在应用数据目录，不应依赖当前工作目录。测试、开发、生产、打包后路径都可能不同。

第六个坑是 IPC 数据不可序列化。数据库驱动返回的特殊对象、Date、Buffer、BigInt 或错误实例直接穿过 IPC 时可能出问题，应在 service 边界转换成稳定的普通对象。

## 推荐阅读顺序

建议先读 `packages/desktop/src/process` 的主进程入口，确认服务注册和应用启动生命周期。然后读 `packages/desktop/src/process/services/database` 的入口文件，理解它暴露给上层的公共 API。

接着阅读数据库初始化相关文件，重点看数据库文件路径、连接创建、迁移执行和关闭逻辑。随后再读 schema、migration 或 repository，建立“有哪些核心数据模型、谁负责读写”的整体图景。

之后阅读调用 database 的上层服务，尤其是 `packages/desktop/src/process/services` 中直接 import database 的模块。最后再看 `packages/desktop/src/preload` 和 `packages/desktop/src/renderer` 中对应功能的调用路径，确认数据如何从 UI 请求进入主进程，又如何被序列化返回。
