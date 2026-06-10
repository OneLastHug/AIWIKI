# 目录：packages/web-host

## 它负责什么

`packages/web-host` 是 AionUi 的 WebUI 宿主层，核心职责是把“前端静态站点”和“后端 aioncore 服务”绑在一起跑。根据 `package.json` 的描述和 `src/index.ts` 的实现，它不依赖 Electron，本质上是一个可独立启动的 Web host：一边启动或接管后端进程，一边提供静态文件服务，并把 `/api/*`、`/login`、`/logout`、`/ws` 这类请求转发到后端。

从角色上看，它更像运行时编排层，而不是业务层。真正的业务逻辑不在这里，`web-host` 主要负责进程生命周期、端口分配、反向代理、静态资源分发，以及把启动结果汇总成一个统一的 handle 给上层调用者。

## 直接子目录地图

这个目录本身不大，直接子目录主要就两块：

- `src/`：主实现区，包含对外入口、后端启动器、静态服务器、类型定义，以及一个进程注册辅助模块。
- `tests/`：端到端/集成测试区，覆盖启动流程、等价性和 mock 后端场景。

根目录下还有几个关键文件，但它们不是子目录：

- `README.md`：包说明和用法示例。
- `package.json`：包名、导出入口、脚本和依赖声明。
- `tsconfig.json`：TypeScript 配置。
- `vitest.config.ts`：测试配置。

`src/` 内部从文件名看已经能分出稳定职责：`index.ts` 是统一入口，`backend-launcher.ts` 管后端生命周期，`static-server.ts` 管外层 HTTP/TCP 监听与代理，`agent-process-registry.ts` 是后端启动时的辅助清理逻辑，`types.ts` 则承载公共类型。

## 关键入口

最重要的入口是 `src/index.ts`，因为 `package.json` 的 `exports` 直接指向了它。这里对外暴露了 `startWebHost()`，同时再导出后端启动器和静态服务器的能力，说明它是这个包的门面层。

第二层关键入口是：

- `src/backend-launcher.ts`：负责拉起 aioncore、选择可用端口、拼装 spawn 参数和环境变量、处理启动失败与超时。
- `src/static-server.ts`：负责监听用户侧端口，提供静态资源和 SPA fallback，并把后端相关请求代理出去。
- `src/types.ts`：定义 `WebHostOptions`、`WebHostHandle` 以及后端启动相关类型，方便上层和内部模块共享契约。

从 README 的示例也能看出来，外部调用者只需要拿到 `startWebHost()`，传入 `app`、`staticDir` 和后端解析方式，就能得到一个带 `url` 和 `stop()` 的 handle。

## 主流程位置

主流程基本就是 `src/index.ts` 里的 `startWebHost()`，可以概括成三步：

1. 启动后端。
   - 如果 `opts.backend.kind === 'ownBackend'`，就调用 `startBackend()` 真正拉起 aioncore。
   - 如果是 `useExistingBackend`，就构造一个“假 handle”，只记录端口，不负责停止外部进程。

2. 启动静态服务器。
   - 调用 `startStaticServer()`，把 `staticDir`、后端端口、前端监听端口和 `allowRemote` 传进去。
   - 如果静态服务器启动失败，会先停止后端，避免留下孤儿进程。

3. 返回组合后的 handle。
   - 汇总 `port`、`backendPort`、`url`、`localUrl`、`networkUrl`、`lanIP`。
   - `stop()` 会依次停掉静态服务器和后端。

后端主流程主要落在 `src/backend-launcher.ts`。从已读片段看，它负责：

- 选择端口，且会避开浏览器 `fetch` 兼容性有问题的保留端口。
- 通过 `buildSpawnArgs()` 组装启动参数。
- 通过 `buildSpawnEnv()` 注入 `AIONUI_CACHE_DIR`、`AIONUI_WORK_DIR`、`AIONUI_LOG_DIR`。
- 处理启动失败、健康检查、超时和取消错误。

静态服务主流程落在 `src/static-server.ts`。它的结构比较清晰：

- 一个内部 `http.Server` 负责 `/api/*`、`/login`、`/logout` 和静态文件。
- 一个外层 `net.Server` 负责拦截连接前几个字节，判断是不是 `GET /ws...`，如果是就直接 TCP splice 到后端。
- 这样做是为了绕开某些运行时对 `upgrade` 事件转发不稳定的问题。根据当前片段推断，这是一条兼容性分支，源头注释明确提到 bun 的 HTTP 兼容层问题。

## 推荐阅读顺序

如果是第一次看这个目录，建议按下面顺序：

1. `src/index.ts`
   - 先看整体编排，知道它怎么把后端和静态服务器串起来。

2. `src/types.ts`
   - 搞清楚 `WebHostOptions`、`WebHostHandle`、`BackendBinaryResolver` 这些核心契约。

3. `src/backend-launcher.ts`
   - 看后端是怎么被启动、诊断、停止的。

4. `src/static-server.ts`
   - 看前端静态站点怎么对外提供，以及 `/api`、`/ws` 怎么转发。

5. `tests/start-web-host.test.ts`
   - 验证主启动流程的真实使用方式。

6. `tests/equivalence.test.ts`
   - 如果你关心和旧实现的一致性，这个测试能补上迁移背景。

如果只想快速建立目录感，不必把所有测试都展开到实现细节，先看文件名和入口关系就够了。

## 常见误区

- 把 `web-host` 当成纯前端包。它实际上是运行时宿主，核心工作是进程和网络编排，不是 UI 组件。
- 只看 `README.md` 不看源码。README 里 `Status` 仍写着 M3 skeleton 和 placeholder implementations，但 `src/index.ts`、`src/static-server.ts`、`src/backend-launcher.ts` 已经有实质实现了。这里 README 明显偏旧，判断应以源码为准。
- 以为它只负责静态站点。实际上它同时处理后端启动、端口选择、健康检查、反向代理和 WebSocket 转发。
- 忽略 `tests/`。这个包的行为很依赖启动顺序、端口和代理规则，测试目录比一般工具包更值得看。
- 把 `src/static-server.ts` 当成普通 `http.Server` 封装。它还有一层原始 TCP 监听，专门处理 `/ws` 路由，这是一条很关键的主流程分支。
