# 目录：packages/database/src/models/userMemory

## 它负责什么

`packages/database/src/models/userMemory` 位于 `packages/database` 的数据库访问层，也就是项目数据流中的 “DB Model” 位置。按照仓库约定，前端或服务端业务不会直接拼 SQL，而是通过 Server Service、TRPC Router 等上层入口调用 `packages/database/src/models/*` 里的模型类，再由模型类使用 Drizzle ORM 访问 PostgreSQL。

这个目录关注的是 **用户记忆 User Memory** 的持久化读写。它不是前端记忆面板，也不是记忆抽取算法本身，而是把已经形成的记忆数据落库、查询、更新、删除，并为上层提供稳定的数据访问 API。根据当前片段推断，相关上游包括 `src/services/userMemory`、`src/store/userMemory`、`src/hooks/useFetchMemoryForTopic.ts`，以及记忆能力包 `packages/memory-user-memory`、内置工具包 `packages/builtin-tool-memory`。这些路径说明 “User Memory” 在系统中横跨 UI 状态、客户端服务、工具调用、记忆处理包和数据库模型，而本目录只承担其中靠近数据库的一段。

从职责边界看，`userMemory` model 通常处理以下问题：按 `userId` 隔离数据、按 topic/session 等上下文查询相关记忆、创建或更新记忆条目、软删除或清理无效记忆、给上层返回结构化的 memory 记录。它依赖 `packages/database/src/schemas` 中定义的表结构，而不是自己定义数据库 schema。

## 直接子目录地图

这是一个偏小的 model 目录，重点不是复杂的子目录分层，而是一个围绕 `UserMemoryModel` 的模型入口。根据当前片段推断，它下面大概率没有多层业务子目录，主要由入口文件和可能的类型、测试或辅助文件组成。

可按角色理解为：

- `packages/database/src/models/userMemory`：用户记忆数据库模型目录，封装 User Memory 的 CRUD、列表查询、上下文检索等持久化操作。
- `packages/database/src/models`：数据库模型层的同级目录，通常每个业务实体一个 model，例如 message、topic、session、file 等；`userMemory` 与它们处在同一抽象层。
- `packages/database/src/schemas`：表结构来源。`userMemory` model 不应被理解为 schema 定义目录，真正的列、索引、外键、时间戳等定义要回到 schemas 查。
- `packages/database/tests` 或相邻测试目录：数据库包测试位置。若要确认 model 行为，要找对应 user memory 的测试或上层服务测试。

由于本次只做地图式概览，不逐文件展开；如果目录内只有 `index.ts` 一类入口文件，可以把它视为整个目录的主要阅读对象。

## 关键入口

最关键的入口是 `packages/database/src/models/userMemory/index.ts`，通常这里会导出 `UserMemoryModel` 或同等命名的模型类。这个类是上层访问用户记忆数据的主要门面：构造时接收数据库连接或执行上下文，方法内部组合 Drizzle 查询条件，并返回业务层需要的数据结构。

第二类入口是数据库包的聚合导出。根据 LobeHub 的项目结构，`packages/database/src/models` 往往会通过各 model 目录暴露模型类，上层再从数据库包或 server-side context 中拿到这些模型。阅读时不要只盯着 `userMemory` 目录本身，还要顺着 `packages/database/src/models` 的导出关系确认它如何被外部引用。

第三类入口是 schema。虽然目标目录是 model，但理解字段含义必须回看 `packages/database/src/schemas` 中与 user memory 相关的表定义，尤其是记录主键、`userId`、内容字段、来源字段、时间字段、状态字段、索引和唯一约束。model 中很多查询条件只有结合 schema 才能看懂，例如为什么按某个字段排序、为什么 upsert 时使用某组 key。

第四类入口是上游调用方。`src/services/userMemory` 更接近客户端或 API 服务封装，`src/store/userMemory` 更接近前端 Zustand 状态，`packages/memory-user-memory` 更接近记忆生成、整理或领域逻辑，`packages/builtin-tool-memory` 则可能把记忆能力暴露为 agent 可调用工具。这些入口能帮助判断 model 方法为什么这样设计。

## 主流程位置

主流程可以按 “产生记忆、写入记忆、读取记忆、展示或注入上下文” 四段理解。

第一段是记忆产生。用户聊天、主题上下文或工具执行过程中，上层逻辑会识别出需要保存的长期偏好、事实或上下文。这个阶段更可能发生在 `packages/memory-user-memory`、agent runtime、server service 或工具包中，不属于 `userMemory` model 的职责。

