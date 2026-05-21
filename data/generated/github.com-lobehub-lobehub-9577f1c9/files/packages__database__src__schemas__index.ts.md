# 文件：packages/database/src/schemas/index.ts

## 它负责什么

`packages/database/src/schemas/index.ts` 是 `@lobechat/database` 包里数据库 Schema 层的统一导出入口，也就是一个典型的 barrel file。

它本身不定义表、不写业务逻辑、不连接数据库，而是把 `packages/database/src/schemas/` 目录下分散在各个领域文件里的 Drizzle schema 统一重新导出：

```ts
export * from './agent';
export * from './message';
export * from './session';
export * from './topic';
export * from './user';
// ...
```

从包级配置看，`packages/database/package.json` 明确把它暴露成子路径导出：

```json
"exports": {
  ".": "./src/index.ts",
  "./schemas": "./src/schemas/index.ts"
}
```

所以外部代码可以这样使用：

```ts
import { agents, messages, topics } from '@lobechat/database/schemas';
```

内部数据库模型、仓储、测试也大量通过相对路径使用它：

```ts
import { agents, users } from '../schemas';
import * as schema from '../schemas';
```

它的核心职责可以概括为：**把所有数据库表、关系、类型、常量和 insert schema 聚合成一个稳定的公共 schema API**。

## 关键组成

这个文件由一组 `export * from './xxx'` 组成，按领域把 schema 模块聚合起来。根据当前文件内容，可以大致分成几类。

第一类是核心会话与消息相关表：

```ts
export * from './agent';
export * from './chatGroup';
export * from './message';
export * from './session';
export * from './topic';
export * from './relations';
```

这些模块通常定义聊天系统的主干数据结构。例如 `agent.ts` 中定义了 `agents` 表、`agentsKnowledgeBases`、`agentsFiles` 等表，并导出：

```ts
export type NewAgent = typeof agents.$inferInsert;
export type AgentItem = typeof agents.$inferSelect;
```

`message.ts` 中定义了 `messageGroups` 等消息相关表，并引用 `agents`、`sessions`、`topics`、`users`、`files`、`chunks` 等表，说明消息 schema 位于多个业务实体的交汇处。

第二类是用户、认证和权限相关表：

```ts
export * from './user';
export * from './nextauth';
export * from './betterAuth';
export * from './oidc';
export * from './apiKey';
export * from './rbac';
```

这些模块负责用户账号、登录认证、OIDC 会话、API Key、角色权限等数据库结构。

第三类是知识库、文件、RAG 和文档相关表：

```ts
export * from './file';
export * from './rag';
export * from './ragEvals';
export * from './documentHistory';
export * from './agentDocuments';
```

这些模块和文件管理、知识库、向量检索、RAG 评测、文档历史记录相关。调用方中可以看到 `repositories/knowledge`、`models/chunk`、`models/embedding`、`models/document` 等会使用这些导出。

第四类是 AI 基础设施和模型配置相关表：

```ts
export * from './aiInfra';
export * from './agentBotProvider';
export * from './systemBotProvider';
```

根据命名和调用方推断，这些模块用于存储 AI provider、model、bot provider 等配置。调用方包括 `models/aiProvider.ts`、`models/aiModel.ts`、`models/agentBotProvider.ts`、`models/systemBotProvider.ts`。

第五类是任务、异步任务、生成任务和 Agent 执行相关表：

```ts
export * from './asyncTask';
export * from './generation';
export * from './task';
export * from './agentCronJob';
export * from './agentOperations';
export * from './agentEvals';
export * from './agentSkill';
```

这些模块服务于后台任务、生成记录、Agent 技能、Agent 评测、Agent 操作记录和定时任务。

第六类是通知、Messenger、记忆等扩展领域：

```ts
export * from './notification';
export * from './messengerAccountLink';
export * from './messengerInstallation';
export * from './userMemories';
```

其中 `userMemories` 是一个目录，实际入口是 `packages/database/src/schemas/userMemories/index.ts`，由这里继续统一导出。

另外，`index.ts` 还导出了：

```ts
export * from './relations';
```

这个文件通常用于 Drizzle 的关系定义。`core/web-server.ts` 和 `core/getTestDB.ts` 都会 `import * as schema from '../schemas'`，因此 `relations` 也会被一起传入 Drizzle，使查询层可以使用关系元数据。

