# 文件：drizzle.config.ts

## 它负责什么

`drizzle.config.ts` 是仓库根目录下给 `drizzle-kit` 使用的数据库结构配置文件。它本身不定义业务表，也不执行迁移，而是告诉 Drizzle CLI：

1. 数据库连接地址从哪里来：`process.env.DATABASE_URL`
2. 当前项目使用什么数据库方言：`postgresql`
3. schema 源码在哪里：`./packages/database/src/schemas`
4. 生成出来的 migration 文件放哪里：`./packages/database/migrations`
5. 是否启用严格模式：`strict: true`

可以把它理解为“数据库 schema 生成工具的导航文件”。当开发者运行 `db:generate` 或 `drizzle-kit studio` 这类命令时，`drizzle-kit` 会读取这个配置，找到 schema 源码、连接数据库，并按配置生成或展示数据库结构。

这个文件服务的是“开发期/构建期的 Drizzle 工具链”，不是应用运行时的数据库访问入口。应用真正执行迁移时，使用的是 `scripts/migrateServerDB/index.ts`，而不是直接执行 `drizzle.config.ts`。

## 关键组成

文件顶部有两个 import：

```ts
import * as dotenv from 'dotenv';
import type { Config } from 'drizzle-kit';
```

`dotenv` 用来加载 `.env` 中的环境变量。这里调用了：

```ts
dotenv.config();
```

这意味着只要项目根目录存在 `.env`，`DATABASE_URL` 就可以从里面被加载到 `process.env`。注释里提到也可以通过 Node 的 `dotenv_config_path` 参数指定其他 env 文件，但当前文件自身只显式调用了默认的 `dotenv.config()`。

`Config` 是从 `drizzle-kit` 导入的类型，只用于 TypeScript 类型检查：

```ts
import type { Config } from 'drizzle-kit';
```

因为它是 `import type`，编译到运行时代码时不会产生实际依赖加载。

核心变量是：

```ts
let connectionString = process.env.DATABASE_URL!;
```

这里用非空断言 `!` 告诉 TypeScript：`DATABASE_URL` 一定存在。注意，这只是类型层面的承诺，不会在运行时真正校验。如果实际环境没有 `DATABASE_URL`，`connectionString` 仍然可能是 `undefined`，只是 TypeScript 不再报错。

默认导出是整个文件最重要的部分：

```ts
export default {
  dbCredentials: {
    url: connectionString,
  },
  dialect: 'postgresql',
  out: './packages/database/migrations',
  schema: './packages/database/src/schemas',
  strict: true,
} satisfies Config;
```

逐项看：

`dbCredentials.url`  
数据库连接字符串，来自 `DATABASE_URL`。这是 `drizzle-kit` 连接 PostgreSQL 数据库时使用的地址。

`dialect: 'postgresql'`  
声明当前数据库类型是 PostgreSQL。结合仓库里的迁移脚本也可以看到运行迁移时使用了 `drizzle-orm/neon-serverless/migrator` 或 `drizzle-orm/node-postgres/migrator`，说明 PostgreSQL 是这里的核心数据库目标。

`out: './packages/database/migrations'`  
Drizzle 生成 migration SQL 文件的输出目录。项目的数据库迁移产物集中放在 `packages/database/migrations` 下。

`schema: './packages/database/src/schemas'`  
Drizzle schema 源码目录。该目录下有大量业务表定义文件，例如 `agent.ts`、`message.ts`、`session.ts`、`user.ts`、`topic.ts`、`file.ts`、`rag.ts` 等，同时还有 `index.ts` 和 `relations.ts` 作为 schema 聚合与关系定义入口。

`strict: true`  
启用 Drizzle Kit 的严格模式。通常用于让 schema 和迁移生成过程更谨慎，减少隐式或危险变更被静默处理的可能。

`satisfies Config`  
这是 TypeScript 的类型约束写法。它会检查这个对象是否满足 `drizzle-kit` 的 `Config` 类型，同时保留对象字面量自身较精确的类型。相比直接写成 `const config: Config = ...`，`satisfies` 更适合配置文件，因为既能校验字段，又不会过度抹平字段类型。

## 上下游关系

上游输入主要有两类。

第一类是环境变量：

```ts
DATABASE_URL
```

`drizzle.config.ts` 通过 `dotenv.config()` 读取 `.env`，再从 `process.env.DATABASE_URL` 取数据库连接字符串。这个连接字符串是 Drizzle CLI 访问数据库的基础。

