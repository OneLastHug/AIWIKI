# 运行流程与关键调用链

本页按一次典型运行来解释 OpenClaw：从 `openclaw` 命令启动，到 Gateway 加载配置和插件，再到 WebSocket/HTTP 请求、channel 消息、agent run 和后台服务。依据来自 `openclaw.mjs`、`src/entry.ts`、`src/cli/gateway-cli/run.ts`、`src/cli/gateway-cli/run-loop.ts`、`src/gateway/server.ts`、`src/gateway/server.impl.ts`、`src/gateway/server-startup-plugins.ts`、`src/gateway/server-plugin-bootstrap.ts`、`src/gateway/server-ws-runtime.ts`、`src/gateway/server-request-context.ts`、`src/agents/agent-command.ts`、`src/channels/**`。没有集中入口说明的部分会标注“根据当前文件推断”。

## CLI 启动

`package.json` 的 `bin.openclaw` 指向 `openclaw.mjs`。用户执行 `openclaw ...` 时，首先进入 `openclaw.mjs`。这个文件做三件明显的事：检查 Node 版本至少为 22.19；判断当前是源码 checkout 还是 packaged install；根据源码/打包场景处理 Node compile cache 和 respawn。它还会在 packaged 场景为 compile cache 生成与 package version、package.json mtime/size 有关的目录。这里的重点是：真正的 TypeScript CLI 逻辑不在 `openclaw.mjs`，它是启动包装层。

源码入口是 `src/entry.ts`。它设置 `process.title`、执行 `ensureOpenClawExecMarkerOnProcess`、安装 warning filter、规范化环境变量，解析 `--profile`、`--dev`、container 参数、Windows argv，并处理 root help/version fast path。若不是 help/version 快路径，就动态导入 `src/cli/run-main.js` 并调用 `runCli(argv)`。因此，如果读者想知道某个命令怎么注册，不应停在 `entry.ts`，而要进入 `src/cli/run-main.ts` 和具体 `src/cli/*-cli.ts`。

## Gateway 命令进入服务启动

当执行 `openclaw gateway` 或开发脚本 `pnpm gateway:watch` 进入 Gateway 时，命令层会走 `src/cli/gateway-cli/register.ts` 和 `src/cli/gateway-cli/run.ts`。`run.ts` 负责解析 `--port`、`--bind`、`--auth`、`--token`、`--password`、`--tailscale`、`--force`、`--dev`、`--reset`、`--ws-log` 等选项；它会读取配置快照，校验 gateway mode、端口、bind/auth 组合，并处理非 loopback bind 下没有 shared secret 的风险。

`run.ts` 会动态导入 `src/gateway/server.js` 的 `startGatewayServer`。它不是直接启动后退出，而是把启动函数交给 `src/cli/gateway-cli/run-loop.ts`。`run-loop.ts` 负责 Gateway lock、signal handler、SIGTERM/SIGINT/SIGUSR1、restart intent、update respawn、in-process restart、close drain、健康探测和 supervisor 场景。根据当前文件推断，OpenClaw Gateway 被设计成长期进程，需要处理升级、重启、服务管理器和端口竞争，而不是简单的一次性 HTTP server。

## Gateway 服务启动

`src/gateway/server.ts` 是懒加载包装，真正实现是 `src/gateway/server.impl.ts` 的 `startGatewayServer(port, opts)`。启动开始会规范状态目录环境、bootstrap network runtime，并把实际端口写入 `OPENCLAW_GATEWAY_PORT`。然后它加载 `src/gateway/server-startup-config.ts`，调用 `loadGatewayStartupConfigSnapshot` 读取配置快照，再调用 `prepareGatewayStartupConfig` 处理 auth、tailscale、secrets activation、runtime config。随后它调用 `setRuntimeConfigSnapshot`，把启动时配置放入运行时快照。

配置之后进入插件 bootstrap。`server.impl.ts` 调用 `prepareGatewayPluginBootstrap`。在 `src/gateway/server-startup-plugins.ts` 中，它会运行 channel plugin startup maintenance、session migration、初始化 subagent registry，合并插件自动启用配置，解析默认 agent/workspace，构建 `pluginLookUpTable`，计算 deferred channel plugin 和 startup plugin ids。若允许运行时加载插件，则继续调用 `loadGatewayStartupPluginRuntime`。

`loadGatewayStartupPluginRuntime` 会进入 `src/gateway/server-plugin-bootstrap.ts`，这里先安装 Gateway plugin runtime environment：设置 subagent override policy、Gateway subagent runtime、Gateway nodes runtime；然后调用 `loadGatewayPlugins` 加载插件，prime configured binding registry，并把 channel registry pin 到 active runtime。根据当前文件推断，插件加载结果会提供 `pluginRegistry`、`gatewayHandlers`、`gatewayMethodDescriptors`、HTTP routes、channel registry、node capabilities 等能力，具体字段需要继续读 `src/plugins/registry-types.ts` 与 `src/plugins/registry.ts`。

## HTTP、WebSocket 与 method registry

Gateway 启动中会创建 runtime config，解析 bind host、Control UI、OpenAI-compatible HTTP、OpenResponses、auth、tailscale、HSTS 等设置。随后构造 Gateway method registry：`src/gateway/methods/registry.ts` 把 core descriptors、plugin descriptors 和 auxiliary handlers 归一化，要求每个 method 有非空 name 和 scope，并能列出 advertised methods、查 handler、查 scope、判断 startup unavailable 和 control-plane write。

