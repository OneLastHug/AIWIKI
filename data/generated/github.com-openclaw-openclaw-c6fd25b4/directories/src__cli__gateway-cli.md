# 子系统：src/cli/gateway-cli

## 解决什么问题

`src/cli/gateway-cli` 是 OpenClaw CLI 中 `openclaw gateway` 命令族的实现层，负责把用户在终端输入的网关启动、状态查询、RPC 调用、发现、健康检查、诊断导出等操作，转换成对 gateway runtime 的启动参数或 WebSocket RPC 请求。

它不是 gateway 服务本体。真正的 HTTP/WebSocket 服务在 `src/gateway/server.ts` 等目录中；这里的职责是“CLI 编排”：注册 commander 子命令，继承父命令选项，读取配置，校验端口/认证/绑定模式，启动服务循环，处理重启/停止信号，以及把状态、健康、stability 等结果渲染成终端或 JSON 输出。

这个目录也承担一部分运维安全边界：例如非 loopback 绑定时必须有 token/password 或 trusted-proxy；systemd/launchd 等 supervisor 场景下要避免反复重启；`--password` 会提示进程列表暴露风险；`--force` 杀端口监听前会受 future config guard 限制。

## 相关目录和文件

核心入口是 `src/cli/gateway-cli/register.ts`，它注册 `gateway` 顶层命令以及 `call`、`usage-cost`、`health`、`stability`、`discover`、`status`、`probe` 等子命令，并接入 `src/cli/daemon-cli/register-service-commands.ts` 提供的 service 生命周期命令。

`src/cli/gateway-cli/run-command.ts` 只定义 `addGatewayRunCommand`，集中声明 gateway 启动类选项，例如 `--port`、`--bind`、`--auth`、`--tailscale`、`--force`、`--ws-log`。它被 `register.ts` 和轻量 CLI bootstrap 路径复用，避免帮助信息加载完整 gateway server 树。

`src/cli/gateway-cli/run.ts` 是前台启动命令的主体：读取配置、解析认证、确定 bind/port/tailscale、执行启动防护，然后调用 `runGatewayLoop`。

`src/cli/gateway-cli/run-loop.ts` 维护单进程 gateway 生命周期：加锁、启动 server、响应 SIGTERM/SIGINT/SIGUSR1、停机、重启、drain 活跃任务、必要时 respawn 新进程。

`src/cli/gateway-cli/call.ts` 是 CLI 到 gateway RPC 的轻封装，最终调用 `src/gateway/call.ts`。`src/cli/gateway-cli/discover.ts` 负责整理 bonjour/wide-area discovery 结果。`src/cli/gateway-cli/shared.ts` 放服务冲突时的跨平台 stop 提示。`src/cli/gateway-cli/qa-parent-watchdog.ts` 只服务 QA 场景，避免父进程退出后遗留孤儿 gateway 和临时目录。

## 核心对象

`registerGatewayCli(program)` 是命令注册总入口。它通过 `addGatewayRunCommand` 给 `gateway` 本身和 `gateway run` 都挂上相同启动选项，使 `openclaw gateway --token ...` 和 `openclaw gateway run --token ...` 的体验一致。

`GatewayRunOpts` 是启动参数的聚合类型，覆盖端口、绑定、认证、Tailscale、日志、dev/reset、raw stream 等开关。`resolveGatewayRunOptions` 会从父 commander 命令继承选项，解决顶层 `gateway` 与子命令 `run` 的 option collision 问题；相关测试在 `src/cli/gateway-cli/run.option-collisions.test.ts` 和 `src/cli/gateway-cli/register.option-collisions.test.ts`。

`runGatewayCommand(opts)` 是真正的启动编排函数。它会规范化 state dir 环境变量，安装 QA watchdog，设置 verbose/ws log/raw stream，延迟导入 `startGatewayServer`，读取配置快照，解析端口和 bind，校验 `gateway.mode`，调用 `resolveGatewayAuth`，最后把 `startGatewayServer(port, ...)` 包装给 `runGatewayLoop`。

`runGatewayLoop(params)` 是生命周期核心。它持有 gateway lock，启动 server，处理停止和重启信号。重启时会先进入 draining 状态，等待 active tasks 和 embedded runs；对于 `update.run` 还会优先尝试 fresh PID respawn，失败后回退到 in-process restart。

`GatewayRpcOpts` 和 `callGatewayCli(method, opts, params)` 是 RPC 调用对象。CLI 调用会传入 `GATEWAY_CLIENT_NAMES.CLI` 和 `GATEWAY_CLIENT_MODES.CLI`，并根据 `--json` 决定是否显示 progress spinner。

## 运行流程

启动流程大致是：`src/cli/gateway-cli.ts` 导出 `registerGatewayCli`，上层 CLI 程序调用它注册命令；用户执行 `openclaw gateway run` 或直接执行带 action 的 `openclaw gateway`；commander action 延迟导入 `run.ts`；`resolveGatewayRunOptions` 合并父子选项；`runGatewayCommand` 读取配置、端口、认证和 bind 策略；确认不违反安全约束后，动态导入 `src/gateway/server.ts`，调用 `startGatewayServer`；`runGatewayLoop` 获得锁并托管生命周期。