第二类是 schema 源码：

```plaintext
packages/database/src/schemas
```

这个目录是数据库表结构的真实来源。根据当前片段可以看到其中包含多个领域的 schema 文件：

```plaintext
packages/database/src/schemas/agent.ts
packages/database/src/schemas/message.ts
packages/database/src/schemas/session.ts
packages/database/src/schemas/topic.ts
packages/database/src/schemas/user.ts
packages/database/src/schemas/file.ts
packages/database/src/schemas/rag.ts
packages/database/src/schemas/relations.ts
packages/database/src/schemas/index.ts
...
```

这些文件描述了数据库表、字段、索引、外键、关系等结构。`drizzle.config.ts` 不关心每张表的业务含义，只负责告诉 `drizzle-kit` 去哪里读取这些定义。

下游输出主要是 migration 文件：

```plaintext
packages/database/migrations
```

当运行：

```bash
db:generate
```

对应 `package.json` 中的脚本是：

```json
"db:generate": "drizzle-kit generate && npm run workflow:dbml"
```

其中 `drizzle-kit generate` 会读取 `drizzle.config.ts`，比较 schema 与迁移历史，然后生成新的 migration 文件到 `packages/database/migrations`。后面的 `workflow:dbml` 则用于数据库结构可视化相关流程，根据当前片段可以判断它是数据库文档/图谱的后续步骤。

另一个相关脚本是：

```json
"db:studio": "drizzle-kit studio"
```

`drizzle-kit studio` 也会使用该配置来连接数据库并读取 schema，用于打开 Drizzle Studio 这类数据库查看工具。

需要特别区分的是：

```json
"db:migrate": "cross-env MIGRATION_DB=1 tsx ./scripts/migrateServerDB/index.ts"
```

`db:migrate` 并不是直接运行 `drizzle-kit migrate`，而是运行仓库自己的迁移脚本 `scripts/migrateServerDB/index.ts`。这个脚本读取 `DATABASE_URL`，动态导入 `packages/database/src/server` 里的 `serverDB`，然后根据 `DATABASE_DRIVER` 选择 `node-postgres` 或 `neon-serverless` 的 migrator，最终执行 `packages/database/migrations` 目录中的迁移文件。

所以关系可以概括为：

```plaintext
packages/database/src/schemas
        ↓
drizzle.config.ts
        ↓
drizzle-kit generate
        ↓
packages/database/migrations
        ↓
scripts/migrateServerDB/index.ts
        ↓
真实 PostgreSQL 数据库
```

## 运行/调用流程

以新增或修改数据库表字段为例，典型流程是：

1. 开发者修改 `packages/database/src/schemas` 下的 schema 文件。
2. 开发者运行 `db:generate`。
3. `db:generate` 调用 `drizzle-kit generate`。
4. `drizzle-kit` 自动读取根目录的 `drizzle.config.ts`。
5. `drizzle.config.ts` 通过 `dotenv.config()` 加载 `.env`。
6. 配置对象把 `DATABASE_URL` 传给 `dbCredentials.url`。
7. `drizzle-kit` 根据 `schema: './packages/database/src/schemas'` 扫描 schema。
8. `drizzle-kit` 根据 `out: './packages/database/migrations'` 把生成的迁移文件写入 migrations 目录。
9. 后续运行 `db:migrate` 时，项目自己的迁移脚本读取这些 migrations，并应用到真实数据库。

以构建部署流程为例，`package.json` 中有：

```json
"build:vercel": "cross-env-shell NODE_OPTIONS=--max-old-space-size=8192 \"bun run build:raw && bun run db:migrate\""
```

这说明 Vercel 构建流程在完成应用构建后，会执行 `db:migrate`。不过这里执行的是 `scripts/migrateServerDB/index.ts`，它使用 migrations 目录中的历史迁移文件，而不是重新根据 schema 生成 migration。

迁移脚本里有一个重要保护：

```ts
const connectionString = process.env.DATABASE_URL;

if (connectionString) {
  runMigrations()
} else {
  console.log('not find database env or in desktop mode, migration skipped')
}
```

也就是说，真正运行迁移时如果没有 `DATABASE_URL`，会跳过迁移。这和 `drizzle.config.ts` 的非空断言不同：`drizzle.config.ts` 偏向 CLI 配置，假定环境变量存在；迁移脚本偏向实际运行，显式处理了没有数据库环境变量的情况。

