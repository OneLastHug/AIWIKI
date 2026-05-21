# 文件：packages/database/src/core/web-server.ts

## 它负责什么

`packages/database/src/core/web-server.ts` 是服务端数据库实例的创建入口，核心导出只有一个函数：`getDBInstance()`。

它的职责可以概括为：根据当前运行环境和数据库配置，创建一个可供服务端代码使用的 Drizzle 数据库对象。这个对象类型是 `LobeChatDatabase`，上层代码拿到它之后就可以执行 `select`、`insert`、`delete`、`transaction` 等 Drizzle ORM 操作。

这个文件不负责定义表结构，也不负责执行具体业务查询。它只做数据库连接层的初始化：

- 校验必要环境变量，例如 `KEY_VAULTS_SECRET`、`DATABASE_URL`
- 根据 `DATABASE_DRIVER` 选择连接实现
- 为连接池注册 `error` 监听，避免空闲连接错误导致 Node 进程崩溃
- 把底层连接池交给 Drizzle，生成带 schema 的数据库访问对象
- 在测试环境下返回空的 mock 对象，避免初始化真实数据库

它是一个偏底层的基础设施文件，位于 `packages/database/src/core/`，和同目录的 `db-adaptor.ts`、`getTestDB.ts` 一起构成数据库运行时入口。

## 关键组成

### 1. 数据库驱动相关 import

文件开头引入了两套数据库驱动：

```ts
import { neonConfig, Pool as NeonPool } from '@neondatabase/serverless';
import { drizzle as neonDrizzle } from 'drizzle-orm/neon-serverless';
import { drizzle as nodeDrizzle } from 'drizzle-orm/node-postgres';
import { Pool as NodePool } from 'pg';
import ws from 'ws';
```

这里可以看出项目支持两种服务端 PostgreSQL 连接方式：

- `@neondatabase/serverless`：默认的 Neon serverless 连接方式，适合 serverless / Vercel 等环境
- `pg` + `drizzle-orm/node-postgres`：传统 Node PostgreSQL 连接池方式

`ws` 只在特定迁移场景下使用，用来给 Neon serverless 配置 WebSocket 构造器。

### 2. 配置来源 `serverDBEnv`

```ts
import { serverDBEnv } from '@/config/db';
```

`serverDBEnv` 来自 `src/config/db.ts`。该配置读取并校验以下与数据库相关的环境变量：

- `DATABASE_DRIVER`：数据库驱动，默认是 `neon`，可选值为 `neon` 或 `node`
- `DATABASE_URL`：主数据库连接字符串
- `DATABASE_TEST_URL`：测试数据库连接字符串，主要由测试入口使用
- `KEY_VAULTS_SECRET`：服务端加密相关密钥
- `REMOVE_GLOBAL_FILE`：其他数据库相关开关

在 `web-server.ts` 中直接用到的是：

- `serverDBEnv.KEY_VAULTS_SECRET`
- `serverDBEnv.DATABASE_URL`
- `serverDBEnv.DATABASE_DRIVER`

### 3. schema 注入

```ts
import * as schema from '../schemas';
```

这里把 `packages/database/src/schemas` 下导出的所有表结构、关系等内容整体传给 Drizzle：

```ts
return nodeDrizzle(client, { schema });
return neonDrizzle(client, { schema });
```

这样返回的数据库对象就不是一个“裸 Drizzle 实例”，而是带有项目 schema 类型信息的实例。上层使用时可以通过 `db.query.users.findFirst()`、`db.insert(users)` 等方式获得类型提示。

### 4. 返回类型 `LobeChatDatabase`

```ts
import type { LobeChatDatabase } from '../type';
```

`LobeChatDatabase` 在 `packages/database/src/type.ts` 中定义：

```ts
export type LobeChatDatabase = NeonDatabase<LobeChatDatabaseSchema>;
```

