# 目录：src/gateway/protocol

## 它负责什么

`src/gateway/protocol` 是 OpenClaw Gateway 的“线协议契约”目录，负责定义 operator client、节点、Gateway 之间通信时可见的数据结构、方法参数、事件帧、响应形状和运行时校验规则。这里的代码不应该被理解成某个具体 Gateway server 的业务实现，而是所有相关客户端和服务端共同依赖的协议边界。

从 scoped `AGENTS.md` 可以看出，这个目录的变更被视为 protocol change，而不是普通局部重构。新增 Gateway method、event 或 payload field，原则上应先落在这里的 typed protocol definition 中，再由运行时、客户端、文档和测试跟进。目录也强调 data-first、acyclic：协议模块应保持轻量，不能反向依赖更重的 gateway runtime 或 server method helper，避免导入顺序和运行时成本变得脆弱。

整体上，这里做三件事：第一，用 TypeBox schema 描述 wire payload；第二，用 TypeScript type 把 schema 暴露给调用方；第三，在 `index.ts` 里用 Ajv 等机制把协议 schema 组织成可校验、可枚举、可分发的公共接口。

## 直接子目录地图

`src/gateway/protocol/schema` 是唯一直接子目录，承载协议 schema 的主体。它按领域拆分文件，而不是按单个 endpoint 拆到很碎：例如 `agent.ts` 处理 agent 事件和基础 agent 请求，`agents-models-skills.ts` 覆盖 agents、models、skills、tools 相关接口，`channels.ts` 覆盖 channel/talk/web login 等通信能力，`sessions.ts` 覆盖 session lifecycle 和消息订阅，`nodes.ts` 覆盖节点配对、调用和 pending queue，`config.ts` 覆盖配置读取、修改、schema lookup 和更新动作，`frames.ts` 定义连接、请求、响应、事件等外层 frame。

同一子目录还包含较横向的协议基础件：`primitives.ts` 放通用原语，`types.ts` 放共享类型工具，`error-codes.ts` 和 `frames.ts` 共同约束错误与帧形状，`protocol-schemas.ts` 聚合各领域 schema，`snapshot.ts` 描述状态快照。其余文件如 `artifacts.ts`、`cron.ts`、`devices.ts`、`environments.ts`、`exec-approvals.ts`、`plugin-approvals.ts`、`plugins.ts`、`push.ts`、`secrets.ts`、`tasks.ts`、`wizard.ts` 分别对应 Gateway 暴露的功能面。

根层没有更多业务子目录，主要是聚合入口、版本和少量协议辅助文件，例如 `client-info.ts`、`connect-error-details.ts`、`startup-unavailable.ts`、`version.ts`，以及若干 colocated test。

## 关键入口

最重要的入口是 `src/gateway/protocol/index.ts`。它大量导入 `schema/*.ts` 中的 TypeBox schema 和对应 type，并结合 `ajv` 做运行时校验。根据当前片段推断，调用方如果需要“完整 Gateway 协议能力”，通常会从这里获取方法定义、事件定义、frame schema、validator 或协议级类型，而不是直接拼接 JSON。

`src/gateway/protocol/schema.ts` 是 schema 层的 barrel export。它把 `schema/agent.ts`、`schema/channels.ts`、`schema/config.ts`、`schema/frames.ts`、`schema/sessions.ts` 等全部重新导出，适合只需要 schema/type 定义而不需要完整 `index.ts` 聚合逻辑的调用方。

`src/gateway/protocol/schema/protocol-schemas.ts` 是 schema 注册表式入口。它从各领域文件导入大量 `*Schema`，用于把“分散定义的协议形状”汇总成更高层的 protocol schema 集合。阅读它能快速看到 Gateway 当前有哪些主要方法族和事件族。

`src/gateway/protocol/version.ts` 是协议版本相关入口。由于 scoped 规则明确说 incompatible change 需要显式 versioning，并更新所有受影响客户端，所以涉及 wire contract 兼容性时应把它和 `frames.ts`、`index.ts`、相关测试一起看。

## 主流程位置

协议主流程可以按“定义 -> 聚合 -> 校验 -> 使用”理解。