根据当前片段推断，桌面端或不需要服务端数据库的场景可能不会配置 `DATABASE_URL`，因此迁移脚本会跳过数据库迁移。

## 小白阅读顺序

建议先读 `drizzle.config.ts`，因为它只有十几行，能快速建立三个核心概念：

```plaintext
schema 从哪里来
migration 生成到哪里
数据库连接从哪里来
```

然后读 `package.json` 中数据库相关脚本：

```json
"db:generate": "drizzle-kit generate && npm run workflow:dbml"
"db:migrate": "cross-env MIGRATION_DB=1 tsx ./scripts/migrateServerDB/index.ts"
"db:studio": "drizzle-kit studio"
```

这一步要搞清楚：

`db:generate` 是“生成迁移文件”  
`db:migrate` 是“执行迁移文件”  
`db:studio` 是“打开数据库查看工具”

接着看 schema 目录：

```plaintext
packages/database/src/schemas
```

重点从这几个文件开始：

```plaintext
packages/database/src/schemas/index.ts
packages/database/src/schemas/relations.ts
packages/database/src/schemas/user.ts
packages/database/src/schemas/session.ts
packages/database/src/schemas/message.ts
packages/database/src/schemas/topic.ts
```

`index.ts` 通常用于集中导出 schema；`relations.ts` 通常用于定义表之间的关联；业务表文件则能帮助理解项目的数据模型。

最后看迁移执行脚本：

```plaintext
scripts/migrateServerDB/index.ts
```

这一步重点理解它和 `drizzle.config.ts` 的区别：

`drizzle.config.ts` 给 `drizzle-kit` 生成/查看使用。  
`scripts/migrateServerDB/index.ts` 给项目实际执行迁移使用。

如果只看 `drizzle.config.ts`，容易误以为它负责所有数据库迁移；看完迁移脚本后就能明白，它只是工具链配置的一环。

## 常见误区

第一个误区：以为 `drizzle.config.ts` 会在应用运行时自动执行。

它不会。这个文件是 Drizzle Kit 的配置文件，主要被 `drizzle-kit generate`、`drizzle-kit studio` 这类 CLI 命令读取。应用运行时的数据库访问和迁移执行有其他入口，例如 `packages/database/src/server` 和 `scripts/migrateServerDB/index.ts`。

第二个误区：以为修改 schema 后数据库会自动变化。

不会。修改 `packages/database/src/schemas` 只是改了 TypeScript 层面的结构定义。要让数据库结构变化，需要先运行 `db:generate` 生成 migration，再通过 `db:migrate` 或部署流程执行 migration。

第三个误区：混淆 `schema` 和 `out`。

`schema` 指向源码目录：

```ts
schema: './packages/database/src/schemas'
```

`out` 指向生成结果目录：

```ts
out: './packages/database/migrations'
```

前者是“从哪里读表定义”，后者是“把迁移文件写到哪里”。

第四个误区：以为 `process.env.DATABASE_URL!` 会校验环境变量。

`!` 只是 TypeScript 非空断言，不是运行时检查。它不会阻止 `DATABASE_URL` 为空，也不会抛出更友好的错误。实际运行 `drizzle-kit` 时，如果没有正确配置 `DATABASE_URL`，可能会在连接数据库阶段失败。

第五个误区：以为 `db:migrate` 会读取 `drizzle.config.ts`。

根据当前片段，`db:migrate` 执行的是：

```bash
tsx ./scripts/migrateServerDB/index.ts
```

这个脚本直接指定 migrations 目录：

```ts
const migrationsFolder = join(__dirname, '../../packages/database/migrations');
```

并通过 `drizzle-orm` 的 migrator 执行迁移。它和 `drizzle.config.ts` 共享的是 migrations 目录约定和数据库环境变量，但不是直接读取 `drizzle.config.ts` 来执行。

第六个误区：忽略 `DATABASE_DRIVER` 的影响。

迁移脚本中根据：

```ts
process.env.DATABASE_DRIVER === 'node'
```

选择 `node-postgres` migrator，否则默认使用 `neon-serverless` migrator。`drizzle.config.ts` 只声明了 `dialect: 'postgresql'`，并不负责选择运行时 driver。也就是说，“数据库方言”和“连接驱动”是两个层面的配置。

第七个误区：把 `strict: true` 当成业务校验。

`strict: true` 是 Drizzle Kit 配置层面的严格模式，作用在 schema/migration 工具链上，不是应用业务逻辑的校验规则，也不会替代后端 service、router 或数据库约束本身。
