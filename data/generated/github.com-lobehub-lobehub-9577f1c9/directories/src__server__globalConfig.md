# 目录：src/server/globalConfig

## 它负责什么

`src/server/globalConfig` 是 LobeHub 服务端“全局运行配置”的汇总与解析层。它不直接做业务动作，而是把环境变量、内置模型清单、业务开关、认证开关、默认 Agent、知识库文件配置、系统 Agent、用户记忆抽取配置等，整理成前端和服务端都能消费的结构化配置。

可以把它理解成服务端配置适配器：

- 向前端/SPA 暴露可公开的全局配置，例如可用 AI Provider、认证方式、是否开启文件上传、视觉理解、Langfuse、系统 Agent、公开版 memory 配置。
- 向服务端业务逻辑提供默认配置，例如默认 Agent 配置、默认文件/知识库 embedding 配置、memory 抽取的私有配置。
- 把字符串形式的环境变量解析成类型更明确的对象，例如 `provider/model`、`key=value`、布尔值、数字、数组、嵌套字段。
- 隔离敏感信息，尤其是 `parseMemoryExtractionConfig` 中的 API Key，只在服务端私有配置中使用；下发到 `getServerGlobalConfig` 的是经过 `sanitizeAgent` 处理的公开配置。

目录本身没有子目录，所有文件都在 `src/server/globalConfig` 根下：

```text
genServerAiProviderConfig.ts
getServerAuthConfig.ts
index.ts
parseDefaultAgent.ts
parseFilesConfig.ts
parseMemoryExtractionConfig.ts
parseSystemAgent.ts
*.test.ts
```

## 关键组成

`index.ts` 是这个目录的主入口，核心导出有三个：

- `getServerGlobalConfig`
- `getServerDefaultAgentConfig`
- `getServerDefaultFilesConfig`

`getServerGlobalConfig` 是最重要的函数。它返回 `GlobalServerConfig`，内容包括：

- `aiProvider`：由 `genServerAiProvidersConfig` 生成的所有模型供应商配置。
- `defaultAgent.config`：由 `parseAgentConfig(DEFAULT_AGENT_CONFIG)` 解析出的默认 Agent 配置。
- `disableEmailPassword`、`enableEmailVerification`、`enableMagicLink`：来自 `authEnv` 的认证开关。
- `enableBusinessFeatures`：来自 `@lobechat/business-const` 的业务功能开关。
- `enableKlavis`、`enableLobehubSkill`、`enableMarketTrustedClient`：根据相关环境变量是否存在推导。
- `enableUploadFileToServer`：根据 `fileEnv.S3_SECRET_ACCESS_KEY` 判断是否支持上传到服务器。
- `enableVisualUnderstanding` 和 `visualUnderstanding`：由 `toolsEnv.VISUAL_UNDERSTANDING_PROVIDER`、`toolsEnv.VISUAL_UNDERSTANDING_MODEL` 决定。
- `agentGatewayUrl`：如果配置了 `appEnv.AGENT_GATEWAY_URL`，则下发给客户端，供异构 agent 或队列模式使用。
- `image`：目前包含 `defaultImageNum`。
- `memory.userMemory`：来自 `getPublicMemoryExtractionConfig`，只包含可公开的用户记忆抽取配置。
- `oAuthSSOProviders`：通过 `parseSSOProviders(authEnv.AUTH_SSO_PROVIDERS)` 解析 SSO Provider。
- `systemAgent`：由 `parseSystemAgent(appEnv.SYSTEM_AGENT)` 解析。
- `telemetry.langfuse`：Langfuse 是否启用。

`genServerAiProviderConfig.ts` 负责生成 AI Provider 配置。它会：

