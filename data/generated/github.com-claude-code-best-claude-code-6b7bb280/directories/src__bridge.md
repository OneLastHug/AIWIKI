# 目录：src/bridge

## 它负责什么

`src/bridge` 是 Remote Control / Bridge 模式的核心目录，负责把本地 Claude Code 会话接到远端会话、环境工作队列或直接的 session-ingress / CCR 连接上。它同时覆盖两类运行形态：一种是常规的环境驱动桥接，也就是先注册 environment，再轮询 work、拉起子会话、回传结果；另一种是偏 REPL 的无环境层桥接，直接围绕 `v1/code/sessions` 和 `/bridge` 建立会话与传输。

如果只看职责边界，这个目录更像一套“桥接运行时”，而不是单纯的 API 封装。它既管鉴权、token 刷新、信任校验、版本门槛，也管消息转发、权限回调、结果调度、会话标题、崩溃恢复指针、后台 worker 运行等。根据当前片段推断，它是 `src/entrypoints/cli.tsx` 里 remote-control 快捷路径的实际落点之一。

## 直接子目录地图

这个目录结构很扁，直接子目录只有一个：

- `src/bridge/__tests__`：桥接行为测试，当前能看到的覆盖点包括消息处理、权限回调、结果调度、远程中断处理。

除此之外基本都是平级模块，没有再继续分层的深目录。也就是说，这里主要靠文件分工而不是目录分层。

## 关键入口

最重要的入口是 `src/bridge/bridgeMain.ts` 里的 `bridgeMain(args)`。它是命令行进入 Remote Control 的总调度点，负责参数解析、权限模式校验、配置初始化、trust 检查、OAuth 检查、远程对话提示、`--continue` 恢复、初始会话创建，以及最终把控制权交给运行循环。

第二个关键入口是 `src/bridge/bridgeMain.ts` 里的 `runBridgeHeadless(opts, signal)`。它面向 daemon worker，走的是非交互、无 TTY、无 `process.exit()` 依赖的头less路径，适合长期驻留的后台执行。

第三个入口是 `src/bridge/initReplBridge.ts` 的 `initReplBridge(options?)`。它不是命令行入口，但它是 REPL 场景里最关键的装配器：读取 bootstrap 状态、判断是否启用 bridge、处理 OAuth 和组织策略，然后把参数交给真正的桥接核心。

## 主流程位置

主流程大致分成三段：

1. `src/bridge/bridgeMain.ts`
   - 前半段是参数与环境准备，后半段是完整生命周期管理。
   - 这里能看到多会话能力、崩溃恢复指针、首次创建 session、信号处理、`runBridgeLoop(...)` 调用，以及 headless 版本的独立分支。

2. `src/bridge/replBridge.ts`
   - 这里是 REPL 桥接核心，负责会话状态机、消息写入、控制请求、SSE 序号、重连、flush gate、事件派发等。
   - 它更像“桥接引擎”，而不是单纯的包装层。

3. `src/bridge/remoteBridgeCore.ts`
   - 这是无环境层的另一条主线，注释里已经明确写了“Env-less Remote Control bridge core”。
   - 流程是先创建 session，再拿 bridge credentials，再建 v2 transport，再做 token refresh 和重连。

围绕主流程的支撑模块也很集中：
- `src/bridge/bridgeApi.ts` 负责 HTTP 层客户端和桥接环境 API。
- `src/bridge/sessionRunner.ts` 负责子会话进程的启动、活动提取、权限请求转发。
- `src/bridge/bridgeMessaging.ts` 负责消息判定、结果消息构造、输入消息处理。
- `src/bridge/bridgeEnabled.ts` 负责功能门禁和版本/订阅/策略判断。
- `src/bridge/bridgeConfig.ts`、`src/bridge/pollConfig.ts`、`src/bridge/jwtUtils.ts`、`src/bridge/trustedDevice.ts` 分别处理配置、轮询节奏、JWT 刷新、可信设备令牌。
- `src/bridge/bridgeUI.ts`、`src/bridge/bridgeStatusUtil.ts`、`src/bridge/bridgeDebug.ts`、`src/bridge/debugUtils.ts` 则服务于状态展示、调试和日志。

## 推荐阅读顺序

1. 先看 `src/bridge/bridgeEnabled.ts`，弄清楚这个能力什么时候会被放行。
2. 再看 `src/bridge/bridgeMain.ts`，因为它是总入口，能先建立整体心智模型。
3. 然后看 `src/bridge/initReplBridge.ts`，理解 REPL 侧是如何把上下文拼成桥接参数的。
4. 接着看 `src/bridge/replBridge.ts` 和 `src/bridge/remoteBridgeCore.ts`，这两份是两条主线的核心实现。
5. 最后补 `src/bridge/bridgeApi.ts`、`src/bridge/sessionRunner.ts`、`src/bridge/bridgeMessaging.ts`，把环境轮询、子进程、消息流和权限流串起来。

## 常见误区

- 把 `src/bridge` 当成单一的 API 客户端目录。实际上它是完整运行时，包含状态机、消息层、进程管理和恢复逻辑。
- 以为只有 `bridgeMain.ts` 是入口。实际上 `initReplBridge.ts`、`runBridgeHeadless(...)`、`remoteBridgeCore.ts` 也都是主流程关键节点。
- 把 `bridgeEnabled.ts` 当成 transport 实现。它只管门禁和能力开关，不负责消息传输。
- 把 `bridgeApi.ts` 当成全部网络逻辑。它只覆盖桥接环境相关的 HTTP 调用，真正的会话流转还在 `replBridge.ts`、`remoteBridgeCore.ts` 和 `sessionRunner.ts` 里。
- 忽略 `__tests__`。这个目录的测试并不多，但已经覆盖了消息、权限、结果调度和中断处理这几类高风险路径。