`src/gateway/server-request-context.ts` 创建请求上下文。这个上下文把 deps、runtime config、cron、approval manager、plugin approval manager、model catalog、health cache、broadcast、node registry、chat run buffers、session subscribers、wizard sessions、start/stop channel 等对象集中传给 method handler。其注释说明 cron 读取保持 live，以便配置热重载能替换 cron/store state，而不需要重建所有 handler closure。

`src/gateway/server-ws-runtime.ts` 调用 `attachGatewayWsConnectionHandler`，传入 WebSocketServer、clients、preauth budget、auth resolver、gateway methods、events、method registry、broadcast 和 request context。根据当前文件推断，WebSocket 客户端连接后会经过 auth/handshake，然后按 method name 在 registry 中查 handler，并使用 request context 执行。HTTP 路由和 Control UI 路由在 `src/gateway/server-http.ts`、`src/gateway/control-ui*.ts`、`src/gateway/openai-http.ts`、`src/gateway/openresponses-http.ts`、plugin HTTP route 相关文件中继续展开。

## Post-attach 与后台服务

`server.impl.ts` 在 WebSocket handler attach 和 HTTP listen 后，调用 `startGatewayPostAttachRuntime`。传入参数包括 config、bind hosts、port、TLS、tailscale、plugin registry、default workspace、deps、`startChannels`、hooks/channel/cron logs、plugin lookup table、loadStartupPlugins 回调、onStartupPluginsLoaded、onChannelsStarted、onPluginServices、onSidecarsReady 等。根据当前文件推断，post-attach runtime 负责启动 channel、plugin services、tailscale/discovery、hooks、sidecars 和 provider auth prewarm 等启动后任务；具体需要继续读 `src/gateway/server-post-attach-runtime.ts` 及相关 runtime services 文件。

启动 ready 后，Gateway 会启动 managed config reloader：`startManagedGatewayConfigReloader`。它监听配置路径和 config write listener，必要时重载插件、重启 channel、更新 cron/hooks/channel health monitor、激活 runtime secrets、处理 shared gateway auth generation。随后还会安排 post-ready maintenance，包括健康、dedupe、media cleanup、cron start 等后台任务。关闭时，server 返回的 `close` 会停止 sidecars，运行 `gateway_stop` plugin hook，执行 close prelude，并清理 fallback context。

## Agent 请求流

CLI `openclaw agent ...` 或 Gateway method 最终会进入 `src/commands/agent.ts`，但该文件只是 `export * from "../agents/agent-command.js"`。实际实现是 `src/agents/agent-command.ts`。该文件导入 `getRuntimeConfig`、session store、model selection、auth profiles、skills、ACP manager、attempt execution runtime、delivery runtime、workspace、sandbox/tool policy、provider catalog 等模块。一次 agent run 会解析 session key/agent id，确定 agent runtime config、workspace、模型、thinking/verbose、skills snapshot、auth profile、timeout 和 fallback，然后运行 attempt execution 并按 delivery policy 输出或送回 channel。

根据当前文件推断，agent run 可能有两条主要入口：CLI/local request 和 Gateway/channel ingress。`agent-command.ts` 中出现 `withLocalGatewayRequestScope`、`buildOutboundSessionContext`、`resolveMessageChannel`、`deliveryRuntime` 等导入，说明它既可用于直接 CLI 输出，也可用于消息渠道回复。完整调用链需要继续读 `src/agents/command/session.ts`、`src/agents/command/attempt-execution.runtime.ts`、`src/agents/command/delivery.runtime.ts`。

## Channel 消息流

Channel 框架在 `src/channels/**`。`src/channels/message/receive.ts` 定义 `MessageReceiveContext`，包含 id、channel、accountId、message、ackPolicy、ackState、receivedAt、signal、ack/nack 和 `shouldAckAfter(stage)`。ack policy 支持 `after_receive_record`、`after_agent_dispatch`、`after_durable_send`、`manual`。这说明 channel 入站消息不是简单同步调用，而是有接收记录、agent dispatch、durable send、manual ack 等生命周期阶段。

消息访问控制由 `src/channels/message-access/**`、`src/channels/allow-from.ts`、`src/channels/allowlist-match.ts`、`src/channels/mention-gating.ts`、`src/channels/command-gating.ts` 等负责；会话和路由由 `src/channels/session.ts`、`src/channels/session-envelope.ts`、`src/channels/route-projection.ts`、`src/routing/**` 等参与；回复由 `src/channels/message/reply-pipeline.ts`、`src/channels/message/send.ts`、`src/channels/message/outbound-bridge.ts` 处理。具体平台消息如何进入这些通用 contract，需要读对应 `extensions/<channel>` 的 `index.ts`、runtime 文件和 `openclaw.plugin.json`。

## 配置加载与数据流总结

启动时的数据流可以概括为：`openclaw.mjs` 检查环境并进入 `src/entry.ts`；`entry.ts` 进入 CLI；Gateway CLI 读取参数和配置快照；`startGatewayServer` 读取 startup config、准备 auth/secrets/runtime config；插件 bootstrap 生成 lookup table 和 registry；Gateway 创建 method registry 与 request context；HTTP/WebSocket 监听；post-attach runtime 启动 channel/plugin/sidecar/维护任务；运行期请求通过 method registry 或 channel ingress 进入 request context，再调用 agent/channel/plugin/provider 相关能力。

需要特别注意配置和插件是运行期核心事实来源。`getRuntimeConfig`、runtime snapshot、plugin metadata snapshot、plugin registry、gateway method registry、channel registry、node registry 都会在不同阶段被准备并传递。阅读 bug 或功能时，不要只看最终 handler，还要追它使用的是启动快照、热重载后的 runtime config，还是插件 registry 中的 prepared object。