定义层在 `src/gateway/protocol/schema/*.ts`。每个领域文件通常同时给出 schema 和 TypeScript 类型，例如 params、result、event、summary、entry 等数据形状。这里是判断字段是否属于公共协议的第一站。

聚合层有两个：`src/gateway/protocol/schema.ts` 做模块导出聚合，`src/gateway/protocol/schema/protocol-schemas.ts` 做 schema 集合聚合。前者偏给 TypeScript import 使用，后者偏给协议注册、校验和生成类任务使用。

校验和协议运行时辅助集中在 `src/gateway/protocol/index.ts`。该文件导入 Ajv，并导入几乎所有 schema，说明它是把 TypeBox schema 转为实际 validator、协议方法表或事件校验入口的位置。根据当前片段推断，Gateway server、客户端 SDK、测试或生成物会依赖这里来保证请求、响应、事件帧符合契约。

外层消息主干在 `src/gateway/protocol/schema/frames.ts`。`ConnectParamsSchema`、`HelloOkSchema`、`RequestFrameSchema`、`ResponseFrameSchema`、`EventFrameSchema`、`GatewayFrameSchema` 等名字显示，它定义了 wire 上最外层的连接握手、请求、响应、事件和错误结构。要理解“一个 Gateway 消息长什么样”，应优先看这里。

测试是协议主流程的重要保护层。根层的 `index.test.ts`、`connect-error-details.test.ts`、`native-protocol-levels.guard.test.ts`、`talk-config.contract.test.ts`，以及 schema 子目录下的 `agent.test.ts` 等，主要用于锁定公共契约和边界行为。协议目录的测试不是普通实现细节测试，而是兼容性证据的一部分。

## 推荐阅读顺序

1. 先读 `src/gateway/protocol/AGENTS.md`，明确这个目录是公共 wire contract，schema 变更需要同步文档、测试和客户端产物。
2. 再读 `src/gateway/protocol/schema/frames.ts`，建立 Gateway frame、request、response、event、error 的外层模型。
3. 读 `src/gateway/protocol/schema/protocol-schemas.ts`，从聚合清单快速掌握协议覆盖的功能域。
4. 按关注面选择领域 schema：会话看 `src/gateway/protocol/schema/sessions.ts`，节点看 `src/gateway/protocol/schema/nodes.ts`，channel/talk 看 `src/gateway/protocol/schema/channels.ts`，配置看 `src/gateway/protocol/schema/config.ts`，插件能力看 `src/gateway/protocol/schema/plugins.ts` 和 `src/gateway/protocol/schema/plugin-approvals.ts`。
5. 回到 `src/gateway/protocol/index.ts`，理解这些 schema 如何被统一导入、校验和暴露。
6. 最后看相关 `*.test.ts`，确认哪些字段、错误码、协议级行为已经被测试锁定。

## 常见误区

不要把 `src/gateway/protocol` 当作 Gateway server 实现目录。这里定义的是协议契约，不负责真正执行 session、plugin、node 或 channel 的业务逻辑。

不要绕过这里在 runtime 中临时拼 ad hoc JSON。scoped 规则明确要求新的 Gateway method、event 或 payload field 通过这里的 typed protocol definitions 落地。

不要把 schema 变更当作只影响 TypeScript 的内部重构。字段新增、删除、含义变化、默认值变化、错误形状变化，都可能影响客户端、节点、文档、测试和生成产物。

不要只改某个领域 schema 而忘记聚合入口。新增公开 schema 往往需要同步 `src/gateway/protocol/schema.ts`、`src/gateway/protocol/schema/protocol-schemas.ts`、`src/gateway/protocol/index.ts` 以及对应测试。

不要让协议模块依赖重型 runtime。这个目录要求 data-first 和 acyclic，协议层应被 runtime 使用，而不是反向绑定 runtime 实现细节。

不要忽视版本和兼容性。scoped 规则强调 prefer additive evolution；不兼容变更需要显式 versioning 和客户端跟进。对于公开 wire contract，最安全的阅读姿势是把 schema、validator、测试、文档视为同一份契约的不同投影。
