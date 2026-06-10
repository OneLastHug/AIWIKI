# 目录：src/infra

## 它负责什么

`src/infra` 是 OpenClaw 的基础设施层，放的是跨 CLI、gateway、channels、plugins 运行路径复用的底层能力。它不像 `src/channels` 那样代表某个通道实现，也不像 `src/plugins` 那样管理插件加载，而是提供“运行时需要但不属于单一业务域”的通用模块：命令安全与审批、出站消息投递、网络 fetch 与代理、文件和路径安全、设备身份与配对、gateway 进程管理、安装/包管理辅助、诊断事件、心跳提醒、归档和备份等。

这个目录的特点是文件多、领域簇明显、入口分散。根据当前片段推断，它没有一个统一的 `src/infra/index.ts` 总出口；上层代码通常按能力直接引用具体模块，例如 `src/infra/exec-approvals.ts`、`src/infra/outbound/message.ts`、`src/infra/net/runtime-fetch.ts`。测试也大多与实现同目录同名放置，例如 `src/infra/exec-safety.test.ts`、`src/infra/outbound/delivery-queue.test.ts`，说明这里的模块更偏“可组合工具和小型运行时”，不是单一服务。

## 直接子目录地图

`src/infra/command-analysis` 负责命令风险分析。这里有 `explain.ts`、`inline-eval.ts`、`risks.ts`、`policy.ts`，从命名看用于把 shell 命令拆解成风险、解释和策略判断，服务于 exec 审批、安全提示或命令展示。

`src/infra/command-explainer` 负责命令解释的结构化解析与格式化。关键文件包括 `index.ts`、`extract.ts`、`format.ts`、`tree-sitter-runtime.ts`、`types.ts`。它更像 parser/formatter 层，`command-analysis` 则更偏风险语义层。

`src/infra/format-time` 放时间格式化工具，包括 `format-datetime.ts`、`format-duration.ts`、`format-relative.ts`、`parse-offsetless-zoned-datetime.ts`。这是较独立的展示型工具簇。

`src/infra/net` 是网络基础设施。它包含 `runtime-fetch.ts`、`fetch-guard.ts`、`ssrf.ts`、`undici-runtime.ts`、`undici-global-dispatcher.ts`、`proxy-fetch.ts`、`proxy-env.ts`、`http-connect-tunnel.ts` 等，负责 fetch 封装、SSRF 防护、Undici dispatcher、代理环境解析和本地 origin 绕过等。

`src/infra/net/proxy` 是网络代理的更细分运行时，包含 `managed-proxy-undici.ts`、`proxy-lifecycle.ts`、`proxy-validation.ts`、`proxy-tls.ts`、`active-proxy-state.ts`。根据当前片段推断，它处理托管代理生命周期、校验、TLS 和全局代理状态。

`src/infra/outbound` 是出站消息与回复投递核心。这里有单独的 scoped `AGENTS.md`，说明它处在热路径上：reply、action、media、channel contract 都会经过这里。关键文件包括 `message.ts`、`deliver.ts`、`outbound-send-service.ts`、`delivery-queue.ts`、`target-resolver.ts`、`channel-selection.ts`、`message-action-runner.ts`、`session-binding-service.ts`、`payloads.ts`。它把“要发什么、发到哪里、用哪个 channel、失败如何排队恢复”拆成多个小模块。

`src/infra/tls` 目录存在，但当前读取片段没有展开到具体文件。根据目录名和 `src/infra/net/proxy/proxy-tls.ts` 推断，它应承载 TLS 相关基础能力；如需精读应再单独查看。

## 关键入口

审批和命令执行安全的关键入口集中在根目录文件：`src/infra/exec-approvals.ts`、`src/infra/exec-approvals-effective.ts`、`src/infra/exec-safety.ts`、`src/infra/exec-command-resolution.ts`、`src/infra/exec-wrapper-resolution.ts`、`src/infra/exec-safe-bin-policy.ts`、`src/infra/approval-handler-bootstrap.ts`、`src/infra/approval-handler-runtime.ts`、`src/infra/approval-native-runtime.ts`。这些文件共同决定命令是否需要审批、审批请求如何展示、如何转交到 native/channel/gateway 层。

出站消息的入口在 `src/infra/outbound/message.ts`、`src/infra/outbound/deliver.ts`、`src/infra/outbound/outbound-send-service.ts`、`src/infra/outbound/message-action-runner.ts`。如果要理解机器人回复、工具消息、media/action 参数如何流向具体 channel，应从这里开始，而不是直接看某个 channel 的实现。

网络入口在 `src/infra/fetch.ts` 和 `src/infra/net/runtime-fetch.ts`。前者像通用 fetch 包装，后者更接近运行时网络策略聚合点。安全相关需要一起看 `src/infra/net/ssrf.ts`、`src/infra/net/fetch-guard.ts`、`src/infra/net/undici-global-dispatcher.ts`。

心跳入口在 `src/infra/heartbeat-runner.ts` 和 `src/infra/heartbeat-runner.runtime.ts`，周边有 `heartbeat-schedule.ts`、`heartbeat-events.ts`、`heartbeat-visibility.ts`、`heartbeat-wake.ts`。这组文件控制提醒何时触发、是否可见、如何发送、如何处理会话忙碌等状态。

