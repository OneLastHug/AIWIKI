# 文件：packages/coding-agent/src/modes/rpc/rpc-types.ts
## 一句话定位
这个文件是 `coding-agent` 的 RPC 协议类型契约层，专门定义“头less 模式”下 stdin/stdout 之间交换的命令、响应、扩展 UI 请求，以及会话状态和可执行斜杠命令的结构。根据当前片段推断，它本身不承载业务逻辑，只负责把协议边界固定下来，供 `rpc-mode.ts` 和 `rpc-client.ts` 双向共享。

## 它暴露/定义了什么
它导出了几组核心联合类型和接口：`RpcCommand` 描述所有可从 stdin 送入的命令；`RpcResponse` 描述所有 stdout 返回的响应；`RpcExtensionUIRequest` / `RpcExtensionUIResponse` 描述扩展 UI 的请求回传；`RpcSessionState` 描述 `get_state` 的快照；`RpcSlashCommand` 描述可通过 prompt 调用的命令；`RpcCommandType` 则是 `RpcCommand["type"]` 的便捷别名。这里的命令面很宽，覆盖 prompt、模型切换、thinking level、队列模式、compaction、retry、bash、会话管理、消息读取和命令枚举。

## 谁调用它
直接消费者主要是 `packages/coding-agent/src/modes/rpc/rpc-mode.ts` 和 `packages/coding-agent/src/modes/rpc/rpc-client.ts`。前者把这些类型当作服务端协议来收发 JSONL，后者把它们当作客户端 API 的类型底座。间接上，`packages/coding-agent/src/modes/index.ts` 和 `packages/coding-agent/src/index.ts` 也在重新导出这些类型，说明它们面向包外使用，而不是 RPC 模块内部私有实现。

## 它调用谁
这个文件没有运行时调用链，只有类型层面的依赖。它引用了 `@earendil-works/pi-agent-core` 的 `AgentMessage`、`ThinkingLevel`，`@earendil-works/pi-ai` 的 `ImageContent`、`Model`，以及 `core` 层的 `SessionStats`、`BashResult`、`CompactionResult`、`SourceInfo`。也就是说，它把底层领域对象嵌进 RPC 协议里，但不负责生成这些对象。

## 核心流程
RPC 的主流程可以概括为“命令进来，响应出去，中间穿插事件和扩展 UI 交互”。命令从 stdin 进入后，由 `rpc-mode.ts` 解析成 `RpcCommand`，再路由到具体处理分支；处理成功时返回对应的 `RpcResponse`，失败时返回带 `error` 的统一错误响应。某些动作不是一次性完成，而是会先发出 `RpcExtensionUIRequest`，等待外部客户端用 `RpcExtensionUIResponse` 回填。`get_state`、`get_commands`、`get_messages` 这类查询型命令则把会话快照、可用命令和消息数组直接封装进响应数据里。

## 关键函数的高层作用
这个文件里没有业务函数，只有一个小型辅助类型 `RpcCommandType`，作用是给调用方提供“所有命令类型字符串”的联合类型，方便做分发、校验或映射表键。真正的核心不是函数，而是几组联合类型的设计：它们用 `type`、`command`、`success`、`data` 这些离散字段把协议做成可判别联合，便于 `rpc-mode.ts` 和 `rpc-client.ts` 在编译期完成穷尽检查。

## 修改风险
这里的改动风险很高，因为它等同于协议变更。新增、删除或改名任一命令字段，都会同步影响 `rpc-mode.ts` 的分支处理、`rpc-client.ts` 的发送与解析逻辑，以及包外通过 `index.ts` 暴露的 API。尤其是 `type`、`command`、`success` 这些判别字段，一旦不一致就会导致 JSON 解析后无法正确分派。另一个高风险点是数据形状，例如 `RpcSessionState`、`RpcSlashCommand`、`RpcExtensionUIRequest` 的字段增减，会直接影响外部集成方和测试基线。根据当前片段推断，这个文件更像协议版本边界，改动时应按“接口破坏”来评估。