- 读取 `getLLMConfig()`，拿到各 Provider 的启用状态。
- 通过 `loadModels()` 加载内置模型列表。
- 从 `model-bank` 静态导出的模型中补充 provider 模型。
- 遍历 `ModelProvider` 的所有 provider。
- 按 provider 读取环境变量中的模型列表，例如默认读取 `${PROVIDER}_MODEL_LIST`，也可以通过 `modelListKey` 自定义。
- 调用 `extractEnabledModels` 解析启用模型。
- 调用 `transformToAiModelList` 生成服务端模型列表 `serverModelLists`。
- 支持 provider 特殊配置，例如 `enabledKey`、`modelListKey`、`withDeploymentName`、`fetchOnClient`。

`index.ts` 调用它时给部分 provider 加了定制逻辑，例如：

- `azure` 使用 `ENABLED_AZURE_OPENAI`，并开启 `withDeploymentName`。
- `bedrock` 使用 `ENABLED_AWS_BEDROCK` 和 `AWS_BEDROCK_MODEL_LIST`。
- `ollama` 在桌面端默认启用，且根据 `OLLAMA_PROXY_URL` 决定是否让客户端拉取。
- `lobehub` 只有在 `ENABLE_BUSINESS_FEATURES` 为真时强制启用。
- `deepseek` 被显式设置为启用。

`getServerAuthConfig.ts` 是一个轻量版全局配置入口，主要用于认证页面布局。它返回的 `GlobalServerConfig` 不包含完整 AI Provider 和复杂运行配置，只保留认证页需要的公共开关：

- `disableEmailPassword`
- `enableEmailVerification`
- `enableMagicLink`
- `enableMarketTrustedClient`
- `enableBusinessFeatures`
- `oAuthSSOProviders`
- 空的 `aiProvider`
- 空的 `telemetry`

这能避免 auth 页面为了少量开关加载完整模型/provider 配置。

`parseDefaultAgent.ts` 提供 `parseAgentConfig`，用于解析 `DEFAULT_AGENT_CONFIG`。它支持这种形式：

```text
model=gpt-4;params.temperature=0.7;enableAutoCreateTopic=true;plugins=search
```

解析特性包括：

- 用分号分隔多个 `key=value`。
- 支持引号包裹的字符串，允许值中包含分号。
- 自动把数字字符串转为 `number`。
- 自动把 `true` / `false` 转为 `boolean`。
- 支持英文逗号和中文逗号分隔的数组。
- 使用 `es-toolkit/compat` 的 `set` 支持嵌套路径，例如 `params.temperature=0.7`。
- 对 `plugins` 做特殊处理：如果只有一个字符串，也会转成数组。

`parseFilesConfig.ts` 提供 `parseFilesConfig`，用于解析知识库/文件相关的默认配置。它读取的主要是 `knowledgeEnv.DEFAULT_FILES_CONFIG`，支持的 key 是受保护白名单：

- `embedding_model`
- `reranker_model`
- `query_mode`

其中 `embedding_model` 和 `reranker_model` 的值必须是 `provider/model` 格式，解析后分别写入：

```ts
config.embeddingModel = { provider, model }
config.rerankerModel = { provider, model }
```

如果没有配置字符串，则返回 `DEFAULT_FILES_CONFIG`。如果格式不合法，会直接抛错。

`parseSystemAgent.ts` 提供 `parseSystemAgent`，用于解析 `appEnv.SYSTEM_AGENT`。它根据 `DEFAULT_SYSTEM_AGENT_CONFIG` 的 key 做白名单过滤，只允许系统已有的 agent key 被配置。格式也是逗号分隔的 `key=provider/model`。

它还有一个特殊 key：`default`。例如：

```text
default=openai/gpt-4.1-mini
```

会把这个默认 provider/model 应用到所有没有单独配置的系统 agent 上。

此外，`promptRewrite` 和 `autoSuggestion` 在被配置时会默认设置 `enabled: true`。这里源码中变量名写作 `defaultTrueLey`，根据当前片段推断应是 “default true key” 的拼写误差，但不影响逻辑。

`parseMemoryExtractionConfig.ts` 是目录里最复杂的解析器，负责用户记忆抽取相关配置。它分成两个层级：