设备、gateway、安装和本地环境入口分散在 `src/infra/device-bootstrap.ts`、`src/infra/device-identity.ts`、`src/infra/device-pairing.ts`、`src/infra/gateway-processes.ts`、`src/infra/gateway-lock.ts`、`src/infra/install-flow.ts`、`src/infra/npm-pack-install.ts`、`src/infra/package-update-steps.ts`、`src/infra/openclaw-root.ts`。

## 主流程位置

命令审批主流程大致是：命令先经过 `src/infra/command-explainer` 和 `src/infra/command-analysis` 提取结构、解释和风险，再进入 `src/infra/exec-safety.ts`、`src/infra/exec-approvals.ts`、`src/infra/exec-safe-bin-policy.ts` 判断策略；需要用户确认时，通过 `src/infra/approval-handler-runtime.ts`、`src/infra/approval-native-runtime.ts`、`src/infra/exec-approval-forwarder.ts` 转成可投递的审批请求。根据当前片段推断，`approval-view-model.ts` 和 `exec-approval-command-display.ts` 负责把内部判断整理成面向用户的显示模型。

出站消息主流程大致是：调用方构造 message/action 请求，进入 `src/infra/outbound/message.ts` 或 `message-action-runner.ts`；随后通过 `channel-selection.ts`、`target-resolver.ts`、`session-binding-service.ts`、`message-plan.ts` 决定目标和投递计划；最终由 `deliver.ts`、`deliver-runtime.ts`、`outbound-send-service.ts` 发出，失败或离线场景交给 `delivery-queue.ts`、`delivery-queue-storage.ts`、`delivery-queue-recovery.ts`。这个流程是 channel 热路径，不宜把插件发现、真实 delivery runtime 等重逻辑随意引入纯参数测试。

网络主流程在 `fetch.ts` 到 `net/runtime-fetch.ts` 之间组装，底层接 Undici、proxy、SSRF guard 和 redirect header 处理。gateway 生命周期主流程则散落在 `gateway-processes.ts`、`gateway-lock.ts`、`gateway-process-argv.ts`、`gateway-discovery-targets.ts`。本地持久化和路径安全常见支撑点是 `file-store.ts`、`json-file.ts`、`json-files.ts`、`fs-safe.ts`、`boundary-path.ts`、`boundary-file-read.ts`。

## 推荐阅读顺序

第一步先扫 `src/infra/outbound/AGENTS.md`，理解出站路径为什么强调热路径和窄测试。然后看目录簇而不是逐文件打开：先读 `src/infra/outbound/message.ts`、`src/infra/outbound/deliver.ts`、`src/infra/outbound/target-resolver.ts`，建立投递主线。

第二步看命令审批簇：`src/infra/command-explainer/index.ts`、`src/infra/command-analysis/risks.ts`、`src/infra/exec-approvals.ts`、`src/infra/approval-handler-runtime.ts`。这能把“命令是什么、风险是什么、谁来批准、如何展示”串起来。

第三步看网络与环境支撑：`src/infra/fetch.ts`、`src/infra/net/runtime-fetch.ts`、`src/infra/net/ssrf.ts`、`src/infra/net/proxy/managed-proxy-undici.ts`，再补 `src/infra/env.ts`、`src/infra/openclaw-root.ts`、`src/infra/fs-safe.ts`。

第四步按需求阅读边缘簇：调 gateway 看 `gateway-processes.ts`；调安装升级看 `install-flow.ts`、`package-update-steps.ts`；调提醒看 `heartbeat-runner.ts`；调设备配对看 `device-bootstrap.ts`、`device-pairing.ts`。

## 常见误区

不要把 `src/infra` 当成“杂物箱”。它虽然文件多，但多数文件围绕稳定基础能力组织：审批、出站、网络、路径、安装、gateway、诊断。新增逻辑时应先判断是否属于这些跨域基础能力，还是应该放到 `src/channels`、`src/plugins` 或具体 plugin。

不要从 channel 实现反推出站流程。回复、消息 action、media 和 channel target 的公共规则集中在 `src/infra/outbound`，直接改某个 channel 可能只修到单边行为，破坏其他 channel 或 plugin contract。

不要绕过命令安全簇直接执行 shell。exec 相关文件覆盖 allowlist、safe bin、wrapper trust、approval display、session target 等多个层面，单独改 `node-shell.ts` 或命令拼接逻辑容易漏掉审批和展示一致性。

不要把网络 fetch 简化成原生 `fetch`。这里存在 SSRF、防代理、本地 origin 绕过、Undici dispatcher、proxy lifecycle 等约束；新增网络请求应复用 `src/infra/fetch.ts` 或 `src/infra/net/runtime-fetch.ts` 这类现有入口。

不要逐个叶子文件背诵。overview 阶段更重要的是识别路径角色和主流程：`outbound` 管发消息，`command-analysis` 与 `command-explainer` 管命令理解，`net` 管网络安全与代理，根目录大量 `exec-*`、`approval-*`、`heartbeat-*`、`gateway-*`、`install-*` 文件是按能力前缀组织的模块簇。