## 上下游关系

上游是 `packages/database/src/schemas/` 目录里的各个具体 schema 文件。

这些具体文件一般会做几件事：

1. 从 `drizzle-orm/pg-core` 引入 `pgTable`、`text`、`jsonb`、`index`、`uniqueIndex`、`primaryKey` 等构表工具。
2. 从其他 schema 文件引入被引用的表，例如 `agent.ts` 引入 `users`、`files`、`knowledgeBases`、`sessionGroups`。
3. 定义数据库表，例如 `agents = pgTable(...)`。
4. 定义索引、唯一约束、外键和级联删除策略。
5. 导出 Drizzle 推导类型，例如 `NewAgent`、`AgentItem`。
6. 有些文件还导出 `createInsertSchema` 生成的 Zod schema 或业务常量。

`index.ts` 把这些上游模块重新导出，形成一个统一下游入口。

下游主要有三类。

第一类是 Drizzle 数据库实例初始化。

`packages/database/src/core/web-server.ts` 中：

```ts
import * as schema from '../schemas';

return nodeDrizzle(client, { schema });
return neonDrizzle(client, { schema });
```

这里会把整个 schema 对象传给 Drizzle。也就是说，`index.ts` 的导出集合会直接影响运行时数据库客户端认识哪些表和关系。

`packages/database/src/core/getTestDB.ts` 中也一样：

```ts
import * as schema from '../schemas';

testServerDB = nodeDrizzle(client, { schema });
testClientDB = pgliteDrizzle({ client: pglite, schema });
```

测试数据库同样依赖这个聚合入口。

第二类是数据库模型和仓储层。

例如：

```ts
import { agents, messages, topics } from '../schemas';
import type { AgentItem, NewAgent } from '../schemas';
```

这些文件使用 schema 中导出的表对象构造 Drizzle 查询，例如 `db.select().from(agents)`、`db.insert(messages)`、`eq(topics.id, ...)`。同时也使用 `$inferInsert`、`$inferSelect` 派生出来的类型作为模型输入输出类型。

第三类是应用层和测试层。

外部应用代码会通过包路径导入：

```ts
import { type DocumentItem } from '@lobechat/database/schemas';
import { oidcSessions } from '@lobechat/database/schemas';
```

测试代码也大量直接导入表对象，用于插入测试数据、断言数据库状态或构造集成测试环境。

因此，这个文件虽然只有导出语句，但它位于数据库包的“公共边界”上：**上游 schema 文件新增、删除、改名，最终都需要通过这里暴露给 Drizzle 初始化和业务代码使用。**

## 运行/调用流程

典型运行流程如下。

1. 某个服务、模型或测试需要访问数据库。
2. 数据库初始化代码执行 `import * as schema from '../schemas'`。
3. TypeScript/打包器解析到 `packages/database/src/schemas/index.ts`。
4. `index.ts` 继续重新导出 `agent.ts`、`message.ts`、`user.ts`、`relations.ts` 等所有 schema 模块。
5. 各 schema 模块执行顶层定义，生成 Drizzle 表对象、关系对象、类型导出和常量导出。
6. `schema` 对象被传入 Drizzle：

```ts
nodeDrizzle(client, { schema });
neonDrizzle(client, { schema });
pgliteDrizzle({ client, schema });
```

7. 之后模型层可以用这些表对象构造类型安全查询：

```ts
db.select().from(agents);
db.insert(messages).values(...);
```

对于外部业务代码，调用流程更简单：

1. 代码从 `@lobechat/database/schemas` 导入表、类型或常量。
2. 包导出映射把该路径解析到 `./src/schemas/index.ts`。
3. `index.ts` 把具体模块里的导出转发给调用方。

需要注意的是，`index.ts` 不主动调用任何函数，也不主动建立数据库连接。它参与运行的方式是：**作为模块加载和导出聚合的一环，被 Drizzle 初始化和业务查询代码间接使用。**

## 小白阅读顺序

建议按下面顺序读，不要一上来就试图看完整个 `schemas/` 目录。

第一步，先读当前文件：

```ts
packages/database/src/schemas/index.ts
```

目标是看清它导出了哪些领域模块。它本身没有复杂逻辑，重点是建立“数据库 schema 总目录”的概念。

第二步，读包导出配置：

```ts
packages/database/package.json
```

