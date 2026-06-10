# 文件：src/gateway/server.impl.ts

## 一句话定位

`src/gateway/server.impl.ts` 是 OpenClaw Gateway 的启动与生命周期编排核心：它不主要实现某个业务方法，而是把配置加载、认证、插件、HTTP/WS 监听、通道运行时、健康检查、后台任务、热重载和关闭清理串成一个可运行的 Gateway Server。

## 它暴露/定义了什么

文件主要导出三类公共表面：

`startGatewayServer(port, opts)`：核心入口，启动 Gateway HTTP/WebSocket 服务并返回 `{ close }`。

`GatewayServerOptions`、`GatewayServer`、`GatewayCloseOptions`：描述启动参数、返回对象和关闭参数。启动参数覆盖范围很广，包括 bind/host、Control UI、OpenAI 兼容 HTTP endpoint、auth、Tailscale、wizard runner、是否延后 sidecars，以及 CLI 预读的 config snapshot。

`resetModelCatalogCacheForTest()`：测试辅助导出，通过懒加载 `server-model-catalog.js` 重置模型目录缓存。

此外，文件内部定义了一批启动期辅助机制，例如 `createGatewayStartupTrace()`、懒加载模块函数、auth rate limiter 创建、media TTL 归一化、关闭前清理等。

## 谁调用它

常规调用方不是直接面向此文件，而是通过 `src/gateway/server.ts` 的懒加载包装导出 `startGatewayServer`。CLI 入口 `src/cli/gateway-cli/run.ts` 会动态导入 `src/gateway/server.js` 并启动服务；`src/cli/gateway-cli/run-loop.ts` 持有其返回 server 并管理运行循环。大量 Gateway 测试也通过 `src/gateway/test-helpers.server.ts`、`src/gateway/test-helpers.ts` 或直接导入 `src/gateway/server.js` 启动测试服务器。少数 live/profile 测试会直接导入 `src/gateway/server.impl.ts`，这更像是测试绕过懒加载边界的用法。

## 它调用谁

它调用面非常广，按职责可分为：

配置与 secrets：`src/config/io.ts`、`src/config/runtime-overrides.ts`、`src/config/plugin-auto-enable.ts`、`src/secrets/runtime-state.ts`。

插件与通道：`src/plugins/runtime.ts`、`src/plugins/plugin-lookup-table.ts`、`src/plugins/services.ts`、`src/gateway/server-plugin-bootstrap.ts`、`src/gateway/server-channels.ts`。

HTTP/WS 与请求上下文：`src/gateway/server-runtime-state.ts`、`src/gateway/server-ws-runtime.ts`、`src/gateway/server-request-context.ts`、`src/gateway/server-methods.ts`、`src/gateway/methods/registry.ts`。

启动/关闭拆分模块：`src/gateway/server-startup-config.ts`、`src/gateway/server-startup-plugins.ts`、`src/gateway/server-startup-early.ts`、`src/gateway/server-startup-post-attach.ts`、`src/gateway/server-close.runtime.ts`。

运行期服务：健康检查、cron、model catalog、Tailscale、Control UI root、TLS、restart trace、diagnostics timeline 等模块。

## 核心流程

启动先做进程级准备：规范 state dir 环境变量、加载网络运行时、设置 `OPENCLAW_GATEWAY_PORT`、恢复 restart trace，并创建 startup trace。

随后读取启动配置快照，应用运行时覆盖，准备 Gateway auth 和 secrets。若缺少 token，可能生成仅本次启动有效的 runtime token。之后开启诊断心跳、SIGUSR1 restart 策略、pre-restart deferral 计数，并处理 Control UI allowed origins 的启动期迁移。

接着准备插件启动计划：构建 plugin lookup table、默认 workspace、startup plugin ids、基础 Gateway 方法和 plugin registry。文件会把当前插件元数据 snapshot 固定下来，避免请求热路径反复发现插件。

