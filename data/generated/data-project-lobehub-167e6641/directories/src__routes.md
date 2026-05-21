# 目录：src/routes

## 它负责什么
`src/routes` 是 LobeHub 代码树中的一个功能区域。下面的说明基于真实目录结构和被选中的源码文件生成，后续 Codex 深度解释会继续补全更细的调用关系。

## 下面有哪些子目录
- 没有发现直接子目录。

## 下面有哪些重要文件
- 没有发现直接文件，主要内容在更深层子目录。

## 文件树节选
```text
src/routes/(main)/settings/provider/features/ModelList/ModelConfigModal/index.tsx
src/routes/(main)/settings/service-model/index.tsx
src/routes/(main)/(create)/video/features/ConfigPanel/components/ModelSelect/index.tsx
src/routes/(main)/(create)/image/features/ConfigPanel/components/ModelSelect/index.tsx
src/routes/(main)/settings/provider/features/ModelList/CreateNewModelModal/index.tsx
src/routes/(main)/settings/provider/features/ModelList/SortModelModal/index.tsx
src/routes/(main)/settings/provider/features/ModelList/EnabledModelList/index.tsx
src/routes/(main)/settings/provider/features/ModelList/index.tsx
src/routes/(main)/settings/provider/features/ModelList/ModelTitle/index.tsx
src/routes/(main)/community/(detail)/model/features/Sidebar/RelatedProviders/index.tsx
src/routes/(main)/community/(detail)/provider/features/Sidebar/RelatedModels/index.tsx
src/routes/(main)/community/(detail)/provider/features/Details/Overview/ModelList/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/Overview/ProviderList/index.tsx
src/routes/(main)/community/(list)/model/_layout/index.tsx
src/routes/(main)/settings/provider/features/ProviderConfig/UpdateProviderInfo/index.tsx
src/routes/(main)/settings/provider/features/ProviderConfig/OAuthDeviceFlowAuth/index.tsx
src/routes/(main)/settings/provider/features/ProviderConfig/index.tsx
src/routes/(main)/group/_layout/Sidebar/GroupConfig/Header/index.tsx
src/routes/(mobile)/settings/provider/_layout/index.tsx
src/routes/(main)/settings/_layout/ContextProvider/index.tsx
src/routes/(main)/home/_layout/Body/Agent/Modals/ConfigGroupModal/index.tsx
src/routes/(main)/settings/provider/_layout/Desktop/index.tsx
src/routes/(main)/page/_layout/index.tsx
src/routes/onboarding/components/KlavisServerList/index.tsx
src/routes/(main)/resource/features/store/index.ts
src/routes/(main)/agent/profile/features/store/index.ts
src/routes/(main)/community/(list)/model/index.tsx
src/routes/(main)/community/(detail)/model/index.tsx
src/routes/(main)/community/(list)/model/features/List/index.tsx
src/routes/(main)/community/(detail)/model/features/Sidebar/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/index.tsx
src/routes/(main)/community/(list)/model/features/Category/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/Overview/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/Related/index.tsx
src/routes/(main)/community/(detail)/model/features/Sidebar/ActionButton/index.tsx
src/routes/(main)/community/(detail)/model/features/Sidebar/Related/index.tsx
src/routes/(main)/community/(detail)/model/features/Details/Parameter/index.tsx
src/routes/(main)/settings/stats/features/usage/UsageCards/ActiveModels/index.tsx
src/routes/(main)/(create)/video/features/ConfigPanel/index.ts
src/routes/(main)/(create)/image/features/ConfigPanel/index.ts
src/routes/(mobile)/chat/features/Topic/features/AgentConfig/index.tsx
src/routes/(mobile)/(home)/features/SessionListContent/Modals/ConfigGroupModal/index.tsx
src/routes/(mobile)/chat/features/Topic/features/AgentConfig/Header/index.tsx
src/routes/(main)/settings/provider/(list)/index.tsx
src/routes/(main)/community/(list)/provider/index.tsx
src/routes/(main)/community/(detail)/provider/index.tsx
src/routes/(main)/(create)/image/features/ConfigPanel/components/InputNumber/index.tsx
src/routes/(main)/settings/provider/index.tsx
src/routes/(main)/settings/provider/detail/index.tsx
src/routes/(main)/settings/provider/ProviderMenu/index.tsx
src/routes/(main)/(create)/image/features/ConfigPanel/components/AspectRatioSelect/index.tsx
src/routes/(main)/(create)/image/features/ConfigPanel/components/Select/index.tsx
src/routes/(main)/(create)/image/features/ConfigPanel/components/MultiImagesUpload/index.tsx
src/routes/(main)/settings/provider/detail/newapi/index.tsx
src/routes/(main)/settings/provider/detail/openai/index.tsx
src/routes/(main)/community/(list)/provider/features/List/index.tsx
src/routes/(main)/settings/provider/detail/ollama/index.tsx
src/routes/(main)/page/index.tsx
src/routes/(main)/community/(detail)/provider/features/Sidebar/index.tsx
src/routes/(main)/settings/provider/detail/default/index.tsx
src/routes/(main)/community/(detail)/mcp/features/Sidebar/ServerConfig.tsx
src/routes/(mobile)/_layout/index.tsx
src/routes/(main)/community/(detail)/provider/features/Details/index.tsx
src/routes/(popup)/_layout/index.tsx
src/routes/(main)/settings/provider/detail/azureai/index.tsx
src/routes/(main)/settings/provider/detail/cloudflare/index.tsx
src/routes/(main)/settings/provider/detail/github/index.tsx
src/routes/(main)/settings/provider/detail/azure/index.tsx
src/routes/(main)/settings/provider/ProviderMenu/SortProviderModal/index.tsx
src/routes/(main)/settings/provider/(list)/ProviderGrid/index.tsx
src/routes/(main)/settings/provider/detail/bedrock/index.tsx
src/routes/(main)/settings/provider/detail/vertexai/index.tsx
src/routes/(main)/settings/provider/detail/comfyui/index.tsx
src/routes/(main)/_layout/index.tsx
src/routes/(main)/settings/profile/features/SSOProvidersList/index.tsx
src/routes/onboarding/_layout/index.tsx
src/routes/(main)/settings/provider/features/CreateNewProvider/index.tsx
src/routes/(main)/(task-workspace)/_layout/index.tsx
src/routes/(main)/agent/[topicId]/page/index.tsx
src/routes/(main)/devtools/_layout/index.tsx
...
```

## 小白阅读建议
先看本目录下的 `index`、`route`、`store`、`service`、`schema`、`config` 等名字明显的文件，再顺着导入关系读更深层文件。