- `parseMemoryExtractionConfig`：返回私有服务端配置 `MemoryExtractionPrivateConfig`，可能包含 API Key、Webhook Headers、S3 凭据、Upstash Workflow Headers、白名单等。
- `getPublicMemoryExtractionConfig`：返回可公开的 `GlobalMemoryExtractionConfig`，会移除 API Key，只保留前端需要知道的 provider/model/contextLimit/layers/concurrency 等。

它内部拆了多个 agent 配置：

- `agentGateKeeper`：用户记忆抽取的 gatekeeper agent。
- `agentBenchmarkLoCoMo`：benchmark 相关 agent，默认回退到 gatekeeper。
- `agentLayerExtractor`：分层抽取 agent，支持 `activity`、`context`、`experience`、`identity`、`preference` 五层。
- `agentPersonaWriter`：persona 写入 agent。
- `embedding`：用户记忆 embedding agent。

它还解析：

- `MEMORY_USER_MEMORY_CONCURRENCY`
- `MEMORY_USER_MEMORY_WHITELIST_USERS`
- `MEMORY_USER_MEMORY_WEBHOOK_HEADERS`
- `MEMORY_USER_MEMORY_WORKFLOW_EXTRA_HEADERS`
- 各 agent 的 preferred providers/models
- observability S3 配置
- benchmark feature flag

一个重要安全点是 `sanitizeAgent`：它复制 agent 配置后删除 `apiKey`，再返回公开配置。`getServerGlobalConfig` 调用的是 `getPublicMemoryExtractionConfig`，所以不会把 memory agent 的 API Key 下发给客户端。

## 上下游关系

上游主要是环境变量、常量和模型定义：

- `@/envs/app`：`DEFAULT_AGENT_CONFIG`、`SYSTEM_AGENT`、`AGENT_GATEWAY_URL`、market trusted client 配置。
- `@/envs/auth`：邮箱密码、邮箱验证、Magic Link、SSO Provider 等认证开关。
- `@/envs/file`：S3 Secret，用于判断是否支持服务端文件上传。
- `@/envs/image`：默认图片生成数量。
- `@/envs/knowledge`：默认文件/知识库配置。
- `@/envs/langfuse`：遥测开关。
- `@/envs/tools`：视觉理解 provider/model。
- `@/envs/llm`：各模型供应商的启用状态。
- `model-bank`：`ModelProvider`、静态模型列表。
- `@/business/client/model-bank/loadModels`：加载内置模型。
- `@lobechat/business-const`：业务功能和默认小模型 provider。
- `@lobechat/const`：默认小模型、默认用户记忆 embedding 模型。
- `@/const/settings`、`@/const/settings/knowledge`：系统 Agent 和文件配置默认值。

下游主要分为五类。

第一类是 SPA 初始化。`src/app/spa/[variants]/[[...path]]/route.ts` 在处理 GET 请求时调用 `getServerGlobalConfig()`，然后把结果放进 `SPAServerConfig.config`。这意味着前端应用启动时就能拿到服务端公开配置。

第二类是配置 tRPC。`src/server/routers/lambda/config/index.ts` 中：

- `getDefaultAgentConfig` 调用 `getServerDefaultAgentConfig()`。
- `getGlobalConfig` 并发读取 `getServerGlobalConfig()`、feature flags 和 billboard，返回 `GlobalRuntimeConfig`。

第三类是 AI Provider 相关路由。`src/server/routers/lambda/aiProvider.ts` 和 `aiModel.ts` 会调用 `getServerGlobalConfig()`，取出 `aiProvider`，再注入到 provider repo 或返回给调用方。这里的 `aiProvider` 是服务端根据 env 和 model-bank 生成的 provider 基线配置。

第四类是 Agent、AgentGroup、KnowledgeBase、Chunk、File、UserMemories 等服务。它们主要消费：

- `getServerDefaultAgentConfig()`：创建或更新 agent 时合并服务端默认 Agent 配置。
- `getServerDefaultFilesConfig()`：决定默认 embedding/reranker/queryMode。

