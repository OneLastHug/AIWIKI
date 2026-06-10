# 目录：src/services/analytics
## 它负责什么
`src/services/analytics` 是 Claude Code 里“埋点与事件上报”的中枢目录，负责把应用内部的事件统一收集、补全元数据、做采样与脱敏，再分别送往 Datadog 和 1P（first-party）事件日志系统。根据当前片段推断，这个目录的设计目标不是单一上报器，而是一个可切换、可缓存、可回退的分析层：先在业务代码里统一调用 `logEvent()`，真正的后端路由由启动阶段挂上的 sink 决定。

它的核心职责可以概括为四件事：事件入口统一、元数据统一、后端分发统一、失败重试统一。这里也承担了不少隐私边界工作，比如 `_PROTO_*` 字段只允许进入受控的 1P 通道，进入 Datadog 前必须剔除。

## 直接子目录地图
这个目录下当前没有再往下的子目录，只有一组顶层 `.ts` 文件，角色分得很清楚：

- `index.ts`：对外公共 API，提供 `logEvent()`、`logEventAsync()`、`attachAnalyticsSink()`、`stripProtoFields()`。
- `sink.ts`：真正的路由层，把事件分发到 Datadog 和 1P logger。
- `datadog.ts`：Datadog 发送端，负责批量、过滤、flush 和 shutdown。
- `firstPartyEventLogger.ts`：1P 事件日志主实现，基于 OpenTelemetry，负责采样、补全和初始化。
- `firstPartyEventLoggingExporter.ts`：1P exporter，负责把日志批量送到后端，并处理失败重试和落盘恢复。
- `metadata.ts`：共享元数据构建与清洗逻辑，是所有 analytics 系统的公共数据源。
- `growthbook.ts`：动态配置与特性开关读取层，给采样、批次配置、刷新通知提供数据。
- `config.ts`：全局 analytics 开关，决定什么环境下应整体禁用分析能力。
- `sinkKillswitch.ts`：按 sink 粒度的 killswitch，允许单独关闭 Datadog 或 1P。

## 关键入口
最重要的入口是 `index.ts`。业务侧几乎都只依赖这里：先调用 `logEvent()` 或 `logEventAsync()`，如果 sink 还没挂上，事件会先进入队列，等 `attachAnalyticsSink()` 被调用后再统一冲刷。这避免了初始化顺序问题，也减少了启动阶段的耦合。

第二个入口是 `sink.ts`。它把抽象事件变成真实路由逻辑：先做事件采样，再判断 Datadog 是否可发，最后把同一份事件同时送往 Datadog 和 1P。`initializeAnalyticsSink()` 负责把这个路由器挂到 `index.ts` 的全局 sink 上。

第三个入口是启动链路。根据当前片段，`src/entrypoints/cli.tsx` 会动态加载 `initializeAnalyticsSink`、`shutdownDatadog`、`shutdown1PEventLogging`，说明 analytics 的生命周期是由 CLI 启动/退出流程统一托管的，而不是由单个业务模块自己管理。

## 主流程位置
主流程基本是“事件产生 -> 入口队列 -> sink 路由 -> 双写后端 -> 退出时 flush”。

1. 业务层调用 `logEvent()` / `logEventAsync()`。
2. `index.ts` 如果还没 attach sink，就先排队。
3. 启动阶段调用 `initializeAnalyticsSink()`，把 `sink.ts` 提供的实现挂进去。
4. `sink.ts` 先执行 `shouldSampleEvent()`，再根据 `isSinkKilled('datadog')` 和 `isSinkKilled('firstParty')` 决定是否分发。
5. Datadog 路径会先通过 `stripProtoFields()` 去掉 `_PROTO_*`，保证通用后端看不到敏感字段。
6. 1P 路径会保留完整 payload，由 `firstPartyEventLoggingExporter.ts` 再做更细的字段搬运和防御性清理。
7. 退出时由 `shutdownDatadog()` 和 `shutdown1PEventLogging()` 收尾，避免缓冲队列丢失。

其中 `metadata.ts` 和 `growthbook.ts` 是两条“横切支撑线”：前者负责把会话、模型、平台、MCP、文件扩展名等上下文统一整理出来，后者负责把远端动态配置变成可缓存、可刷新、可复用的数据源。

## 推荐阅读顺序
1. `index.ts`：先看公共 API 和队列机制，理解这个目录对外暴露什么。
2. `sink.ts`：再看路由层，理解事件如何分流到两个后端。
3. `metadata.ts`：补元数据体系，理解埋点字段是怎么拼出来的。
4. `firstPartyEventLogger.ts`：看 1P 侧如何做采样、初始化和批处理。
5. `firstPartyEventLoggingExporter.ts`：看失败重试、落盘恢复和批量发送。
6. `datadog.ts`：最后看 Datadog 侧的发送与过滤。
7. `growthbook.ts`、`config.ts`、`sinkKillswitch.ts`：作为开关层补读。

## 常见误区
- 把 `index.ts` 当成“真正上报器”。它其实只是入口和队列，真正的发送逻辑在 `sink.ts` 及其下游。
- 忽略 `_PROTO_*` 的边界。它们只适合受控的 1P 通道，不能直接进入 Datadog 这类通用后端。
- 以为 analytics 只有一个开关。这里至少有三层：全局禁用 (`config.ts`)、按 sink 禁用 (`sinkKillswitch.ts`)、以及事件级采样 (`firstPartyEventLogger.ts`)。
- 忘记初始化顺序。事件可能在 sink 挂载前就被记录，所以 `attachAnalyticsSink()` 的队列冲刷逻辑是设计核心，不是附属功能。
- 误把 `growthbook.ts` 当纯配置读取。它还承担刷新通知和长期对象重建的触发职责，影响 1P logger 这类长生命周期组件。
- 在 `is1PEventLoggingEnabled()` 里再去调用 `isSinkKilled()`。文件注释已经明确提示这会递归，必须在 per-event dispatch 点判断。
