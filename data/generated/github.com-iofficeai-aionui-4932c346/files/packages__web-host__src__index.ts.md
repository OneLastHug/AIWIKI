# 文件：packages/web-host/src/index.ts

## 一句话定位
`packages/web-host/src/index.ts` 是 `@aionui/web-host` 的包入口和统一编排层，负责把“启动后端”和“启动静态 Web 服务”串起来，对外提供一个可停止的 WebUI 主机能力。根据当前片段推断，它本质上是 Electron 主进程、CLI `webui` 模式和单独 WebUI 启动流程之间的共享启动门面。

## 它暴露/定义了什么
这个文件主要做两件事。

第一，它作为包级入口重新导出类型和能力：`AppMetadata`、`BackendBinaryResolver`、`WebHostOptions`、`WebHostHandle`，以及静态服务相关的 `startStaticServer`、`stopStaticServer`，还有后端启动相关的 `BackendLifecycleManager`、`buildSpawnArgs`、`buildSpawnEnv`、`findAvailablePort`、`startBackend`、`stopBackend` 等。`packages/web-host/package.json` 里把 `.` 映射到这里，说明外部通常就是通过这个文件拿到整个包的公开 API。

第二，它定义了核心函数 `startWebHost(opts)`。这是整个包真正的入口函数，返回一个组合后的 `WebHostHandle`，里面既有前端静态服务端口，也有后端端口、访问 URL 和统一的 `stop()`。

## 谁调用它
从仓库内搜索看，直接调用者主要有四类：

1. `scripts/webui.ts`：独立 WebUI 启动脚本，用自己的 `workDir`、`backendBin` 和日志目录来启动完整服务。
2. `packages/web-cli/src/index.ts`：命令行 WebUI 模式，既有“前端仅运行”场景，也有“前后端一起拉起”的场景。
3. `packages/desktop/src/index.ts`：桌面应用在 `--webui` 或相关模式下复用这套启动逻辑。
4. `packages/desktop/src/process/utils/webuiConfig.ts`：桌面进程内部的 WebUI 配置/启动辅助流程也会走这里。

另外，`packages/web-host/tests/start-web-host.test.ts` 和 `packages/web-host/README.md` 也在使用它，说明它是这个包最核心的公共 API。

## 它调用谁
`startWebHost` 自己只显式调用两个模块：

- `./backend-launcher.js` 里的 `startBackend`
- `./static-server.js` 里的 `startStaticServer`

此外它还依赖 `opts.backend.kind` 决定走哪条分支：

- `ownBackend`：真正启动本地后端；
- `useExistingBackend`：不再拉起新进程，而是构造一个“假的”句柄，只保留 `port` 和空实现 `stop()`。

从返回值看，它还会把静态服务器和后端句柄合并成一个统一对象。

## 核心流程
1. 先按 `backend.kind` 选择后端策略。
2. 如果是 `ownBackend`，调用 `startBackend()`，把 `app`、后端可执行文件解析器、`dataDir`、`logDir`、`dirs` 传下去。
3. 如果是 `useExistingBackend`，直接用传入端口构造一个占位句柄，避免重复启动进程。
4. 接着调用 `startStaticServer()`，把静态目录、后端端口、目标监听端口和 `allowRemote` 传入。
5. 如果静态服务启动失败，会先调用后端句柄的 `stop()` 做清理，再把错误抛出。
6. 两者都成功后，返回一个统一的 `WebHostHandle`，其中 `stop()` 会按顺序先停静态服务，再停后端。

这个流程的关键点是“启动失败要回滚已启动资源”，它避免了后端已起、静态层失败后留下孤儿进程。

## 关键函数的高层作用
- `startWebHost()`：主编排函数，负责把后端、静态站点、端口和清理逻辑组装成一个可用的 WebHost。
- `startBackend()`：后端进程启动器，负责把应用后端真正跑起来。
- `startStaticServer()`：静态站点和转发层启动器，负责对外提供 WebUI 访问入口，并把请求导向后端。
- `stop()`（返回句柄上的方法）：统一释放资源，保证调用方不用分别管理两个子系统。

## 修改风险
这个文件看起来短，但改动风险不低，因为它处在“组合边界”上。

1. 启动顺序和清理顺序一旦改错，就可能出现端口占用、孤儿进程或半启动状态。
2. `ownBackend` 和 `useExistingBackend` 的语义不能混，如果把外部后端误当成本地进程管理，可能误杀别的服务。
3. `allowRemote`、`port`、`dirs`、`dataDir` 这些参数是上层运行模式的映射，改动会直接影响 Electron、CLI 和 standalone WebUI 的行为一致性。
4. 返回的 `WebHostHandle` 是上层依赖的稳定契约，字段增删或语义变化会波及多个调用方。
5. 这个文件当前还承担包入口职责，任何导出调整都会影响 `@aionui/web-host` 的外部 API 面。

根据当前片段推断，这里最稳妥的改法通常是只调整编排细节，不碰对外签名；如果要扩展能力，优先让 `backend-launcher` 和 `static-server` 各自吸收复杂度，再由这里做薄编排。