也就是说，项目把数据库访问对象统一抽象为 `LobeChatDatabase`。虽然 `web-server.ts` 在 `DATABASE_DRIVER === 'node'` 时实际返回的是 `node-postgres` 版 Drizzle，但函数签名仍统一成 `LobeChatDatabase`，方便上层调用方不关心底层连接实现。

根据当前片段推断：这里的类型统一更偏向工程便利性，上层业务通常只使用 Drizzle 的通用查询能力，因此不需要区分 Neon 或 Node Pool 的具体类型。

### 5. `getDBInstance()`

这是文件唯一导出的函数：

```ts
export const getDBInstance = (): LobeChatDatabase => {
  ...
};
```

它的执行逻辑按顺序是：

1. 如果 `NODE_ENV === 'test'`，直接返回空对象并强转为 `LobeChatDatabase`
2. 检查 `KEY_VAULTS_SECRET` 是否存在，不存在就抛错
3. 读取 `DATABASE_URL`
4. 如果 `DATABASE_URL` 不存在，抛错
5. 如果 `DATABASE_DRIVER === 'node'`，创建 `pg` 的 `NodePool`
6. 否则走默认 Neon serverless 连接
7. 为连接池注册 `error` 事件监听
8. 返回 Drizzle 数据库实例

### 6. 测试环境短路

```ts
if (process.env.NODE_ENV === 'test') return {} as LobeChatDatabase;
```

这是一个非常重要的分支。它表示普通测试环境不会在 import 或调用 `getDBInstance()` 时真的初始化数据库连接。

同目录的 `getTestDB.ts` 才是测试数据库的正式入口，它支持：

- `TEST_SERVER_DB === '1'` 时使用真实 PostgreSQL 测试库
- 默认情况下使用 `PGlite` 内存数据库
- 自动执行 migrations，并跳过 PGlite 不兼容的 `pg_search` / `bm25` SQL

所以不要把 `web-server.ts` 里的 test 分支理解为“测试数据库初始化逻辑”。它只是为了避免测试环境误触发真实连接。

### 7. `KEY_VAULTS_SECRET` 校验

```ts
if (!serverDBEnv.KEY_VAULTS_SECRET) {
  throw new Error(...)
}
```

从命名上看，`KEY_VAULTS_SECRET` 是密钥保险箱、API Key 加密、OIDC cookie 加密等能力依赖的服务端密钥。虽然它不是连接 PostgreSQL 所必需的，但项目在初始化服务端数据库实例前强制要求它存在。

这意味着：只要代码路径使用了 `getDBInstance()`，就必须配置 `KEY_VAULTS_SECRET`，否则即使 `DATABASE_URL` 正确也会失败。

错误信息里提示可以用下面的命令生成：

```bash
openssl rand -base64 32
```

### 8. `DATABASE_DRIVER === 'node'` 分支

```ts
if (serverDBEnv.DATABASE_DRIVER === 'node') {
  const client = new NodePool({ connectionString });
  client.on('error', ...);
  return nodeDrizzle(client, { schema });
}
```

这个分支使用传统 `pg` 连接池。适合普通 Node.js 长驻进程、一些非 serverless 环境，或者需要用 `pg` 原生行为的场景。

关键点是注册了连接池错误监听：

```ts
client.on('error', (err) => {
  console.error('[NodePool] idle client error ...', ...)
});
```

注释说明：`pg.Pool` 的空闲客户端在后端连接断开时会触发 `error` 事件。如果没有监听器，Node 会把它升级为 `uncaughtException`，导致进程退出。

所以这里不是为了“修复数据库错误”，而是为了吞掉空闲连接的异步错误，避免整个服务进程被打死。真正的业务查询错误仍然会在业务调用处抛出。

### 9. Neon serverless 默认分支

如果 `DATABASE_DRIVER` 不是 `node`，就走 Neon serverless：

```ts
const client = new NeonPool({ connectionString });
client.on('error', ...);
return neonDrizzle(client, { schema });
```

根据 `src/config/db.ts`，`DATABASE_DRIVER` 默认值是 `neon`：

```ts
DATABASE_DRIVER: process.env.DATABASE_DRIVER || 'neon'
```

