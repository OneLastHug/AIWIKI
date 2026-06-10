# 目录：src/utils

## 它负责什么

`src/utils` 是这个仓库的基础能力层，放的是跨流程复用的通用逻辑，而不是某个单一功能的页面或命令。根据当前片段推断，它覆盖了 CLI 启动、REPL 交互、Claude API 请求、会话恢复、权限控制、终端显示、模型能力判断、路径与环境处理、日志与诊断、工具链适配等一整套底层支撑。

从调用面看，这个目录不是“一个工具库”，而更像仓库内部的公共基础设施。`src/main.tsx`、`src/screens/REPL.tsx`、`src/services/api/claude.ts` 这些主链路文件都大量依赖这里的模块，说明 `src/utils` 承担了“把复杂流程拆成可复用小块”的职责。

## 直接子目录地图

`src/utils` 的第一层子目录很多，但可以按职责分组来看，不必逐个文件背诵。

- 测试镜像层：`__tests__`
- 平台与外部接入：`background`、`claudeInChrome`、`computerUse`、`deepLink`、`dxt`、`nativeInstaller`、`teleport`
- 核心交互与状态：`hooks`、`messages`、`processUserInput`、`session` 相关能力主要分散在若干文件中
- 模型与 API 辅助：`model`、`mcp`、`memory`、`telemetry`
- 权限与安全：`permissions`、`sandbox`、`secureStorage`
- 运行环境与 shell：`bash`、`shell`、`powershell`、`git`、`github`、`cwd`、`env*`
- 产品功能域：`plugins`、`settings`、`skills`、`suggestions`、`swarm`、`task`、`todo`、`ultraplan`

顶层同时还有大量直接 `.ts` 文件，例如 `api.ts`、`config.ts`、`context.ts`、`errors.ts`、`messages.ts`、`sessionRestore.ts`、`systemPrompt.ts`、`queryProfiler.ts`、`toolPool.ts`、`pipeTransport.ts`、`fileStateCache.ts`、`conversationRecovery.ts` 等，说明这里既有通用工具，也有贴近主流程的业务胶水层。

## 关键入口

这个目录本身没有单独的“启动入口”，它的关键入口是被上层流程反复引用的那些总线模块。

- `src/utils/api.ts`：和 API 请求上下文、日志、上下文指标相关，是 `src/main.tsx` 和 `src/services/api/claude.ts` 的重要依赖。
- `src/utils/context.ts`、`src/utils/model/*`：负责模型能力、推理上下文、thinking token 等决策。
- `src/utils/errors.ts`、`src/utils/debug.ts`、`src/utils/cwd.ts`：贯穿启动、异常处理和运行时定位。
- `src/utils/sessionRestore.ts`、`src/utils/conversationRecovery.ts`：负责恢复会话和消息历史，是“断线后继续工作”的关键。
- `src/utils/messages.ts`、`src/utils/contentArray.ts`、`src/utils/messagePredicates.ts`：消息结构与消息流加工的公共层。
- `src/utils/permissions/*`、`src/utils/sandbox/*`：权限、沙箱、自动模式相关的核心控制点。
- `src/utils/claudeInChrome/*`、`src/utils/computerUse/*`、`src/utils/deepLink/*`：外部能力接入的子系统入口。

## 主流程位置

主流程并不在 `src/utils` 内部，而是“从上层流程下沉到这里”。

- 启动阶段：`src/entrypoints/cli.tsx` 进入后，`src/main.tsx` 会拉起大量 `src/utils/*`，包括参数解析、清理注册、会话注册、错误处理、当前目录、session 恢复等。
- 交互阶段：`src/screens/REPL.tsx` 是最密集的消费点之一，它会调用 `tokenBudget`、`QueryGuard`、`systemPrompt`、`toolPool`、`sessionState`、`fileHistory`、`permissions`、`conversationRecovery`、`queryProfiler` 等模块，把用户输入、工具调用、消息展示和自动模式串起来。
- API 阶段：`src/services/api/claude.ts` 负责请求 Claude 接口时的上下文拼装、消息转换、模型能力判断、token 统计、日志与追踪，依赖 `context`、`effort`、`messages`、`tokens`、`model`、`telemetry` 等工具。
- 恢复与续跑：`src/query.ts` 和 `src/QueryEngine.ts` 会把 `src/utils` 里的会话、历史、错误、缓存、消息整理能力串成一轮完整对话循环。

换句话说，`src/utils` 是这些主流程的“地基”，主流程文件决定什么时候用，`src/utils` 决定具体怎么做。

## 推荐阅读顺序

1. 先看 `src/utils/api.ts`、`src/utils/errors.ts`、`src/utils/context.ts`，建立这个目录的公共层认知。
2. 再看 `src/utils/messages.ts`、`src/utils/contentArray.ts`、`src/utils/conversationRecovery.ts`，理解消息与历史是怎么被组织的。
3. 接着看 `src/utils/sessionRestore.ts`、`src/utils/sessionState.ts`、`src/utils/fileStateCache.ts`，补上会话连续性。
4. 然后看 `src/utils/permissions/*`、`src/utils/sandbox/*`、`src/utils/pipeTransport.ts`，理解运行时控制边界。
5. 最后再按需进入 `bash/`、`computerUse/`、`claudeInChrome/`、`deepLink/`、`plugins/` 这些子系统。

## 常见误区

- 把 `src/utils` 当成“纯粹的杂项集合”。实际上它是仓库的底层公共层，很多主流程都依赖这里。
- 只看顶层文件，忽略子目录。真正复杂的逻辑往往在 `bash/`、`computerUse/`、`permissions/`、`telemetry/`、`mcp/` 这类子系统里。
- 误把某个工具文件当成独立入口。多数模块是被 `src/main.tsx`、`src/screens/REPL.tsx`、`src/services/api/claude.ts` 组合调用的。
- 看到 `.js` 后缀就以为是 JS 源码。这里很多导入写成 `*.js`，但实际是 TypeScript 源文件在构建期映射后的结果。
- 忽略 `__tests__`。这个目录的测试覆盖很密，说明很多工具函数是被当作稳定基础设施来维护的。
