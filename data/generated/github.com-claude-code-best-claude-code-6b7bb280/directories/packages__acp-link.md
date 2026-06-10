# 目录：packages/acp-link

## 它负责什么

`packages/acp-link` 是一个把 WebSocket 客户端连接转成 ACP Agent Client Protocol 代理的独立包。根据 `package.json` 和 `README.md`，它既能作为命令行程序 `acp-link` 运行，也能作为库输出 `dist/server.js`。它的核心职责有三层：一是启动代理服务，把前端或外部客户端的消息转给 ACP agent 子进程；二是提供 `--manager` 模式，用一个小型 Web UI 管理多个 `acp-link` 子进程实例；三是支持远程控制场景里的 RCS upstream 注册和转发。根据当前片段推断，这个目录更像是“协议桥接层 + 进程管理层”的组合，而不是单纯的 CLI 工具。

## 直接子目录地图

这个目录下真正有内容的直接子目录只有几个，结构很集中：

- `src/cli/`，放命令行入口相关代码，负责参数解析、模式分流和启动。
- `src/manager/`，放 Manager Web UI 及其后端逻辑，负责创建、停止、删除和查看多个子进程实例。
- `src/__tests__/`，放单元测试，覆盖证书、服务端和类型约束这类基础能力。

除此之外，`src/` 下还有若干平级模块，承担主流程中的支撑角色，比如认证、消息解码、证书、日志和 RCS 上游连接。它们不是子目录，但在整体流程里很关键。

## 关键入口

最直接的运行入口是 `src/cli/bin.ts`。它是一个标准 node 可执行脚本，调用 `@stricli/core` 的 `run()`，再把参数交给 `src/cli/app.ts` 组装出的应用对象。

CLI 的真正分发逻辑在 `src/cli/command.ts`。这里定义了 `--port`、`--host`、`--debug`、`--no-auth`、`--https`、`--manager`、`--group` 这些 flag，并在执行体里分成两条路：

- `--manager` 为真时，直接导入 `../manager/index.js`，启动管理界面。
- 否则要求给出 agent 命令，然后初始化 token、logger，最后进入 `../server.js` 的代理服务。

从包层面看，`package.json` 里的 `bin.acp-link = dist/cli/bin.js` 是对外入口，`main = ./dist/server.js` 则说明这个包也保留了服务端能力的直接导出。

## 主流程位置

主流程基本都收敛在 `src/server.ts`。这是最值得看的地方。

它的核心思路是，维护一份客户端状态 `ClientState`，收到连接后再按消息类型驱动 ACP 会话生命周期。流程大致是：

1. 校验 WebSocket 认证，认证逻辑分别在 `src/ws-auth.ts`，消息大小和 JSON 解析在 `src/ws-message.ts`。
2. 如果不是 `--manager`，就用 `child_process.spawn()` 启动 agent 命令，把 `stdin/stdout` 包成 ACP `ndJsonStream`。
3. 用 `@agentclientprotocol/sdk` 建立 `ClientSideConnection`，执行 `initialize()`，拿到 agent 能力、模型状态和会话能力。
4. 进入消息处理分支，支持 `connect`、`new_session`、`prompt`、`list_sessions`、`load_session`、`resume_session`、`cancel`、`set_session_model` 等动作。
5. 在权限请求、会话更新、session 列表、模型切换这些关键动作上，通过 `send(ws, ...)` 把状态同步回客户端。
6. 如果配置了 RCS 上游，还会走 `src/rcs-upstream.ts`，先 REST 注册，再建立 WS 连接，把本地事件转发到远端。

其中，`src/rcs-upstream.ts` 是另一条重要支线。它处理 `ACP_RCS_URL`、`ACP_RCS_TOKEN`、`ACP_RCS_GROUP` 这些外部配置，负责把这个代理实例挂到远程控制服务器上。`src/cert.ts` 则服务于 `--https` 场景，提供自签名证书和局域网 IP 探测。

Manager 模式则是另一套闭环。`src/manager/index.ts` 启动 Hono 服务，`src/manager/routes.ts` 提供页面、实例列表、创建、停止、删除和 SSE 日志流接口，`src/manager/manager.ts` 负责真正的进程生命周期管理。根据当前片段推断，这一层的核心不是协议转发，而是“把多个 `acp-link` 当成可视化实例来编排”。

## 推荐阅读顺序

1. 先看 `README.md`，建立使用场景和两个模式的整体印象。
2. 再看 `src/cli/bin.ts`、`src/cli/app.ts`、`src/cli/command.ts`，确认入口参数如何流向不同模式。
3. 接着看 `src/server.ts`，这是代理主线，先理解连接建立，再看 session、prompt、permission。
4. 然后看 `src/ws-auth.ts`、`src/ws-message.ts`、`src/cert.ts`、`src/logger.ts`，补齐基础设施。
5. 如果关心远程控制，再读 `src/rcs-upstream.ts`。
6. 最后看 `src/manager/index.ts`、`src/manager/routes.ts`、`src/manager/manager.ts`，理解 Manager 子系统。

## 常见误区

- 容易把 `--manager` 当成代理的一部分，其实它是完全不同的运行模式，启动后不要求 agent 命令。
- 容易忽略 `src/server.ts` 里的会话状态机，这个文件不只是转发 WebSocket，还负责 agent 进程重启、权限超时、session 恢复和模型切换。
- 容易把 `src/rcs-upstream.ts` 看成可选附件，但它实际上是远程接入场景的关键通道。
- 容易只看 CLI 参数，不看 `ws-auth.ts` 和 `ws-message.ts`，结果会漏掉认证方式和消息边界控制。
- 容易误以为 Manager UI 是静态页面，其实它背后还有 `ProcessManager` 和 SSE 日志流，属于完整的进程控制面。
