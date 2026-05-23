# 子系统：packages/database/src/models

## 解决什么问题

`packages/database/src/models` 是数据库访问层里的“业务模型”目录，位于 LobeHub 数据流的后半段：`React UI → Store Actions → Client Service → TRPC Lambda → Server Services → DB Model → PostgreSQL`。它解决的问题不是声明表结构，而是把上层服务需要的持久化动作封装成可复用的 TypeScript 对象：创建、查询、更新、删除，以及围绕某个业务聚合的组合查询。

根据当前片段推断，`models` 主要承接 `src/server/services`、`src/server/routers` 等服务端代码的数据库读写请求，并基于 `packages/database/src/schemas` 中的 Drizzle 表定义构造查询。它的价值在于让上层服务不直接散落 `db.select()`、`db.insert()`、`eq()`、`and()` 这类 Drizzle 细节，而是通过面向领域的模型方法表达意图，例如“查询某用户的会话列表”“更新消息状态”“删除某知识库资源”等。

这个目录可以理解为数据库包里的领域持久化门面：它比 schema 更接近业务，比 server service 更接近数据库。

## 相关目录和文件

与 `packages/database/src/models` 最直接相关的是 `packages/database/src/schemas`。`schemas` 负责定义 PostgreSQL 表、字段、索引、外键和 Drizzle 类型，是模型层所有查询的结构来源。修改模型查询时，通常需要先确认对应 schema 的字段名、索引和关系约束。

`packages/database/src/repositories` 与 `models` 同属数据库访问层。根据项目架构说明，二者都在 `packages/database` 内部，但职责可能有细微差异：`models` 更偏向业务聚合的操作入口，`repositories` 更可能承载通用或较底层的数据访问封装。具体边界需要结合当前仓库文件判断；根据当前片段推断，上层服务优先依赖 `models` 完成领域动作。

上游调用通常来自 `src/server/services` 和 `src/server/routers/{async|lambda|mobile|tools}`。这些目录负责业务编排、鉴权上下文、接口协议和请求响应转换；数据库模型只处理已经被服务层判断过的持久化需求。

此外，`packages/database` 可能还包含数据库连接、迁移、测试工具和类型导出入口。模型目录的改动经常会影响这些包级导出，因此需要关注 `packages/database/src/index.ts` 或类似 barrel 文件是否暴露了相关模型。

## 核心对象

`models` 中的核心对象通常是按领域命名的 Model 类或工厂对象，例如围绕 user、session、message、topic、file、agent、knowledge base、plugin/tool 等业务实体组织。每个 Model 的职责不是复刻单表 CRUD，而是为一个领域聚合提供稳定的数据访问 API。

一个典型 Model 会持有数据库连接或事务上下文，并提供若干方法：读取列表、读取详情、按用户隔离查询、创建记录、局部更新、软删除或级联删除。由于 LobeHub 是多用户、多端、多工作区语义的产品，模型方法通常需要显式处理 `userId`、`sessionId`、`topicId`、`messageId` 等作用域字段，避免跨用户或跨会话读写。

另一个重要对象是 Drizzle 查询构造本身。虽然它不一定在 `models` 中作为独立类存在，但模型方法会大量依赖 `packages/database/src/schemas` 导出的表对象、`eq`、`and`、`inArray`、`desc`、`sql` 等查询工具。这里的核心不是 SQL 字符串，而是类型化查询：字段、返回值和插入值应尽量来自 schema 推导类型。

## 运行流程

一次典型读操作从接口层开始。前端通过 client service 调用 TRPC 或 Web API，`src/server/routers` 接收请求并完成参数校验，然后交给 `src/server/services`。服务层根据当前用户、功能开关、业务规则和请求参数决定要读取什么数据，再调用 `packages/database/src/models` 中对应模型的方法。Model 方法基于 schema 构造 Drizzle 查询，最终由数据库连接执行并返回结构化结果。

写操作类似，但多一步业务一致性处理。服务层负责判断是否允许写入，模型层负责把写入动作落到正确表上。如果涉及多个表，例如删除会话时同时处理 topics、messages、关联表或资源引用，模型层可能会使用事务或分步骤查询保证一致性。根据当前片段推断，复杂写入应优先放在模型或 repository 层集中处理，而不是让多个 server service 各自拼装同一组 SQL。

模型返回的数据通常不会直接成为前端最终结构。服务层还可能做权限裁剪、DTO 转换、默认值补齐、错误映射和缓存失效。也就是说，`models` 关注“数据库里怎么取、怎么改”，`server services` 关注“这个业务动作为什么允许、要返回什么”。

## 上下游依赖

上游主要是服务端业务层：`src/server/services`、`src/server/routers/lambda`、`src/server/routers/async`、`src/server/routers/mobile`、`src/app/(backend)` 下的 API route。它们依赖模型层完成真实数据库访问，但不应该把 Drizzle 查询细节扩散到调用侧。

下游主要是 `packages/database/src/schemas`、数据库连接实例、Drizzle ORM 和 PostgreSQL。模型层对 schema 的字段名、表关系、索引设计高度敏感；schema 变化如果没有同步更新模型，会直接导致类型错误、运行时查询错误或数据语义偏差。

横向依赖包括 `packages/database/src/repositories`、包内类型定义、测试文件和迁移文件。新增字段或表时，通常需要按顺序考虑 schema、migration、model、repository、server service、测试和导出入口。对于云端特性，还要注意 cloud override 机制：项目说明中提到 cloud repo 的 `src/` 和 `packages/business/` 可能覆盖开源核心，因此模型变更可能被云端服务间接依赖。

## 修改时最容易踩的坑

第一类坑是用户隔离条件遗漏。LobeHub 的很多数据都属于某个用户或会话，模型查询如果只按 `id` 查询，而没有同时带上 `userId` 或上层授权边界，就可能产生越权读取或误删。

第二类坑是把业务编排塞进模型。模型层适合封装数据库动作，但不适合承载接口协议、UI 状态、订阅策略或复杂产品规则。判断“用户是否有权限使用某功能”通常应在 server service；判断“如何高效查询这批记录”才属于 model。

第三类坑是 schema 改了但迁移、类型和模型没有一起改。Drizzle 类型可以挡住一部分字段错误，但数据库真实结构仍依赖 migration。新增列、重命名列、调整唯一索引或外键时，要同步检查模型里的插入默认值、排序字段、过滤条件和冲突处理。

第四类坑是事务边界不清。跨多张表的写操作如果拆散在多个服务或多个模型调用里，失败时容易留下半完成状态。涉及级联创建、删除、批量更新、计数同步的逻辑，应优先考虑事务或集中封装。

第五类坑是返回过宽数据。模型层为了方便返回整行记录，可能把上层不需要的字段也带出。对于用户配置、密钥、同步状态、内部标记等敏感字段，应在模型或服务层明确选择字段，避免向 API 响应链路泄漏。

## 推荐阅读顺序

1. 先读 `packages/database/src/schemas`，理解核心表、字段、索引和关系，这是理解模型方法的前提。
2. 再读 `packages/database/src/models` 的入口文件或导出文件，确认有哪些领域模型，以及上层应该如何实例化或引用它们。
3. 选择一两个高频领域模型阅读，例如会话、消息、用户、文件或知识库相关模型，重点看方法命名、作用域参数和事务写法，不需要逐行追 SQL。
4. 对照 `src/server/services` 中调用这些模型的服务，理解模型方法在真实业务流程中的位置。
5. 最后查看相关测试和 migration，确认模型行为如何被验证，以及 schema 变化如何落到数据库。
