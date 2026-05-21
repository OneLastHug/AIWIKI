# 目录：src

## 它负责什么
`src` 是 LobeHub 代码树中的一个功能区域。下面的说明基于真实目录结构和被选中的源码文件生成，后续 Codex 深度解释会继续补全更细的调用关系。

## 下面有哪些子目录
- `app`：`src/app` 下的子功能区，建议展开继续读。
- `business`：`src/business` 下的子功能区，建议展开继续读。
- `components`：`src/components` 下的子功能区，建议展开继续读。
- `config`：`src/config` 下的子功能区，建议展开继续读。
- `const`：`src/const` 下的子功能区，建议展开继续读。
- `envs`：`src/envs` 下的子功能区，建议展开继续读。
- `features`：`src/features` 下的子功能区，建议展开继续读。
- `helpers`：`src/helpers` 下的子功能区，建议展开继续读。
- `hooks`：`src/hooks` 下的子功能区，建议展开继续读。
- `layout`：`src/layout` 下的子功能区，建议展开继续读。
- `libs`：`src/libs` 下的子功能区，建议展开继续读。
- `locales`：`src/locales` 下的子功能区，建议展开继续读。
- `routes`：`src/routes` 下的子功能区，建议展开继续读。
- `server`：`src/server` 下的子功能区，建议展开继续读。
- `services`：`src/services` 下的子功能区，建议展开继续读。
- `spa`：`src/spa` 下的子功能区，建议展开继续读。
- `store`：`src/store` 下的子功能区，建议展开继续读。
- `styles`：`src/styles` 下的子功能区，建议展开继续读。
- `types`：`src/types` 下的子功能区，建议展开继续读。
- `utils`：`src/utils` 下的子功能区，建议展开继续读。

## 下面有哪些重要文件
- 没有发现直接文件，主要内容在更深层子目录。

## 文件树节选
```text
src/server/services/email/README.md
src/server/routers/lambda/config/index.ts
src/server/routers/lambda/__tests__/integration/README.md
src/routes/(main)/settings/provider/features/ModelList/ModelConfigModal/index.tsx
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
src/store/serverConfig/index.ts
src/server/routers/lambda/aiModel.ts
src/routes/(main)/settings/service-model/index.tsx
src/business/server/lambda-routers/config.ts
src/server/routers/lambda/aiProvider.ts
src/server/routers/lambda/agentBotProvider.ts
src/server/runtimeConfig/providers/index.ts
src/routes/(main)/(create)/video/features/ConfigPanel/components/ModelSelect/index.tsx
src/routes/(main)/(create)/image/features/ConfigPanel/components/ModelSelect/index.tsx
src/routes/(main)/settings/provider/features/ModelList/CreateNewModelModal/index.tsx
src/routes/(main)/settings/provider/features/ModelList/SortModelModal/index.tsx
src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx
src/routes/(main)/settings/provider/features/ModelList/index.tsx
src/routes/(main)/settings/provider/features/ModelList/ModelTitle/index.tsx
src/routes/(main)/community/(detail)/model/features/Sidebar/RelatedProviders/index.tsx
src/routes/(main)/community/(detail)/provider/features/Sidebar/RelatedModels/index.tsx
src/server/services/comfyui/config/modelRegistry.ts
src/routes/(main)/community/(detail)/provider/features/Details/Overview/ModelList/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/Overview/ProviderList/index.tsx
src/server/services/comfyui/config/sdModelRegistry.ts
src/server/services/comfyui/config/fluxModelRegistry.ts
src/routes/(main)/community/(list)/model/_layout/index.tsx
src/routes/(main)/settings/provider/features/ProviderConfig/UpdateProviderInfo/index.tsx
src/routes/(main)/settings/provider/features/ProviderConfig/OAuthDeviceFlowAuth/index.tsx
src/routes/(main)/settings/provider/features/ProviderConfig/index.tsx
src/routes/(main)/group/_layout/Sidebar/GroupConfig/Header/index.tsx
src/store/serverConfig/Provider.tsx
src/routes/(mobile)/settings/provider/_layout/index.tsx
src/routes/(main)/settings/_layout/ContextProvider/index.tsx
src/routes/(main)/home/_layout/Body/Agent/Modals/ConfigGroupModal/index.tsx
src/server/routers/lambda/config/index.test.ts
src/routes/(main)/settings/provider/_layout/Desktop/index.tsx
src/routes/(main)/page/_layout/index.tsx
src/routes/onboarding/components/KlavisServerList/index.tsx
src/server/services/agentSignal/index.ts
src/server/services/agentRuntime/index.ts
src/server/services/skill/index.ts
src/server/services/skillManagement/index.ts
src/server/services/queue/index.ts
src/server/services/bot/index.ts
src/server/services/taskScheduler/index.ts
src/libs/router/index.ts
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
...
```

## 小白阅读建议
先看本目录下的 `index`、`route`、`store`、`service`、`schema`、`config` 等名字明显的文件，再顺着导入关系读更深层文件。