例如知识库和文件处理会读取默认 embedding model，如果没有配置则回退到代码中的默认模型。

第五类是 memory/userMemory 相关服务、workflow 和 webhook。它们直接调用 `parseMemoryExtractionConfig()`，因为这些服务端流程需要私有信息，例如 API Key、Webhook Headers、S3 凭据、Upstash Workflow Extra Headers。典型调用包括：

- `src/server/services/memory/userMemory/embedding.ts`
- `src/server/services/memory/userMemory/extract.ts`
- `src/server/services/memory/userMemory/persona/service.ts`
- `src/server/routers/lambda/userMemory.ts`
- `src/app/(backend)/api/webhooks/memory-extraction/*`
- `src/server/workflows-hono/memory-user-memory/*`

认证页还有单独的下游：`src/app/[variants]/(auth)/_layout/AuthGlobalProvider.tsx` 调用 `getServerAuthConfig()`，只拿认证相关的轻量配置。

## 运行/调用流程

完整 SPA 启动时的大致流程是：

1. 浏览器请求 SPA HTML。
2. `src/app/spa/[variants]/[[...path]]/route.ts` 的 `GET` 被执行。
3. 服务端调用 `getServerGlobalConfig()`。
4. `getServerGlobalConfig()` 读取 `getAppConfig()`、各种 `env` 对象和业务常量。
5. 它调用 `genServerAiProvidersConfig()` 生成 `aiProvider`。
6. `genServerAiProvidersConfig()` 遍历 `ModelProvider`，结合 `model-bank`、`loadModels()`、`getLLMConfig()` 和 `${PROVIDER}_MODEL_LIST` 等环境变量，生成每个 provider 的启用状态、启用模型和服务端模型列表。
7. `getServerGlobalConfig()` 继续解析默认 Agent、系统 Agent、公开 memory 配置、SSO Provider、图像/视觉/上传/telemetry 等配置。
8. 最终返回 `GlobalServerConfig`。
9. SPA route 把它放入 `SPAServerConfig.config`，随 HTML 初始化数据交给前端。

通过 tRPC 拉取全局配置时，大致流程是：

1. 前端调用 lambda config router 的 `getGlobalConfig`。
2. `src/server/routers/lambda/config/index.ts` 并发调用：
   - `getServerGlobalConfig()`
   - `getServerFeatureFlagsStateFromRuntimeConfig()`
   - `getActiveBillboard()`
3. 返回 `{ serverConfig, serverFeatureFlags, billboard }`。

获取默认 Agent 配置时流程更短：

1. 调用 `getServerDefaultAgentConfig()`。
2. 内部读取 `getAppConfig().DEFAULT_AGENT_CONFIG`。
3. 使用 `parseAgentConfig` 解析字符串。
4. 如果解析结果为空，则返回 `{}`。

获取默认文件配置时：

1. 调用 `getServerDefaultFilesConfig()`。
2. 内部读取 `knowledgeEnv.DEFAULT_FILES_CONFIG`。
3. 使用 `parseFilesConfig` 解析。
4. 如果没有配置，则回退到 `DEFAULT_FILES_CONFIG`。

memory 抽取服务的流程与前端公开配置不同：

1. 服务端 memory 流程调用 `parseMemoryExtractionConfig()`。
2. 解析 gatekeeper、layer extractor、persona writer、embedding 等私有 agent 配置。
3. 解析 webhook、workflow headers、S3 observability、feature flags、白名单、并发数。
4. 服务端用这些配置创建 runtime、调用 embedding、执行抽取、触发 webhook 或 workflow。
5. 如果是 `getServerGlobalConfig()` 中的 memory 配置，则只调用 `getPublicMemoryExtractionConfig()`，不会暴露 API Key。

## 小白阅读顺序

建议先读 `index.ts`。它是这个目录的总装配点，能最快理解“哪些配置会进入全局配置”。重点看 `getServerGlobalConfig` 的返回对象，不需要一开始就钻进每个 env 的来源。