RPC 查询流程则更短：例如 `gateway health` 或 `gateway call health` 在 `register.ts` 中解析 `--url`、`--token`、`--password`、`--timeout`，再调用本目录 `call.ts`，最终进入 `src/gateway/call.ts` 通过 WebSocket 请求 gateway 方法。输出层由 `register.ts` 负责格式化，健康信息还会使用 `src/commands/health.ts` 和 `src/terminal/health-style.ts`。

发现流程根据当前片段推断主要依赖 `src/infra/bonjour-discovery.ts`、`src/infra/widearea-dns.ts` 和 `src/infra/gateway-discovery-targets.ts`。依据是 `register.ts` 对 discovery 模块使用 lazy loader，`discover.ts` 使用 `GatewayBonjourBeacon` 与 `buildGatewayDiscoveryTarget` 生成展示字段。

## 上下游依赖

上游是 CLI 注册体系：`src/cli/program/register.subclis-core.ts`、`src/cli/run-main.ts` 会按需挂载 gateway 命令；`commander` 提供参数解析；`src/cli/command-options.ts` 提供父命令选项继承。

配置上游包括 `src/config/config.ts`、`src/config/paths.ts`、`src/config/types.openclaw.ts`、`src/config/types.secrets.ts`。认证、绑定和服务启动下游分别是 `src/gateway/auth.ts`、`src/gateway/net.ts`、`src/gateway/server.ts`。

运行时依赖 `src/infra/gateway-lock.ts` 防止多实例抢同一端口，依赖 `src/infra/supervisor-markers.ts` 判断 systemd/launchd 等 supervisor，依赖 `src/logging/diagnostic-stability-bundle.ts` 在失败、重启超时、内存压力等场景写诊断包。

命令输出依赖 `src/runtime.ts` 的 `defaultRuntime`，以及 `src/terminal/theme.ts`、`src/terminal/links.ts`、`src/cli/progress.ts`。服务管理命令来自 `src/cli/daemon-cli/register-service-commands.ts`，这说明 gateway CLI 既支持前台运行，也要与安装后的 daemon/service 模式协作。

## 修改时最容易踩的坑

第一，启动选项有父子继承关系。新增 `gateway run` 选项时，通常要同时考虑 `run-command.ts` 的 commander 声明、`GatewayRunOpts` 类型、`GATEWAY_RUN_VALUE_KEYS` 或 `GATEWAY_RUN_BOOLEAN_KEYS`，否则顶层 `openclaw gateway --flag` 和子命令 `openclaw gateway run --flag` 行为会不一致。

第二，认证和 bind 是安全边界。`run.ts` 明确阻止无共享 secret 时绑定到非 loopback，容器环境下默认 bind 也可能变成更开放的地址。修改 `defaultGatewayBindMode`、`resolveGatewayBindHost`、`resolveGatewayAuth` 相关调用时，需要同时证明 token/password/trusted-proxy 的组合不会放开未认证 gateway。

第三，supervisor 语义不能只按普通 CLI 进程处理。systemd 下已有健康 gateway 时，某些 lock 错误会用配置错误退出码避免 Restart storm；launchd 下 full-process restart 会短暂延迟退出，避免触发节流。这里的退出码和等待时间是运维契约。

第四，`run-loop.ts` 对动态导入非常敏感。它在安装信号监听前 eager load `lifecycle.runtime.ts`，注释说明这是为了避免包升级后 chunk hash 变化导致 SIGUSR1 重启路径找不到模块。不要轻易把这段改回懒加载。

第五，gateway 启动是热路径和冷启动体验兼顾的地方。`register.ts` 大量使用 `createLazyImportLoader`，`run-command.ts` 被轻量 bootstrap 复用。把重模块静态 import 到注册路径，可能破坏 `help` 或 CLI cold start 测试。

第六，诊断命令输出既支持 human readable，也支持 `--json`。新增错误处理时要注意 `runGatewayCommand` 中 JSON transport error 的特殊格式化，避免自动化调用者只能解析普通文本错误。

## 推荐阅读顺序

1. 先读 `src/cli/gateway-cli/run-command.ts`，理解用户可见的启动参数面。
2. 再读 `src/cli/gateway-cli/register.ts`，建立 `openclaw gateway` 命令族的整体地图。
3. 接着读 `src/cli/gateway-cli/run.ts`，关注配置、端口、认证、bind、Tailscale 到 `startGatewayServer` 的编排。
4. 然后读 `src/cli/gateway-cli/run-loop.ts`，理解锁、信号、drain、respawn、诊断包这些生命周期问题。
5. 补读 `src/cli/gateway-cli/call.ts` 和 `src/gateway/call.ts`，看 CLI RPC 如何进入 gateway protocol。
6. 最后看测试：`src/cli/gateway-cli/run-loop.test.ts`、`src/cli/gateway-cli/run.supervised-lock.test.ts`、`src/cli/gateway-cli/register.option-collisions.test.ts`，这些测试比文件清单更能说明该子系统真正维护的行为契约。