所以大多数未显式配置的服务端运行环境都会进入这个分支。

Neon Pool 也注册了 `error` 监听。注释中提到，NeonPool 通过 WebSocket 运行，瞬时断连会以 pool 的 `error` 事件浮现。如果没有监听器，在 Vercel 上曾导致 Lambda 在 5 分钟内崩溃 1800 多次，相关问题标记为 `LOBE-8704`。

这说明这段错误处理是生产稳定性修复，不是普通日志代码。

### 10. `MIGRATION_DB` 特殊处理

```ts
if (process.env.MIGRATION_DB === '1') {
  neonConfig.webSocketConstructor = ws;
}
```

这个逻辑只在 Neon 分支中、创建 NeonPool 之前执行。

根据注释链接和代码可知：Neon serverless 在某些 Node 环境中需要显式设置 WebSocket constructor。`MIGRATION_DB === '1'` 很可能用于数据库迁移命令或迁移执行环境，因为迁移通常运行在 Node 脚本里，而不是浏览器或已有 WebSocket 全局对象的环境中。

根据当前片段推断：普通运行时不一定需要手动设置 `neonConfig.webSocketConstructor`，但迁移环境为了保证 Neon WebSocket 可用，会通过 `MIGRATION_DB=1` 打开这个配置。

## 上下游关系

### 上游：配置、schema 和底层数据库驱动

`web-server.ts` 的上游依赖主要有三类。

第一类是配置：

- `src/config/db.ts`
- `serverDBEnv`
- 环境变量：`DATABASE_URL`、`DATABASE_DRIVER`、`KEY_VAULTS_SECRET`、`MIGRATION_DB`

这些配置决定是否能初始化数据库、使用哪个驱动、是否为 Neon 配置 WebSocket。

第二类是 schema：

- `packages/database/src/schemas`
- `packages/database/src/type.ts`

schema 决定 Drizzle 实例的类型能力和可查询表结构。`LobeChatDatabase` 则给上层提供统一类型。

第三类是外部数据库库：

- `@neondatabase/serverless`
- `pg`
- `drizzle-orm/neon-serverless`
- `drizzle-orm/node-postgres`
- `ws`

这些库负责真正建立 PostgreSQL 连接，并把连接池包装为 Drizzle ORM 实例。

### 下游：`db-adaptor.ts`

同目录的 `packages/database/src/core/db-adaptor.ts` 是最直接的下游：

```ts
import { getDBInstance } from './web-server';
```

它提供两个导出：

```ts
export const getServerDB = async (): Promise<LobeChatDatabase> => { ... };
export const serverDB = getDBInstance();
```

`getServerDB()` 做了懒加载缓存：

- 第一次调用时执行 `getDBInstance()`
- 后续调用返回 `cachedDB`
- 初始化失败时打印错误并重新抛出

`serverDB` 则是模块加载时立即调用 `getDBInstance()` 的同步实例。这个导出更直接，但也意味着 import 该模块时就可能触发环境变量校验和数据库初始化。

因此，上层使用 `getServerDB()` 还是 `serverDB`，会影响数据库连接创建时机。

### 下游：OIDC Provider

另一个直接调用方是：

```ts
src/server/services/oidc/oidcProvider.ts
```

该文件在 `getOIDCProvider()` 中调用：

```ts
const db = getDBInstance();
provider = await createOIDCProvider(db);
```

也就是说，OIDC Provider 初始化时需要数据库实例，并且绕过了 `db-adaptor.ts` 的懒加载缓存，直接从 `web-server.ts` 创建实例。

它还会先检查：

```ts
if (!authEnv.ENABLE_OIDC) {
  throw new Error('OIDC is not enabled. Set ENABLE_OIDC=1 to enable it.');
}
```

因此 OIDC 的调用链大致是：

`getOIDCProvider()` → 检查 `ENABLE_OIDC` → `getDBInstance()` → `createOIDCProvider(db)`

### 下游：业务 repository 和 server router