第二段是写入数据库。上层拿到结构化 memory 后，会调用数据库模型，例如 `UserMemoryModel` 的 create、batch create、update、upsert 或 delete 类方法。这里是 `packages/database/src/models/userMemory` 的核心位置：它负责把业务参数转换成 Drizzle 查询，确保按用户隔离，并把写入结果返回给调用方。

第三段是查询和过滤。当前会话、某个 topic、记忆管理页面或 agent 上下文构造过程需要读取用户记忆时，会从 service/router 进入 model 查询。常见查询维度可能包括 `userId`、记忆分类、记忆内容、更新时间、是否有效、关联 topic 或 session。根据当前片段推断，`src/hooks/useFetchMemoryForTopic.ts` 表明至少存在 “按 topic 拉取相关 memory” 的使用场景。

第四段是消费。读出的 memory 会进入两个方向：一是前端记忆管理界面，通过 `src/store/userMemory` 做列表、编辑、删除等状态管理；二是 agent 或聊天上下文构造，把用户长期记忆注入模型提示词或工具链。`packages/builtin-tool-memory` 的存在说明记忆还可能通过内置工具被 agent 查询或写入。

所以主流程位置不是单点文件，而是一条链路：`src/store/userMemory` 或 UI 操作 → `src/services/userMemory` / TRPC 或 server service → `packages/database/src/models/userMemory` → `packages/database/src/schemas` 对应表 → PostgreSQL。agent 自动记忆场景则可能是 `packages/memory-user-memory` / `packages/builtin-tool-memory` → server service → `UserMemoryModel`。

## 推荐阅读顺序

1. 先读 `packages/database/src/schemas` 中 user memory 相关 schema。目标是弄清楚表结构、索引、字段含义和用户隔离方式。没有 schema 背景，model 方法名容易看懂，但查询约束不容易判断。

2. 再读 `packages/database/src/models/userMemory/index.ts`。重点看导出的模型类、构造参数、公开方法列表，以及每个方法对应的业务动作。overview 阶段不用逐行研究 SQL，只需要标出哪些方法负责创建、哪些负责查询、哪些负责更新或删除。

3. 接着看 `src/services/userMemory`。这里通常能看到 model 能力如何被包装给前端或 API 使用，也能看到参数命名和返回结构是否更接近产品语义。

4. 再看 `src/store/userMemory`。这一步用于理解 UI 层如何消费这些数据，例如列表刷新、乐观更新、删除后同步、编辑后重拉等。

5. 最后看 `packages/memory-user-memory` 和 `packages/builtin-tool-memory`。这两个目录更偏“记忆能力”而不是数据库模型。读它们可以理解 user memory 数据从哪里来，以及 agent 如何使用它。

## 常见误区

第一，不要把 `packages/database/src/models/userMemory` 当成完整的记忆系统。它只是数据库模型层，负责持久化访问；记忆抽取、总结、展示、权限入口、agent 工具调用都在其他目录。

第二，不要在 model 层寻找 UI 文案或交互逻辑。记忆列表、按钮、弹窗、空状态、i18n 文案通常属于 `src/features`、`src/store/userMemory`、`locales/*/memory.json` 等位置。

第三，不要绕过 model 直接在上层拼数据库查询。这个目录存在的意义就是集中封装 user memory 表访问，避免 server service、router、tool executor 到处复制 Drizzle 条件。

第四，不要只看方法名就判断业务含义。比如 update、delete、remove、clear 可能分别对应编辑内容、软删除、物理删除或批量清理，必须结合 schema 字段和调用方确认。

第五，不要忽略 `userId`。User Memory 是强用户隔离数据，所有读写都应围绕当前用户身份约束。若阅读时看到某个查询没有显式用户条件，需要继续追踪调用上下文，确认是否在更上层已经注入隔离条件。

第六，不要把 topic memory 和全局 user memory 混为一谈。`src/hooks/useFetchMemoryForTopic.ts` 暗示存在按 topic 获取记忆的路径，但这不等于所有记忆都绑定 topic。根据当前片段推断，系统可能同时支持全局长期记忆和会话/主题相关记忆，具体边界应以 schema 与 model 查询方法为准。

第七，注意目标路径在当前可见片段中存在路径解析不一致的迹象：给定目标是 `packages/database/src/models/userMemory`，而仓库搜索片段显示相关源码集中在 `packages/database`、`packages/memory-user-memory`、`src/services/userMemory`、`src/store/userMemory`。因此本文对目录内部文件数量和具体方法名只做 overview 级推断，精确细节应以实际检出的 `packages/database/src/models/userMemory` 内容为准。
