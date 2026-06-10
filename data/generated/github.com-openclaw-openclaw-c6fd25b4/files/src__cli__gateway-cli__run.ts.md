# 文件：src/cli/gateway-cli/run.ts

## 一句话定位

`src/cli/gateway-cli/run.ts` 是 `openclaw gateway` 启动命令的执行核心：它把 CLI 参数、配置文件、环境变量、认证策略、端口/绑定策略、Tailscale 暴露策略和进程监督器行为整理成一次可启动、可诊断、可安全退出的 Gateway 服务启动流程。

## 它暴露/定义了什么

这个文件主要导出三个面向外部的符号：

`resolveGatewayRunOptions(opts, command)`：把子命令参数和父命令继承参数合并，处理 `--token`、`--port`、`--bind`、`--ws-log` 等值型选项，以及 `--force`、`--dev`、`--reset`、`--verbose` 等布尔选项。

`runGatewayCommand(opts)`：真正执行 Gateway 启动的主函数，也是文件的中心职责。

`testing` / `__testing`：暴露少量内部函数给测试使用，包括 `normalizeGatewayHealthProbeHost`、`resolveGatewayLockErrorExitCode`、`runGatewayLoopWithSupervisedLockRecovery`。这说明该文件中监督器锁恢复逻辑被视为需要稳定回归测试的关键行为。

文件内还定义了 `GatewayRunOpts`、认证/Tailscale 模式常量、配置错误退出码 `EXIT_CONFIG_ERROR = 78`，以及一组辅助函数，用于端口、认证、密码文件、配置守卫、启动追踪和锁冲突恢复。

## 谁调用它

直接调用方是 `src/cli/gateway-cli/run-command.ts`。该文件通过 `addGatewayRunCommand(cmd)` 注册 `gateway` 启动命令及其选项，并在 `.action()` 中动态导入 `./run.js`，随后调用 `resolveGatewayRunOptions(opts, command)` 和 `runGatewayCommand(...)`。

更外层看，`src/cli/gateway-cli/register.ts` 负责注册整个 Gateway CLI 命令族，包括 call、discover、status、health、stability 等子命令，并把启动命令挂入 commander 命令树。因此，根据当前片段推断，用户执行 `openclaw gateway ...` 启动服务时，路径大致是 CLI 注册层进入 `run-command.ts`，再进入本文件。

测试侧，`src/cli/gateway-cli/run.supervised-lock.test.ts` 覆盖监督器锁恢复行为；`src/cli/gateway-cli.coverage.test.ts` 间接覆盖 CLI 参数入口；`src/cli/help-cold-imports.test.ts` 用 mock 证明帮助信息路径不会冷启动重依赖。

## 它调用谁

本文件是一个编排层，调用面很广，但核心依赖可以分成几类：

配置与路径：`../../config/config.js`、`../../config/paths.js`、`../../config/future-version-guard.js`、`../../config/types.secrets.js`。它读取配置快照、解析端口、判断配置是否存在，并阻止未来版本配置在服务模式下被旧版本 Gateway 启动。

网络与 Gateway：`../../gateway/server.js` 提供 `startGatewayServer`；`../../gateway/auth.js` 解析最终认证模式；`../../gateway/net.js` 解析 bind host 和默认绑定策略；`./run-loop.js` 负责持锁运行、信号处理、重启和关闭循环。

进程与诊断：`../../infra/gateway-lock.js`、`../../infra/supervisor-markers.js`、`../../infra/ports.js`、`../../logging/diagnostic-stability-bundle.js`、`../../logging/subsystem.js`。这些用于处理端口占用、systemd/launchd 等监督器、启动失败诊断包和日志输出。

CLI 辅助：`../shared/parse-port.js`、`../ports.js`、`../progress.js`、`../error-format.js`、`../command-format.js`、`../command-options.js`。它们负责参数解析、错误文本、进度提示、端口释放和父命令选项继承。

## 核心流程

启动开始时，`runGatewayCommand` 先规范化 state 目录环境变量，安装 QA 父进程 watchdog，并在服务模式下记录当前 PID。随后判断 `--dev` / `OPENCLAW_PROFILE=dev` 和 `--reset` 的合法组合；`--reset` 只能配合 dev 模式使用。

接着它设置日志开关：`--verbose` 控制全局详细日志，`--cli-backend-logs` / `--claude-cli-logs` 限制控制台子系统日志，`--ws-log` 和 `--compact` 决定 WebSocket 日志风格，`--raw-stream` 相关参数写入环境变量。

然后它动态导入 `../../gateway/server.js`，并用 `withProgress` 显示“Loading gateway modules...”进度。这里的动态导入很重要，因为 Gateway server 会拉起 channels、plugins、HTTP stack 等重模块；结合 `src/gateway/AGENTS.md` 的约束，Gateway 启动路径应避免不必要地物化完整插件运行时。

配置阶段会读取带 plugin metadata 的配置快照。如果是 dev 模式，会先调用 `ensureDevGatewayConfig` 准备开发配置。之后解析端口，检查 `gateway.port` 或 `--port` 是否有效，并通过 future-version guard 阻止旧版本服务处理未来版本配置。若传入 `--force`，还会尝试释放目标端口并等待端口重新可绑定。

