# 目录：packages/database/src

## 它负责什么

`packages/database/src` 是 LobeHub 仓库中的数据库基础包源码目录，对外包名是 `@lobechat/database`。它不是页面层、也不是业务路由层，而是把数据库相关能力集中封装成可复用的 workspace package，供主应用的 `src/server/services`、TRPC router、后台任务、导入导出等服务端代码调用。

从 `packages/database/package.json` 看，它的主要职责包括：

- 提供数据库表结构定义：通过 `./schemas` 导出 `packages/database/src/schemas/index.ts`。
- 提供数据库连接与适配入口：主入口 `src/index.ts` 导出 `./core/db-adaptor`。
- 提供领域级数据访问封装：目录中有大量 `models/` 与 `repositories/`。
- 提供数据库相关工具：例如 `utils/idGenerator`、`utils/genWhere`、`utils/bm25` 等。
- 支撑测试数据库：`core/getTestDB.ts` 与 package 中的 `@electric-sql/pglite` 依赖说明它可以为测试构造本地轻量数据库环境。

根据 `peerDependencies`，这个包围绕 `drizzle-orm`、`drizzle-zod`、`pg`、`zod`、`nanoid` 工作；根据当前片段推断，它是 PostgreSQL + Drizzle ORM 的集中封装层。

## 关键组成

`core/` 是数据库连接和运行环境适配层。当前入口 `src/index.ts` 直接导出 `core/db-adaptor`，`src/server/index.ts` 又把 `getServerDB`、`serverDB` 从这里转出，说明 `db-adaptor.ts` 是服务端获得数据库实例的核心入口。`core/web-server.ts`、`core/getTestDB.ts` 则分别暗示 Web/Server 场景与测试场景的 DB 初始化支持。

`schemas/` 是表结构层。`schemas/index.ts` 聚合导出 `agent`、`message`、`session`、`topic`、`user`、`file`、`rag`、`rbac`、`aiInfra`、`generation`、`betterAuth`、`nextauth`、`oidc` 等模块。它的职责通常是定义 Drizzle table、relations、insert/select 类型、索引和外键关系。这里的 `relations.ts` 单独被导出，说明关系映射是 schema 层的重要组成部分。

`models/` 是领域模型层。目录中有 `agent.ts`、`message.ts`、`session.ts`、`topic.ts`、`user.ts`、`file.ts`、`knowledgeBase.ts`、`document.ts`、`generation.ts`、`aiProvider.ts` 等大量文件。根据当前片段推断，每个 model 大概率围绕一个业务实体封装 CRUD、查询组合、分页、状态更新等数据库操作，让上层服务不直接拼 Drizzle 查询。

`repositories/` 是更高阶的数据仓库层。它包含 `compression`、`dataExporter`、`dataImporter`、`home`、`knowledge`、`search`、`topicImporter`、`aiInfra`、`userMemory` 等目录。相比单实体 `models/`，repository 更可能负责跨表聚合、导入导出、首页数据聚合、搜索、知识库等复杂用例。主入口 `src/index.ts` 只直接导出了 `repositories/compression`，说明压缩相关能力被当作公共 API 暴露给包外调用。

`types/` 与 `type.ts` 是类型出口。`src/index.ts` 导出 `./type`，而目录下还有 `types/chatGroup.ts`、`types/generation.ts`，说明数据库包不仅给运行时代码使用，也为上层提供领域数据结构类型。

`utils/` 是数据库辅助工具。可见文件包括 `columns.ts`、`genWhere.ts`、`idGenerator.ts`、`bm25.ts` 及其测试。`genWhere` 通常用于生成条件查询，`bm25` 指向搜索排序或相关度计算，`idGenerator` 则是统一 ID 生成策略。

## 上下游关系

上游输入主要来自三类地方：

- 主应用服务端：典型链路是 `src/server/routers` 或 API route 接收请求，再进入 `src/server/services`，最终调用 `@lobechat/database` 中的 model/repository。
- 业务配置与类型包：`package.json` 依赖 `@lobechat/types`、`@lobechat/const`、`@lobechat/business-const`、`@lobechat/business-model-bank` 等，说明数据库层会复用全局业务类型、常量和模型定义。
- ORM 与数据库驱动：`drizzle-orm`、`pg`、`drizzle-zod`、`zod` 为 schema、查询和校验提供基础能力。

下游输出主要是：