第二步读 `genServerAiProviderConfig.ts`。这个文件解释了 `aiProvider` 是怎么来的。理解它以后，就能明白为什么前端能知道每个 provider 是否启用、有哪些服务端模型、哪些模型被环境变量启用。

第三步读 `parseDefaultAgent.ts`。它很短，但能帮助你理解 `DEFAULT_AGENT_CONFIG` 这种字符串配置如何变成嵌套对象。注意它支持数字、布尔、数组和嵌套路径。

第四步读 `parseFilesConfig.ts`。它对应知识库/文件默认模型配置，格式更严格，主要是 `embedding_model=provider/model`、`reranker_model=provider/model`、`query_mode=...`。

第五步读 `parseSystemAgent.ts`。它对应系统内置 Agent 的 provider/model 配置，尤其要理解 `default=provider/model` 会批量填充未配置项。

第六步读 `parseMemoryExtractionConfig.ts`。这是最复杂的文件，建议分两遍看：第一遍只看导出的 `parseMemoryExtractionConfig` 和 `getPublicMemoryExtractionConfig`；第二遍再看每个 `parseXxxAgent` 辅助函数。核心关注点是“私有配置”和“公开配置”的边界。

最后再看调用方：

- `src/app/spa/[variants]/[[...path]]/route.ts`：看 SPA 初始化如何注入全局配置。
- `src/server/routers/lambda/config/index.ts`：看 tRPC 如何返回全局运行配置。
- `src/server/routers/lambda/aiProvider.ts`：看 AI Provider 配置如何进入服务端 provider 仓储。
- `src/server/services/memory/userMemory/extract.ts` 或 `embedding.ts`：看 memory 私有配置如何被实际服务使用。

## 常见误区

不要把 `getServerGlobalConfig()` 理解成“只给前端用”。它确实会在 SPA 初始化和 config router 中下发公开配置，但服务端路由也会调用它，例如 AI Provider 相关路由会读取其中的 `aiProvider`。

不要把 `parseMemoryExtractionConfig()` 的返回值直接下发给前端。它是私有配置，可能包含 `apiKey`、Webhook Headers、S3 凭据等敏感信息。下发给全局配置的是 `getPublicMemoryExtractionConfig()`，它会通过 `sanitizeAgent` 删除 `apiKey`。

不要以为所有配置都来自同一种 env 入口。这个目录混合使用了 `getAppConfig()`、`appEnv`、`authEnv`、`knowledgeEnv`、`toolsEnv`、`imageEnv`、`fileEnv`、`langfuseEnv`、`process.env` 和 `getLLMConfig()`。其中 memory 抽取配置大量直接读取 `process.env.MEMORY_USER_MEMORY_*`。

不要忽略 provider 的特殊配置。`genServerAiProvidersConfig` 默认按 `${PROVIDER}_MODEL_LIST` 和 `ENABLED_${PROVIDER}` 读取，但 `index.ts` 对很多 provider 做了覆盖，例如 Azure、Bedrock、Tencent Cloud、Ollama、LobeHub 等。

不要以为 `parseFilesConfig` 会接受任意 key。它只处理 `embedding_model`、`reranker_model`、`query_mode`，其它 key 即使出现在字符串里也不会进入最终配置；格式错误时还会抛异常。

不要以为 `parseSystemAgent` 的 `default` 是一个普通系统 Agent。它只是批量默认值，不会作为 key 写入最终配置，而是用于填充 `DEFAULT_SYSTEM_AGENT_CONFIG` 中尚未配置的条目。

不要忽略中英文标点兼容。`parseFilesConfig` 和 `parseSystemAgent` 都会把中文逗号 `，` 替换成英文逗号 `,`；`parseAgentConfig` 的数组解析也兼容中文逗号。这对中文部署文档里的环境变量示例很重要。

不要把 `getServerAuthConfig()` 和 `getServerGlobalConfig()` 混为一谈。前者是 auth 页面用的轻量配置，`aiProvider` 为空，也不会解析完整 provider/model/memory 配置；后者才是完整全局配置。
