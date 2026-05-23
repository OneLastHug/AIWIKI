# 文件：packages/database/src/index.ts

## 一句话定位

这是 `@lobechat/database` 包的总入口文件，作用是把数据库层最常用的能力统一对外暴露出去，让上层代码通过一个稳定的包入口拿到数据库实例、仓库类、类型和 ID 工具。根据 `packages/database/package.json`，包根入口 `.` 就指向这里。

## 它暴露/定义了什么

这个文件本身不实现业务逻辑，只做四组聚合导出：

- `./core/db-adaptor`：提供 `getServerDB`、`serverDB`
- `./repositories/compression`：提供 `CompressionRepository` 及其相关参数/结果类型
- `./type`：提供 `LobeChatDatabase`、`Transaction` 等数据库类型
- `./utils/idGenerator`：提供 `createNanoId`、`idGenerator`、`randomSlug`、`inboxSessionId`

所以它更像一个“门面层”，把数据库包里最常被外部使用的对象集中到一个入口。

## 谁调用它

根据当前仓库中的引用情况，调用方主要是上层服务和路由层，而不是数据库包内部。例如：

- `src/libs/better-auth/define-config.ts`
- `src/app/(backend)/oidc/clear-session/route.ts`
- `src/server/services/message/index.ts`
- `src/server/services/*` 下大量业务服务
- `src/server/routers/lambda/**` 和对应测试
- 其他包，如 `packages/memory-user-memory/src/**`

其中一个很典型的消费点是 `src/server/services/message/index.ts`，它直接从 `@lobechat/database` 引入 `CompressionRepository`。很多地方也只取类型，比如 `LobeChatDatabase`，用来约束服务层的数据库参数。

## 它调用谁

它不直接调用任何业务函数；`export * from ...` 只是把子模块的导出透传出去。真正被加载和执行的是它转出的模块：

- `core/db-adaptor` 内部会触发 `getDBInstance`
- `repositories/compression` 内部会访问 `messageGroups`、`messages` 以及 `drizzle-orm` 查询构造器
- `utils/idGenerator` 内部会用 `nanoid/non-secure` 和 `random-words`
- `type` 只导出类型，不会产生运行时逻辑

所以严格说，这个文件本身不“调用”下游，只是建立了一个统一入口。

## 核心流程

1. 上层代码通过 `@lobechat/database` 进入数据库包。
2. 入口文件把所需能力从内部模块重新导出。
3. 业务层按需拿到：
   - 数据库实例：`serverDB`、`getServerDB`
   - 仓库能力：`CompressionRepository`
   - 类型：`LobeChatDatabase`、`Transaction`
   - ID/slug 工具：`idGenerator` 等
4. 这些能力再被服务层、路由层、测试层组合使用，完成读写数据库、压缩消息、生成业务 ID 等工作。

## 关键函数的高层作用

这里要说明的是，这个文件**没有自己的函数定义**，关键能力来自它转出的模块：

- `getServerDB`：按环境懒加载数据库实例，避免模块一被 import 就立刻初始化连接。
- `serverDB`：直接暴露一个已解析的数据库实例，适合启动期或确定环境下使用。
- `CompressionRepository`：封装消息压缩相关操作，包括创建压缩组、查询压缩组、更新元数据、标记/取消标记消息、删除压缩组。
- `idGenerator` / `createNanoId` / `randomSlug`：生成带前缀的业务 ID 或可读 slug，减少各业务模块自己拼接 ID 的重复代码。
- `LobeChatDatabase` / `Transaction`：为服务层和测试提供统一的数据库类型约束。

## 修改风险

这个文件看起来很薄，但改动风险并不小，因为它是包级公开 API 的汇总点：

- 改导出路径会直接影响所有 `@lobechat/database` 的调用方。
- 删除或重命名导出会造成大量编译错误，尤其是服务层和测试代码。
- 新增导出看似无害，但会扩大包的公开面，后续就要承担兼容性维护。
- 如果调整 `packages/database/package.json` 的 `exports` 配置，这个入口会立刻变成全包消费链路的核心断点。
- 根据当前片段推断，很多上层模块依赖它做类型引入和实例获取，因此这类改动最好先检查全仓库引用，再做同步调整。