- PostgreSQL 数据库读写。
- 对主应用暴露的 `serverDB` / `getServerDB`。
- 对上层业务暴露的 model、repository、schema、类型和工具函数。
- 对测试暴露的测试数据库构造能力，package exports 中还提供了 `./test-utils`。

这个包的边界比较清晰：它不负责 HTTP、TRPC、React 状态，也不负责 UI 展示；它负责把“数据如何存、如何查、如何组合”封装起来。

## 运行/调用流程

一个常见调用流程可以理解为：

1. 前端页面触发某个操作，例如发送消息、创建助手、上传文件、查询知识库。
2. 客户端 service 调用 TRPC 或后端 API。
3. 后端 router 进入 `src/server/services` 中的业务服务。
4. 业务服务通过 `@lobechat/database` 获得 `serverDB` 或调用某个 model/repository。
5. model/repository 使用 `schemas/` 中定义的表结构和 Drizzle ORM 构造 SQL。
6. 数据写入或读取 PostgreSQL。
7. 查询结果被转换为业务需要的类型，返回给 service，再回到 router 和前端。

如果是跨实体场景，例如首页聚合、知识库搜索、数据导入导出，调用点更可能进入 `repositories/`。如果是单实体操作，例如 message、topic、session、user 的增删改查，则更可能落在 `models/`。

测试流程则可能使用 `core/getTestDB.ts` 和 `tests/test-utils.ts` 初始化隔离数据库，再运行 `models/__tests__` 或 `utils/*.test.ts`。

## 小白阅读顺序

建议先从入口看边界：

1. `packages/database/package.json`：先确认这个包对外暴露什么。当前 exports 只有 `"."`、`"./schemas"`、`"./test-utils"`，说明外部应优先通过这些入口使用。
2. `packages/database/src/index.ts`：看主入口。它导出 `db-adaptor`、`compression`、`type`、`idGenerator`，能快速判断公共 API 面向哪些能力。
3. `packages/database/src/server/index.ts`：看服务端如何拿数据库实例。这里导出 `getServerDB` 和 `serverDB`。
4. `packages/database/src/schemas/index.ts`：建立数据表地图。先记住核心域：`user`、`session`、`message`、`topic`、`agent`、`file`、`rag`、`generation`。
5. `packages/database/src/models/`：按业务对象阅读。新手可以先看 `user.ts`、`session.ts`、`message.ts`、`topic.ts` 这类核心实体，再看更复杂的 `knowledgeBase.ts`、`generation.ts`。
6. `packages/database/src/repositories/`：最后看跨表用例，例如 `search`、`knowledge`、`dataExporter`、`dataImporter`。这些通常更依赖你已经理解 schema 和 model。

阅读时要把 `schemas`、`models`、`repositories` 三层分开：schema 是“表长什么样”，model 是“单个领域对象怎么读写”，repository 是“一个业务场景怎么组合多张表”。

## 常见误区

第一个误区是把 `models/` 当成前端 model。这里的 model 是数据库访问模型，不是 React 组件状态，也不是 Zustand store。它通常运行在服务端或测试环境中。

第二个误区是绕过 `models/` 和 `repositories/` 直接在业务服务里拼复杂 SQL。这样会让查询逻辑散落到各处，后续 schema 变化时很难维护。根据当前结构，仓库倾向于把数据访问集中放在 `packages/database/src`。

第三个误区是混淆 `schemas/` 和 `types/`。`schemas/` 更接近数据库表定义和 ORM 映射，`types/` / `type.ts` 更接近 TypeScript 层面对外复用的数据类型。

第四个误区是认为 `repositories/` 和 `models/` 没区别。根据目录命名和文件分布推断，`models/` 更偏实体级操作，`repositories/` 更偏业务场景聚合，例如搜索、知识库、导入导出、压缩等。

第五个误区是只看 `src/index.ts` 就以为这个包只暴露了少量能力。实际上 package 还通过 `./schemas` 暴露 schema 聚合入口，而主应用内部也可能通过 workspace alias 或具体路径引用更深层模块。判断真实调用关系时，需要再查调用方。

第六个误区是忽视测试环境。这个包有 `getTestDB.ts`、`models/__tests__`、`utils/*.test.ts`，并且 package scripts 区分 `test:client-db` 和 `test:server-db`。数据库层改动通常不只要看类型通过，还要关注 server DB 测试与查询行为。