安全阶段先解析 `--auth`、`--token`、`--password`、`--password-file` 和 `--tailscale`。它通过 `resolveGatewayAuth` 得到最终认证模式，并用 `getGatewayStartGuardErrors` 强制普通启动必须有合法的 `gateway.mode=local`，除非传入 `--allow-unconfigured`。随后根据 bind host 判断是否允许无共享密钥启动：如果 Gateway 要绑定到非 loopback 地址，且不是 `trusted-proxy`，又没有 token/password，就会拒绝启动。

最后它构造 `startLoop`：调用 `runGatewayLoop` 获取 Gateway lock，并在其中调用 `startGatewayServer(port, { bind, auth, tailscale, startupStartedAt, startupConfigSnapshotRead })`。外层再通过 `runGatewayLoopWithSupervisedLockRecovery` 处理 systemd/launchd 等监督器下的“锁已存在但旧进程可能正在启动”场景。启动失败时，锁错误会给出端口诊断和 stop 提示；其他错误会写启动失败诊断包并建议运行 `openclaw gateway status --deep`。

## 关键函数的高层作用

`runGatewayCommand` 是主入口。它不是简单调用 server，而是负责把用户输入、配置、环境变量、安全策略、端口状态和监督器语义合并成一个确定的启动决策。

`resolveGatewayRunOptions` 负责参数继承。Gateway 命令存在父子 commander 关系，某些选项可能挂在父命令上；这个函数保证真正启动时能看到完整选项。

`readGatewayStartupConfig` 读取配置快照，并把读取过程纳入启动 trace。它返回 `cfg`、原始 `snapshot` 和可转交给 server 的 `startupConfigSnapshotRead`，避免后续启动阶段重复读取或丢失配置元数据。

`getGatewayStartGuardErrors` 是配置启动守卫。它防止缺失配置、缺失 `gateway.mode` 或非 local 模式被静默启动，尤其在服务模式下会用 78 退出码避免 supervisor 重启风暴。

`resolveGatewayPasswordOption` 处理 `--password` 与 `--password-file` 的互斥，并通过 secret-file 读取文件密码。`warnInlinePasswordFlag` 只是安全提醒：命令行明文密码可能出现在进程列表中。

`shouldBlockGatewayBindWithoutExplicitAuth` 是网络暴露安全闸门。它把“非 loopback 绑定”和“没有共享密钥”组合视为危险，除非认证模式是 `trusted-proxy`。

`runGatewayLoopWithSupervisedLockRecovery` 处理被监督运行时的锁冲突。如果发现已有 Gateway 锁，它会探测 `/healthz`：健康则让现有进程继续控制；systemd 下会抛出带 78 退出语义的锁错误，避免 `Restart=always` 造成循环；不健康则短暂等待重试，超时后失败。

`probeGatewayHealthz` 和 `normalizeGatewayHealthProbeHost` 是健康探测辅助：当绑定地址是 `0.0.0.0` 或 `::` 时，探测会改用 `127.0.0.1`。

`maybeLogPendingControlUiBuild` 只做启动提示：当 Control UI 未显式禁用且资产缺失时，提示首次启动可能构建 UI 资产。

## 修改风险

第一类风险是安全回归。`bind`、`auth`、`token/password`、`trusted-proxy` 和 Tailscale 的组合决定 Gateway 是否暴露到本机外。放宽 `shouldBlockGatewayBindWithoutExplicitAuth`、默认 bind 策略或认证解析，可能让无认证 Gateway 暴露到 LAN、容器端口映射或 tailnet。

第二类风险是升级/配置兼容。`getGatewayStartGuardErrors`、future-version guard、`EXIT_CONFIG_ERROR = 78` 和 config snapshot 传递都服务于启动安全与可恢复性。错误改动可能让损坏配置被继续使用，或者让 systemd 进入重启风暴。

第三类风险是启动性能。该文件刻意使用动态导入和 startup trace，避免 CLI 冷启动或帮助命令加载 Gateway 全量依赖。把 `../../gateway/server.js`、auth、diagnostic bundle 等改成顶层静态导入，可能影响 CLI 体验和测试中的 cold import 假设。

第四类风险是进程生命周期。真正的锁、信号、重启循环在 `src/cli/gateway-cli/run-loop.ts`，本文件负责传入 `lockPort`、`healthHost` 和 `start` 回调。修改这些参数的含义，可能破坏 SIGTERM/SIGUSR1、更新重启、端口锁释放或健康探测。

第五类风险是测试策略。监督器恢复逻辑已有专门测试，改动 `runGatewayLoopWithSupervisedLockRecovery`、锁错误识别、退出码映射或健康探测 host 规则时，应同步更新 `src/cli/gateway-cli/run.supervised-lock.test.ts`。涉及 Gateway lazy-loading 或 bundled plugin artifact 的改动，还需要注意 `src/gateway/AGENTS.md` 中关于热路径和构建验证的约束。