然后解析运行时 Gateway 配置，包括 bind host、Control UI、OpenAI 兼容 HTTP endpoints、auth、Tailscale、TLS、hooks 配置等。再创建 channel manager、readiness checker、HTTP/WS runtime state、node session runtime 和 live state。

进入真正 attach 阶段后，文件启动 early runtime、订阅运行时事件、启动 runtime services，加载 core/aux/plugin Gateway handlers，构造 `GatewayMethodRegistry`，再创建 `GatewayRequestContext`。随后将 WebSocket handler 绑定到 `wss`，启动 HTTP listen。

HTTP 绑定后，post-attach runtime 启动通道、插件服务、Tailscale、post-ready sidecars 等。ready 后再启动 config reloader，支持配置变更时重载 hooks、cron、通道和插件。最后安排 post-ready maintenance，例如健康轮询、dedupe cleanup、media cleanup、cron 启动和内存采样。

关闭流程返回在 `GatewayServer.close()` 中：先标记关闭开始，停止 lifetime/post-ready sidecars，执行 `gateway_stop` 插件 hook，跑 close prelude 清理诊断、rate limiter、健康监控、secrets snapshot、MCP loopback 等，再交给 `server-close.runtime.ts` 统一 drain session、停止通道、关闭 HTTP/WS 和 timers。

## 关键函数的高层作用

`startGatewayServer()` 是全文件核心。它的职责是“编排启动”，不是承载单个请求逻辑。所有长期状态都收束到 `runtimeState`、`gatewayRequestContext`、`pluginRegistry`、`channelManager` 和 `clients` 等对象中，再传给下游模块。

`createGatewayStartupTrace()` 负责启动性能观测。它记录阶段耗时、restart trace、diagnostics timeline 和 event loop delay sample，是排查 Gateway 启动慢、阻塞和 restart readiness 的关键工具。

`reloadAttachedGatewayPlugins()` 是配置热重载中的插件替换逻辑。它根据新配置重新构建 plugin lookup table，判断哪些 channel 需要先停、替换 plugin registry、刷新 discovery、重启 plugin services，并返回需要重启的通道集合。

`createCloseHandler()` 把关闭所需资源打包交给 close runtime，包括 channels、plugin services、cron、heartbeat、update check、pending replies、WebSocket clients、HTTP servers、chat runs 和 config reloader。

`getChannelRuntime()`、`getStartupChannelRuntime()`、`loadGatewayStartupEarlyModule()` 等懒加载函数用于控制 Gateway 热路径和启动成本，符合 `src/gateway/AGENTS.md` 中避免 HTTP/server 代码过早物化完整插件运行时的约束。

## 修改风险

最大风险是启动顺序。配置、secrets、auth、plugin metadata snapshot、HTTP/WS attach、channel start、scheduled services 激活之间存在明确依赖；提前或延后任一步都可能造成方法列表不完整、认证状态不一致、Control UI 无法连接、插件路由未注册或 readiness 误报。

第二类风险是插件/通道边界。该文件需要避免在 Gateway server 热路径加载过重的 bundled plugin runtime；修改插件发现、registry pin、deferred plugin loading、channel config target 判断时，应同时检查 `src/gateway/AGENTS.md` 的 hot path 规则。

第三类风险是 auth 和 shared session generation。这里同时处理 token auth、browser-origin throttling、trusted proxies、shared auth generation 以及配置写入约束。改动可能导致旧 session 被错误保留、配置热更新后客户端认证状态错乱，或 loopback/browser 限流策略失效。

第四类风险是关闭清理。新增 timer、sidecar、subscription、channel/runtime service 时，如果没有挂入 `runtimeState` 和 close prelude/close handler，容易留下后台任务、端口占用、测试泄漏或 restart 卡住。

第五类风险是测试模式与生产模式分叉。`minimalTestGateway`、`deferStartupSidecars`、懒加载、post-ready maintenance 会让同一逻辑在测试和生产中表现不同。修改后应至少覆盖目标 Gateway 测试文件；涉及 lazy boundary、插件 artifact、动态 import 或发布表面时，还需要构建级验证。
