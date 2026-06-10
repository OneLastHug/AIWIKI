# 文件：src/gateway/protocol/index.ts

## 一句话定位

`src/gateway/protocol/index.ts` 是 Gateway 协议的运行时入口：它把 `src/gateway/protocol/schema.ts` 及其下游 TypeBox schema 暴露成统一的类型、schema、AJV validator、错误码和错误格式化工具，供 WebSocket Gateway、server methods、CLI/TUI/UI、插件 SDK 相关边界共同使用。

## 它暴露/定义了什么

这个文件主要暴露四类内容。第一类是协议类型和常量，例如 `RequestFrame`、`ResponseFrame`、`EventFrame`、`ConnectParams`、`ErrorShape`、`ErrorCodes`、`PROTOCOL_VERSION`、`MIN_CLIENT_PROTOCOL_VERSION`。第二类是 TypeBox schema 的再导出，例如 `RequestFrameSchema`、`SessionsSendParamsSchema`、`TalkSessionCreateParamsSchema`、`ToolsInvokeParamsSchema`。第三类是 AJV runtime validators，命名统一为 `validateXxx`，例如 `validateRequestFrame`、`validateConnectParams`、`validateSessionsPatchParams`、`validateNodeInvokeResultParams`。第四类是 `formatValidationErrors`，用于把 AJV 的结构化错误压缩成可读的协议错误消息。

它本身不定义业务协议字段，字段来源主要是 `src/gateway/protocol/schema.js`；本文件更像“协议门面 + runtime validator 注册表”。

## 谁调用它

调用者分布很广，说明它是 Gateway wire contract 的中心出口。核心 Gateway 侧包括 `src/gateway/client.ts`、`src/gateway/call.ts`、`src/gateway/server.auth.shared.ts`、`src/gateway/server-methods.ts`、`src/gateway/server/ws-connection/message-handler.ts`、`src/gateway/server-methods/*`。这些模块用它校验请求参数、构造错误、声明帧类型、检查协议版本。

上层客户端和界面也依赖它：`src/tui/*`、`ui/src/ui/chat/slash-commands.ts`、`src/commands/*`、`src/cli/*` 会引用命令、会话、错误或版本相关类型。插件/SDK 边界中，`src/plugin-sdk/gateway-runtime.ts` 会再导出 `ErrorCodes`、`errorShape`、`EventFrame`，把部分 Gateway 协议能力传给插件作者可见的 runtime 表面。测试和文档也把它当成协议事实来源，例如 `docs/concepts/typebox.md` 明确把 runtime validators 指向此文件。

## 它调用谁

它直接依赖 `ajv` 做 JSON schema runtime validation；依赖 `../../shared/string-normalization.js` 的 `uniqueStrings` 去重错误文本；依赖 `../session-utils.types.js` 的 `SessionsPatchResult` 类型；大量依赖 `./schema.js` 导入 TypeBox schema、类型、错误码、版本常量和 `ProtocolSchemas`。根据当前片段推断，`./schema.js` 是由 `src/gateway/protocol/schema.ts` 聚合导出的协议定义层，本文件只把这些定义转成运行时可调用的验证函数。

## 核心流程

协议数据进入 Gateway 或相关调用点后，调用方选择对应的 `validateXxx` 函数验证输入或输出。首次使用某个 validator 时，`lazyCompile` 才会通过共享的 AJV 实例编译对应 schema；后续调用复用已编译函数。校验失败时，调用方可以读取 validator 的 `errors`，再用 `formatValidationErrors` 生成稳定、去重、面向人的错误描述。对于协议消费者，整个流程是：schema 定义在 `schema/*`，本文件生成 validator，Gateway/server-method/client 调用 validator，错误通过 `ErrorCodes`、`errorShape` 和格式化文本返回到 wire/API 边界。

## 关键函数的高层作用

`getAjv` 负责懒加载单例 AJV，配置为 `allErrors: true`、`strict: false`、`removeAdditional: false`。这意味着它倾向于一次报告多个问题，不自动删除额外字段，也不会因 TypeBox/JSON schema 的非严格细节在导入期失败。

`lazyCompile` 是本文件的核心封装。它返回一个看起来像 AJV `ValidateFunction` 的函数，但真正的 schema 编译推迟到第一次校验时发生。它还代理 `errors`、`evaluated`、`schema`、`schemaEnv`、`source` 等属性，保持与 AJV validator 调用方的兼容。这样可以避免模块加载时一次性编译大量协议 schema，降低 Gateway 或客户端导入成本。

`formatValidationErrors` 负责把 AJV `ErrorObject[]` 转成人类可读字符串。它特别处理 `additionalProperties`，输出类似 “unexpected property” 的信息；其他错误则拼接 `instancePath` 和 AJV message；最后用 `uniqueStrings` 去重并保序。辅助性的 `validateXxx` 导出只是把某个 schema 绑定到 `lazyCompile`，职责明确但不承载额外业务逻辑。

## 修改风险

这里属于 Gateway 协议边界，风险高于普通内部模块。新增、删除或改名任何 `validateXxx`、schema 再导出、类型再导出，都可能影响 Gateway server methods、CLI/TUI/UI、插件 SDK、测试和文档。尤其是 `RequestFrame`、`ResponseFrame`、`EventFrame`、`ConnectParams`、版本常量、`ErrorCodes`、`ErrorShape` 这类 wire contract 相关导出，变更可能导致新旧客户端握手失败、节点/操作端不兼容，或插件可见 API 破坏。

修改 AJV 配置也有兼容风险。比如开启 strict、改变 `removeAdditional`、调整错误收集策略，会改变当前请求是否被接受以及错误文本形态，进而影响 server-method validation、测试断言和用户可见诊断。修改 `lazyCompile` 的属性代理要小心，因为调用方可能依赖 `validator.errors` 的 AJV 语义。修改 `formatValidationErrors` 看似只是文案，但它会影响错误响应、日志、CLI/UI 提示和测试。

如果要新增协议方法或字段，正确路径通常不是只改本文件，而是同步更新 `src/gateway/protocol/schema.ts` 或 `src/gateway/protocol/schema/*`、本文件 validator/export、相关 server methods、客户端调用点、`docs/gateway/protocol.md` 以及协议测试。 scoped `AGENTS.md` 也明确要求协议变更优先 additive；不兼容变更需要显式版本处理，并同步所有受影响客户端。
