# 目录：packages/database/src

## 它负责什么

`packages/database/src` 是整个数据库层的实现核心，职责不是单纯放 SQL 表结构，而是把“连接数据库、定义 schema、封装模型、组织仓库方法、对外提供服务端入口”这一整套能力放在一起。根据当前片段推断，这里是 `@lobechat/database` 包的主要源码区，供上层的 server、router、服务层直接调用。

它的定位可以概括成三层：

1. 连接层：负责创建 Drizzle 数据库实例，并按环境选择 Neon 或 `pg`。
2. 数据结构层：通过 `schemas` 统一导出所有表、关系和相关 schema。
3. 业务访问层：通过 `models` 和 `repositories` 把具体读写逻辑按领域拆开。

这使得上层代码不需要直接接触连接细节，也不需要在各处重复拼查询。

## 直接子目录地图

`packages/database/src` 下的直接子目录主要有这些：

- `core`：数据库实例创建与环境适配的入口。这里通常是连库、缓存实例、测试环境兼容的地方。
- `schemas`：Drizzle 表结构与关联定义的总出口，里面还按主题继续拆分，如 `agentDocuments`、`ragEvals`、`userMemories` 等。
- `models`：面向业务概念的模型层，按领域组织，比如 `agentDocuments`、`agentEval`、`agentSignal`、`ragEval`、`userMemory`，并带有大量测试。
- `repositories`：更偏应用场景的查询/写入封装，按能力域拆分为 `aiInfra`、`dataImporter`、`knowledge`、`search`、`topicImporter`、`userMemory` 等。
- `server`：服务端侧的轻量出口，当前片段里主要是把 `getServerDB`、`serverDB` 转出。
- `types`：类型定义补充区，通常承接数据库相关的公共类型。
- `utils`：通用小工具，例如 ID 生成类辅助函数。

如果只看目录角色，不展开叶子文件，这里最值得注意的是：`models` 和 `repositories` 都是按领域切块，但它们的关注点不同，前者更接近“实体/业务模型”，后者更接近“面向场景的数据操作”。

## 关键入口

最重要的几个入口文件是：

- `packages/database/src/index.ts`：包级主入口，对外导出 `core/db-adaptor`、`repositories/compression`、`type`、`utils/idGenerator`。
- `packages/database/src/core/db-adaptor.ts`：真正的数据库适配层，提供 `getServerDB` 和 `serverDB`。
- `packages/database/src/core/web-server.ts`：真正创建 Drizzle 实例的地方，决定用 `node-postgres` 还是 Neon serverless。
- `packages/database/src/schemas/index.ts`：所有 schema 的总出口，其他层通常通过这里拿到完整表定义。
- `packages/database/src/server/index.ts`：服务端侧的再导出入口，把 `getServerDB` 和 `serverDB` 暴露出去。

从结构上看，`index.ts` 不是重逻辑文件，而是“包的公开门面”；真正的初始化策略集中在 `core/`。

## 主流程位置

主流程可以理解成一条从“环境检查”到“可用 DB 实例”的链路，核心位置在 `core/web-server.ts` 和 `core/db-adaptor.ts`。

流程大致是：

1. `core/db-adaptor.ts` 先提供懒加载接口 `getServerDB()`，避免模块一被 import 就立刻初始化数据库。
2. 如果已经缓存了实例，就直接复用 `cachedDB`。
3. 否则调用 `getDBInstance()`。
4. `core/web-server.ts` 负责真正创建数据库：
   - 在 `NODE_ENV === 'test'` 时返回空壳实例，避免测试初始化失败。
   - 校验 `KEY_VAULTS_SECRET` 和 `DATABASE_URL`。
   - 根据 `DATABASE_DRIVER` 选择 `pg` 或 Neon。
   - 为连接池注册 `error` 监听，避免 idle client 错误把进程打崩。
5. 最终把 `schema` 注入 Drizzle 实例，得到完整的 `LobeChatDatabase`。

也就是说，这个目录真正的“主流程”不是 CRUD，而是“如何稳定、安全地把数据库对象交出去”。

## 推荐阅读顺序

如果是第一次理解这个目录，建议按下面顺序看：

1. `packages/database/src/index.ts`：先看包对外暴露什么。
2. `packages/database/src/type.ts`：确认数据库实例和事务类型是怎么定义的。
3. `packages/database/src/core/db-adaptor.ts`：看缓存、懒加载和服务端入口。
4. `packages/database/src/core/web-server.ts`：看真实建连逻辑和环境分支。
5. `packages/database/src/schemas/index.ts`：理解 schema 是如何聚合的。
6. 再回头看 `models/` 和 `repositories/` 的目录切分，这时更容易理解它们各自承接的业务范围。

## 常见误区

最常见的误区是把 `models`、`repositories`、`schemas` 混为一谈。实际上：

- `schemas` 负责“数据库长什么样”。
- `models` 负责“某个业务实体怎么被组织和操作”。
- `repositories` 负责“某类场景怎么查询或写入”。

第二个误区是以为 `core/web-server.ts` 只是普通工具文件。其实它是数据库启动策略的中心，包含环境判断、驱动切换、错误监听和 schema 注入，属于高敏感入口。

第三个误区是忽略 `test` 分支。这里有专门的测试环境返回逻辑，说明这个包的设计目标之一就是让数据库相关测试尽量不依赖真实连库。

最后要注意，`server/` 在当前片段里看起来很薄，只是把服务端 DB 入口再导出。根据当前片段推断，它更像“服务端消费层的稳定门面”，而不是另起一套数据库实现。
