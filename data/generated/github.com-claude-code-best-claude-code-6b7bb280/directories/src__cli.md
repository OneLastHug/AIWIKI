# 目录：src/cli

## 它可能负责什么
这个目录包含 37 个被抽样展示的文件。请从文件命名、子目录和关键源码入手理解它在项目中的职责。

## 文件列表节选
```text
src/cli/bg.ts
src/cli/remoteIO.ts
src/cli/up.ts
src/cli/ndjsonSafeStringify.ts
src/cli/rollback.ts
src/cli/print.ts
src/cli/updateCCB.ts
src/cli/structuredIO.ts
src/cli/exit.ts
src/cli/__tests__/userFacingErrorMessages.test.ts
src/cli/transports/HybridTransport.ts
src/cli/transports/transportUtils.ts
src/cli/transports/WorkerStateUploader.ts
src/cli/transports/SSETransport.ts
src/cli/transports/ccrClient.ts
src/cli/transports/SerialBatchEventUploader.ts
src/cli/transports/WebSocketTransport.ts
src/cli/transports/Transport.ts
src/cli/transports/__tests__/SSETransport.test.ts
src/cli/handlers/auth.ts
src/cli/handlers/templateJobs.ts
src/cli/handlers/agents.ts
src/cli/handlers/autoMode.ts
src/cli/handlers/mcp.tsx
src/cli/handlers/plugins.ts
src/cli/handlers/ant.ts
src/cli/handlers/autonomy.ts
src/cli/handlers/util.tsx
src/cli/handlers/__tests__/autonomy.test.ts
src/cli/bg/tail.ts
src/cli/bg/engine.ts
src/cli/bg/__tests__/detached.test.ts
src/cli/bg/__tests__/engine.test.ts
src/cli/bg/__tests__/tail.test.ts
src/cli/bg/engines/detached.ts
src/cli/bg/engines/index.ts
src/cli/bg/engines/tmux.ts
```

## 小白阅读建议
- 先看项目说明、`index` 入口、路由、业务服务、类型/结构定义等文件。英文文件名只是代码命名，不要求先理解英文语义。
- 暂时跳过构建产物、测试快照和重复样板。
- 如果这里是业务目录，优先找“谁调用它”和“它调用谁”。