重点看：

```json
"./schemas": "./src/schemas/index.ts"
```

这能解释为什么应用代码可以写：

```ts
import { agents } from '@lobechat/database/schemas';
```

第三步，读数据库初始化入口：

```ts
packages/database/src/core/web-server.ts
packages/database/src/core/getTestDB.ts
```

重点看：

```ts
import * as schema from '../schemas';
```

这一步能理解为什么 barrel export 不只是为了方便导入，它还决定了 Drizzle 初始化时收到的完整 schema 集合。

第四步，挑一个核心 schema 文件读，例如：

```ts
packages/database/src/schemas/agent.ts
```

关注 `pgTable`、字段定义、外键、索引、`$inferInsert`、`$inferSelect`。读完这个文件后，再回头看 `index.ts` 中的 `export * from './agent'`，就能理解这条导出实际暴露了哪些东西。

第五步，再读一个关系复杂的文件，例如：

```ts
packages/database/src/schemas/message.ts
packages/database/src/schemas/relations.ts
```

`message.ts` 会引用多个领域表，适合理解 schema 文件之间如何互相依赖。`relations.ts` 则适合理解 Drizzle relation 元数据为什么也要被统一导出。

第六步，任选一个调用方读，例如：

```ts
packages/database/src/models/agent.ts
packages/database/src/models/message.ts
packages/database/src/repositories/knowledge/index.ts
```

这一步看业务代码如何使用 `agents`、`messages`、`documents` 等表对象，把 schema 定义和真实查询连接起来。

## 常见误区

误区一：以为 `index.ts` 定义了数据库表。

实际不是。它只是重新导出。真正的表定义在 `agent.ts`、`message.ts`、`user.ts`、`file.ts` 等具体文件中。

误区二：以为这个文件只影响导入路径美观。

它确实让导入更方便，但作用不止于此。`core/web-server.ts` 和 `core/getTestDB.ts` 会把 `import * as schema from '../schemas'` 得到的对象传给 Drizzle，所以这里的导出集合会影响运行时数据库实例可见的 schema。

误区三：新增 schema 文件后忘记在这里导出。

如果新增了 `schemas/foo.ts`，但没有在 `schemas/index.ts` 里加：

```ts
export * from './foo';
```

那么 `@lobechat/database/schemas` 无法直接导出它，`import * as schema from '../schemas'` 也不会包含它。根据当前片段推断，这可能导致模型层无法统一导入新表，或者 Drizzle 初始化时缺少对应表/关系元数据。

误区四：把 `packages/database/src/index.ts` 和 `packages/database/src/schemas/index.ts` 混为一谈。

`packages/database/src/index.ts` 是数据库包的主入口，当前只导出：

```ts
export * from './core/db-adaptor';
export * from './repositories/compression';
export * from './type';
export * from './utils/idGenerator';
```

而 schema 子路径入口是由 `package.json` 的 `"./schemas"` 单独暴露的。也就是说：

```ts
import { getDBInstance } from '@lobechat/database';
```

和：

```ts
import { agents } from '@lobechat/database/schemas';
```

走的是不同入口。

误区五：以为 `export *` 会导出默认导出。

`export * from './agent'` 只会转发命名导出，不会转发 `default export`。当前 schema 文件采用的是命名导出模式，例如 `export const agents`、`export type AgentItem`，所以这种写法是匹配的。

误区六：忽略 schema 文件之间的循环引用风险。

例如 `message.ts` 中存在自引用或跨模块引用，`agent.ts` 也引用 `users`、`files`、`knowledgeBases` 等表。Drizzle 通常通过回调形式声明外键：

```ts
.references(() => users.id, { onDelete: 'cascade' })
```

这种写法可以缓解模块加载顺序问题。但如果新增 schema 时随意改动导入关系，仍可能引入循环依赖或初始化顺序问题。阅读时要注意具体表之间的引用方向。

误区七：把 schema 类型当成业务 DTO。

例如：

```ts
export type NewAgent = typeof agents.$inferInsert;
export type AgentItem = typeof agents.$inferSelect;
```

这些类型直接反映数据库表结构，适合模型层和仓储层使用。它们不一定等同于 API 返回给前端的 DTO，也不一定包含业务组装后的字段。业务层如果需要隐藏字段、合并字段或转换结构，通常应另行定义类型或在服务层处理。
