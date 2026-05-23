# 目录：packages/database

## 它负责什么

根据当前片段推断，`packages/database` 是整个仓库的数据库基础层，负责把 schema、类型、测试数据库、迁移脚本和一组面向业务的 repository 统一封装起来，供上层服务和应用直接使用。它不是单纯的“表定义目录”，而是把“怎么连库、怎么迁移、怎么读写、怎么测”都放在一起的基础包。

从 `package.json` 看，这个包对外主要暴露三个入口：`src/index.ts`、`src/schemas/index.ts`、`tests/test-utils.ts`。这说明它既服务运行时，也服务测试；而 `src/type.ts` 又把 schema 绑定成统一的 `LobeChatDatabase` 类型，说明类型安全是这个包的重要职责。

## 直接子目录地图

`packages/database` 下面最重要的直接子目录是这几个：

- `src/`：主源码区，承载 schema、模型、仓储层、数据库适配器和工具方法。
- `migrations/`：数据库迁移 SQL，`getTestDB()` 会直接读取这里的迁移文件并执行。
- `tests/`：测试环境辅助文件，主要给数据库测试和公共测试工具用。
- 还有根部的 `package.json`、`vitest.config.mts`、`vitest.config.server.mts`，它们不算目录，但决定了这个包如何被消费和测试。

如果继续往 `src/` 里看，直接子目录可以概括成：

- `core/`：数据库实例获取、测试库初始化等连接层逻辑。
- `schemas/`：Drizzle schema 聚合层，负责统一导出所有表定义。
- `models/`：按业务域拆开的数据模型层，通常是面向实体和查询组合的核心业务代码。
- `repositories/`：更高一级的数据访问封装，通常服务于导入、导出、搜索、AI 基础设施等场景。
- `server/`：服务端侧的数据库导出与适配入口。
- `types/`、`type.ts`、`utils/`：类型补充和通用工具。

## 关键入口

最关键的入口有四个：

- `src/index.ts`：包级主入口，导出 `core/db-adaptor`、`repositories/compression`、`type`、`utils/idGenerator`。这说明外部最常通过它拿数据库句柄、压缩相关仓储和通用类型/工具。
- `src/schemas/index.ts`：schema 总入口，把 `agent`、`message`、`session`、`user`、`topic`、`generation`、`ragEvals`、`userMemories` 等模块统一汇总。
- `src/type.ts`：定义 `LobeChatDatabaseSchema`、`LobeChatDatabase` 和 `Transaction`，是整个包里最核心的类型绑定点。
- `src/core/db-adaptor.ts` 与 `src/core/web-server.ts`：前者负责懒加载服务器数据库实例，后者负责在测试或本地环境里真正构造数据库连接并跑迁移。

`src/server/index.ts` 也很重要，但它更像一个薄转发层，把 `core/db-adaptor` 暴露给 server 侧消费。

## 主流程位置

如果只看“数据从哪里进来、怎么落到库、再怎么被业务层取走”，主流程基本落在这几段：

1. `migrations/` 提供结构演进脚本。
2. `src/core/web-server.ts` 读取 `src/schemas` 和迁移目录，构造测试数据库或服务端数据库。
3. `src/core/db-adaptor.ts` 对外提供 `getServerDB()` 和 `serverDB`，负责缓存和懒加载。
4. `src/models/` 处理按业务域拆分的实体逻辑，是更接近领域的读写入口。
5. `src/repositories/` 在模型之上做更偏任务型的封装，比如 `dataImporter`、`dataExporter`、`search`、`aiInfra`、`topicImporter`、`compression` 等。
6. `src/index.ts` 再把这些关键能力汇总成包级 API。

测试主流程则是另一条线：`packages/database/tests/setup-db.ts` 和 `src/core/getTestDB.ts` 会把 PGlite 或 node-postgres 的测试库准备好，再配合 `vitest.config.server.mts` 跑服务端测试。根据当前片段推断，这个包对测试环境做了双模式支持，原因是 `getTestDB()` 里明确区分了 `TEST_SERVER_DB=1` 的 node-postgres 路径和默认的 PGlite 路径。

## 推荐阅读顺序

建议按下面顺序看，能最快建立地图感：

1. `package.json`：先看导出面和测试方式。
2. `src/index.ts`：确认包级 API。
3. `src/type.ts`：理解数据库类型是怎么绑定 schema 的。
4. `src/schemas/index.ts`：看有哪些 schema 家族。
5. `src/core/web-server.ts`、`src/core/db-adaptor.ts`：看数据库实例如何创建、缓存、迁移。
6. `src/models/` 与 `src/repositories/` 的各自 `index.ts`：按业务域理解数据访问层的分工。
7. `migrations/`：最后再看结构演进历史。

如果目标是做测试或排障，可以优先看 `tests/test-utils.ts`、`tests/setup-db.ts` 和 `src/core/getTestDB.ts`。

## 常见误区

- 把 `src/schemas` 当成全部数据库逻辑。它只负责结构定义和聚合，不等于完整的数据访问层。
- 只看 `src/models` 或只看 `src/repositories`。这个包是分层的，schema、model、repository、core 之间各有边界。
- 忽略 `migrations/`。很多真实问题不在代码里，而在迁移顺序、迁移兼容性或测试库初始化逻辑里。
- 误以为 `src/index.ts` 导出了全部能力。实际上它只暴露了少量主入口，很多能力要从具体 `models` 或 `repositories` 目录进入。
- 看测试时只盯着单元测试，不看 `src/core/getTestDB.ts`。这里决定了测试库模式，尤其是 PGlite 和 node-postgres 的差异。
- 以为这个目录是纯后端私有实现。实际上它是多个上层模块共享的基础包，`src/schemas/index.ts` 和 `src/type.ts` 都是明显的公共边界。
