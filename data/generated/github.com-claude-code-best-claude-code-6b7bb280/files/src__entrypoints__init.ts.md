# 文件：src/entrypoints/init.ts

## 一句话定位
`src/entrypoints/init.ts` 是整个 CLI 启动期的“全局初始化门闸”，负责在主业务逻辑启动前，把配置系统、运行时环境、清理钩子、网络代理、日志/分析、远程设置和可选遥测等基础设施按正确顺序装起来。根据当前片段推断，它是 `main.tsx` 进入完整 CLI 之前最关键的预处理层之一。

## 它暴露/定义了什么
这个文件对外最重要的导出有两个：`init()` 和 `initializeTelemetryAfterTrust()`。前者是一次性的异步总初始化入口，内部用 `memoize` 保证同一进程里重复调用不会重复做重活；后者是在“信任已建立”之后再补启动遥测的入口。文件内部还维护了 `telemetryInitialized` 这个模块级状态，用来防止 OpenTelemetry 重复初始化。

## 谁调用它
根据当前片段推断，主要调用方是 `src/main.tsx`：它在完成一些早期参数和状态判断后会 `await init()`，然后在信任对话或启动阶段结束后调用 `initializeTelemetryAfterTrust()`。另外 `src/interactiveHelpers.tsx` 也会通过 `setImmediate(() => initializeTelemetryAfterTrust())` 间接触发它，说明这个模块不只服务于完整交互式 CLI，也服务于某些交互辅助路径。

## 它调用谁
`init()` 依赖并驱动了大量底层模块。它会先启用配置系统 `enableConfigs()`，再设置主题回调 `setThemeConfigCallbacks()`，随后应用“安全”的环境变量 `applySafeConfigEnvironmentVariables()` 和证书配置 `applyExtraCACertsFromConfig()`。之后它会挂上 `setupGracefulShutdown()`，并通过动态导入启动一组异步后台任务：`firstPartyEventLogger`、`growthbook`、余额轮询、OAuth 账户信息补全、JetBrains 检测、仓库探测、远程管理设置/策略限制的预加载。它还会配置 `configureGlobalMTLS()`、`configureGlobalAgents()`，初始化 `initSentry()`、`initUser()`、`initLangfuse()`，预热 `preconnectAnthropicApi()`，以及按需启动 `upstreamproxy`、`setShellIfWindows()`、LSP 清理、swarm team 清理和 scratchpad 目录。

`initializeTelemetryAfterTrust()` 则最终会落到 `doInitializeTelemetry()` 和 `setMeterState()`，后者动态导入 `../utils/telemetry/instrumentation.js`，再调用 `initializeTelemetry()` 并把 meter 注入到 `setMeter()`。

## 核心流程
它的核心流程可以理解为“先建立安全底座，再放开高权限能力”。第一步是验证和启用配置，保证后续读取 `settings.json` 的逻辑可用；第二步只应用不会引发信任风险的环境变量和 CA 证书，避免过早泄露或污染运行环境；第三步注册退出清理，确保进程退出时能收尾。接着它启动一批非阻塞的后台预热任务，把分析、账户信息、远程设置、仓库信息、网络连接和平台检测尽量前移，但不阻塞首帧。真正的后半段则是网络与可观测性：先配好 mTLS / proxy / Sentry / Langfuse，再在用户授信后补开遥测。最后，它还负责处理配置解析失败：非交互模式直接写 stderr 并退出，交互模式则动态加载 `InvalidConfigDialog`，避免把 React 相关依赖提前拉进来。

## 关键函数的高层作用
`init()` 是总编排器，关注“顺序”和“幂等”；`initializeTelemetryAfterTrust()` 是遥测的二阶段启动器，关注“等信任、再启用”；`doInitializeTelemetry()` 是真正的遥测幂等保护层，负责跳过未启用场景并处理失败回滚；`setMeterState()` 是把 OpenTelemetry 结果接到应用状态里的适配层。其余像 `profileCheckpoint()`、`logForDiagnosticsNoPII()`、`registerCleanup()` 更像是贯穿流程的基础设施，不承担业务决策，但决定启动过程是否可观测、可恢复。

## 修改风险
这个文件改动风险很高，因为它处在进程启动链最前面，任何顺序调整都可能引发“配置还没读完就发起网络请求”“信任未建立就加载高风险能力”“清理钩子没注册导致资源泄漏”这类问题。最需要小心的是三个点：一是 `applySafeConfigEnvironmentVariables()` 与 `applyConfigEnvironmentVariables()` 的分层，前者只能做安全子集；二是 `telemetryInitialized` 与 `memoize` 的双重幂等控制，改坏后容易出现重复初始化或无法重试；三是动态导入和异常分支，尤其是 `ConfigParseError` 的非交互退出逻辑，动错会直接破坏 JSON/脚本场景。总体上，这里不适合做大重构，任何改动都应尽量保持“只改一个环节，不改启动顺序”的原则。