大量业务代码不会直接 import `web-server.ts`，而是通过 `getServerDB()`、`serverDB` 或测试中的 `getTestDB()` 拿到 `LobeChatDatabase`。常见下游包括：

- `packages/database/src/repositories/**`
- `src/server/routers/**`
- `src/server/services/**`
- 各类 integration test

这些下游通常关心的是“拿到一个 Drizzle DB 对象”，而不是关心它来自 NeonPool、NodePool 还是 PGlite。

### 与 `getTestDB.ts` 的关系

`getTestDB.ts` 和 `web-server.ts` 都能产出 `LobeChatDatabase`，但面向不同场景：

- `web-server.ts`：生产 / 开发服务端运行时数据库入口
- `getTestDB.ts`：测试数据库入口

`web-server.ts` 在 `NODE_ENV === 'test'` 下返回空对象，是为了避免误初始化。真正需要测试数据库的测试文件，会显式调用 `getTestDB()`。

这是一处容易混淆的设计：测试环境不是靠 `getDBInstance()` 创建 PGlite，而是靠单独的 `getTestDB()`。

## 运行/调用流程

### 默认 Neon 流程

默认情况下，`DATABASE_DRIVER` 是 `neon`。完整流程如下：

1. 某个服务端模块调用 `getDBInstance()`
2. 函数检查 `NODE_ENV`
3. 如果不是 `test`，继续初始化
4. 检查 `KEY_VAULTS_SECRET`
5. 检查 `DATABASE_URL`
6. 判断 `DATABASE_DRIVER`
7. 由于默认是 `neon`，进入 Neon 分支
8. 如果 `MIGRATION_DB === '1'`，设置 `neonConfig.webSocketConstructor = ws`
9. 创建 `new NeonPool({ connectionString })`
10. 给 NeonPool 注册 `error` 监听
11. 调用 `neonDrizzle(client, { schema })`
12. 返回 `LobeChatDatabase`

调用方之后就可以用这个 db 实例访问数据库。

### Node Pool 流程

当环境变量设置为：

```bash
DATABASE_DRIVER=node
```

流程变为：

1. 调用 `getDBInstance()`
2. 校验 `KEY_VAULTS_SECRET`
3. 校验 `DATABASE_URL`
4. 命中 `DATABASE_DRIVER === 'node'`
5. 创建 `new NodePool({ connectionString })`
6. 注册 `client.on('error', ...)`
7. 调用 `nodeDrizzle(client, { schema })`
8. 返回数据库实例

这个分支不会走 Neon 的 WebSocket 配置。

### 测试环境流程

当：

```bash
NODE_ENV=test
```

函数最开始直接返回：

```ts
{} as LobeChatDatabase
```

这意味着：

- 不检查 `KEY_VAULTS_SECRET`
- 不检查 `DATABASE_URL`
- 不创建连接池
- 不注入真实 schema 行为
- 不适合直接执行真实数据库查询

如果测试需要真实或模拟数据库，应使用：

```ts
getTestDB()
```

而不是依赖 `getDBInstance()`。

### 错误处理流程

这个文件主动抛出的错误主要有两个：

第一，缺少 `KEY_VAULTS_SECRET`：

```ts
throw new Error('`KEY_VAULTS_SECRET` is not set...')
```

第二，缺少 `DATABASE_URL`：

```ts
throw new Error('You are try to use database, but "DATABASE_URL" is not set correctly')
```

此外，连接池的 `error` 事件不会重新抛出，而是打印：

- `[NodePool] idle client error ...`
- `[NeonPool] idle client error ...`

这类日志表示空闲连接发生异常，代码选择吞掉它以避免进程崩溃。它不代表业务查询一定成功，也不代表数据库错误被全局忽略。

## 小白阅读顺序

1. 先看 `getDBInstance()` 的整体结构，不要一开始陷入 Neon、Drizzle、pg 的细节。先理解它就是“创建数据库实例”的工厂函数。

