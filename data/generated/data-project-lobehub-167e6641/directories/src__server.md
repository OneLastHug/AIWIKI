# 目录：src/server

## 它负责什么
`src/server` 是 LobeHub 代码树中的一个功能区域。下面的说明基于真实目录结构和被选中的源码文件生成，后续 Codex 深度解释会继续补全更细的调用关系。

## 下面有哪些子目录
- 没有发现直接子目录。

## 下面有哪些重要文件
- 没有发现直接文件，主要内容在更深层子目录。

## 文件树节选
```text
src/server/services/email/README.md
src/server/routers/lambda/config/index.ts
src/server/routers/lambda/__tests__/integration/README.md
src/server/routers/tools/index.ts
src/server/routers/async/index.ts
src/server/routers/mobile/index.ts
src/server/routers/lambda/index.ts
src/server/routers/tools/_helpers/index.ts
src/server/routers/lambda/image/index.ts
src/server/routers/lambda/video/index.ts
src/server/routers/lambda/market/index.ts
src/server/services/riskControl/routerAlertNotification.ts
src/server/services/messenger/MessengerRouter.ts
src/server/services/bot/BotMessageRouter.ts
src/server/routers/lambda/_schema/context.ts
src/server/routers/lambda/_schema/documentHistory.ts
src/server/routers/lambda/aiModel.ts
src/server/routers/lambda/aiProvider.ts
src/server/routers/lambda/agentBotProvider.ts
src/server/runtimeConfig/providers/index.ts
src/server/services/comfyui/config/modelRegistry.ts
src/server/services/comfyui/config/sdModelRegistry.ts
src/server/services/comfyui/config/fluxModelRegistry.ts
src/server/routers/lambda/config/index.test.ts
src/server/services/agentSignal/index.ts
src/server/services/agentRuntime/index.ts
src/server/services/skill/index.ts
src/server/services/skillManagement/index.ts
src/server/services/queue/index.ts
src/server/services/bot/index.ts
src/server/services/taskScheduler/index.ts
src/server/services/messenger/index.ts
src/server/services/doc/index.tsx
src/server/modules/PluginStore/index.ts
src/server/services/email/index.ts
src/server/services/home/index.ts
src/server/services/user/index.ts
src/server/services/followUpAction/index.ts
src/server/services/oidc/index.ts
src/server/services/aiChat/index.ts
src/server/services/oauthDeviceFlow/index.ts
src/server/services/webhookUser/index.ts
src/server/modules/AssistantStore/index.ts
src/server/services/taskReview/index.ts
src/server/services/notebook/index.ts
src/server/services/chunk/index.ts
src/server/services/systemAgent/index.ts
src/server/services/agentGroup/index.ts
src/server/services/taskTemplate/index.ts
src/server/services/sandbox/index.ts
src/server/services/usage/index.ts
src/server/services/desktopRelease/index.ts
src/server/services/changelog/index.ts
src/server/services/search/index.ts
src/server/services/heterogeneousAgent/index.ts
src/server/services/klavis/index.ts
src/server/services/agent/index.ts
src/server/services/toolExecution/index.ts
src/server/services/brief/index.ts
src/server/services/knowledgeBase/index.ts
src/server/services/generation/index.ts
src/server/services/taskGraph/index.ts
src/server/services/taskRunner/index.ts
src/server/services/file/index.ts
src/server/services/message/index.ts
src/server/services/document/index.ts
src/server/services/mcp/index.ts
src/server/services/market/index.ts
src/server/services/agentDocuments/index.ts
src/server/services/gateway/index.ts
src/server/services/task/index.ts
src/server/services/taskLifecycle/index.ts
src/server/services/onboarding/index.ts
src/server/services/agentDocumentVfs/index.ts
src/server/services/discover/index.ts
src/server/services/agentEvalRun/index.ts
src/server/services/aiAgent/index.ts
src/server/services/agentSignal/services/selfIteration/index.ts
src/server/services/agentSignal/procedure/accumulators/index.ts
src/server/services/messenger/platforms/telegram/index.ts
...
```

## 小白阅读建议
先看本目录下的 `index`、`route`、`store`、`service`、`schema`、`config` 等名字明显的文件，再顺着导入关系读更深层文件。