2. 再看最前面的测试环境分支：

   ```ts
   if (process.env.NODE_ENV === 'test') return {} as LobeChatDatabase;
   ```

   这个分支解释了为什么测试环境下不会真实连接数据库。

3. 接着看两个环境变量校验：

   ```ts
   serverDBEnv.KEY_VAULTS_SECRET
   serverDBEnv.DATABASE_URL
   ```

   这两个校验说明：服务端只要要用数据库，就必须先准备密钥和数据库连接字符串。

4. 然后看 `DATABASE_DRIVER === 'node'` 分支。这个分支比较接近传统 Node.js 数据库连接方式：创建 `pg.Pool`，再交给 Drizzle。

5. 再看默认 Neon 分支。重点理解它和 Node 分支类似，都是“创建连接池 → 注册错误监听 → 包装成 Drizzle 实例”，只是底层连接池不同。

6. 最后看同目录的 `db-adaptor.ts`。它能帮助你理解为什么 `getDBInstance()` 是底层函数，而业务层通常更适合通过 `getServerDB()` 获取数据库。

7. 如果还想继续看测试场景，再看 `getTestDB.ts`。它会说明项目测试时为什么可以不用真实生产数据库。

## 常见误区

### 误区一：以为 `web-server.ts` 负责业务查询

这个文件不写任何业务 SQL，也不关心用户、会话、消息、知识库等业务表的具体逻辑。它只负责初始化数据库访问对象。真正的业务查询一般在 repository、model、service 或 router 中。

### 误区二：以为 `KEY_VAULTS_SECRET` 是 PostgreSQL 连接必需项

从 PostgreSQL 连接本身看，真正连接数据库需要的是 `DATABASE_URL`。但项目在 `getDBInstance()` 中强制检查 `KEY_VAULTS_SECRET`，是因为数据库层和服务端加密能力在工程上被绑定了。

所以本项目里“能连数据库”不只意味着有 `DATABASE_URL`，还必须配置 `KEY_VAULTS_SECRET`。

### 误区三：以为测试环境会自动创建测试数据库

`NODE_ENV === 'test'` 时，`getDBInstance()` 返回的是空对象强转类型，不是真正可用的数据库。测试如果要查询数据库，应显式使用 `getTestDB()`。

也就是说：

- `getDBInstance()` 的 test 分支是防误触发
- `getTestDB()` 才是测试数据库初始化入口

### 误区四：以为 `client.on('error')` 会处理所有数据库错误

这里监听的是连接池上的异步 `error` 事件，特别是空闲连接断开之类的问题。它的目的主要是防止 Node 进程因为未监听的 `error` 事件崩溃。

业务查询里的错误，例如 SQL 约束失败、连接超时、字段错误，仍然会在执行查询的调用链里抛出，需要业务层自己处理。

### 误区五：以为 `DATABASE_DRIVER=node` 和默认行为一样

两者最终都返回 Drizzle 实例，但底层连接机制不同：

- `neon`：使用 `@neondatabase/serverless` 的 `NeonPool`，偏 serverless / WebSocket 场景
- `node`：使用 `pg` 的 `NodePool`，偏传统 Node.js PostgreSQL 场景

如果部署环境不同，连接池行为、错误表现、迁移配置都可能不同。

### 误区六：忽略 `MIGRATION_DB`

`MIGRATION_DB === '1'` 时会设置：

```ts
neonConfig.webSocketConstructor = ws;
```

这通常和迁移脚本或 Node 环境下运行 Neon serverless 有关。不要随意删除它；否则迁移环境可能因为缺少 WebSocket constructor 而无法连接 Neon。

### 误区七：把 `serverDB` 和 `getServerDB()` 看成完全一样

在 `db-adaptor.ts` 中：

```ts
export const serverDB = getDBInstance();
```

这是模块加载时立即初始化。

而：

```ts
export const getServerDB = async () => { ... }
```

是懒加载并缓存。

二者拿到的都是数据库实例，但初始化时机不同。对于服务端模块，初始化时机可能影响启动错误、测试 mock、serverless 冷启动和环境变量读取。
