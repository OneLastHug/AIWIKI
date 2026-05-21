# 文件：src/server/globalConfig/index.ts

## 它负责什么

`src/server/globalConfig/index.ts` 是服务端“全局运行配置”的聚合入口。它不直接实现某一个业务能力，而是把多个来源的配置汇总成一个统一的 `GlobalServerConfig`，供 SPA 初始化、TRPC 配置接口、模型/provider 接口、用户记忆等服务读取。

可以把它理解成服务端配置的“总装配层”：

- 从环境变量模块读取运行时开关，例如 `authEnv`、`appEnv`、`fileEnv`、`imageEnv`、`toolsEnv`、`knowledgeEnv`、`langfuseEnv`、`klavisEnv`。
- 解析 AI provider 配置，生成每个模型服务商的可用状态、模型列表、启用模型。
- 解析默认 agent 配置、默认文件/知识库配置、系统 agent 配置、用户记忆公开配置。
- 控制哪些功能开关暴露给客户端，例如邮箱登录、Magic Link、Klavis、上传文件、视觉理解、商业特性等。
- 对敏感配置做边界控制，例如 `memory.userMemory` 只暴露公开字段，不直接暴露 API key。

这个文件导出三个函数：

- `getServerGlobalConfig`
  - 异步函数，返回完整的服务端全局配置。
  - 这是最核心的导出。
- `getServerDefaultAgentConfig`
  - 同步函数，只返回服务端默认 agent 配置。
  - 主要给创建 agent、agent group 等服务复用。
- `getServerDefaultFilesConfig`
  - 同步函数，只返回默认文件/知识库配置。
  - 主要给知识库、文件、用户记忆相关服务复用 embedding 配置。

## 关键组成

### 1. import 依赖

这个文件的 import 可以分成几类。

第一类是业务常量和环境判断：

- `ENABLE_BUSINESS_FEATURES` 来自 `@lobechat/business-const`，用于判断是否启用商业相关能力。
- `isDesktop` 来自 `@/const/version`，用于区分桌面端和非桌面端行为。

第二类是环境变量配置模块：

- `appEnv`
- `authEnv`
- `fileEnv`
- `imageEnv`
- `knowledgeEnv`
- `langfuseEnv`
- `toolsEnv`
- `klavisEnv`

这些模块已经把原始环境变量整理成结构化配置。`index.ts` 不直接大量读取 `process.env`，而是优先通过这些 env 模块拿值。不过 AI provider 的部分底层解析仍会在 `genServerAiProviderConfig.ts` 中读取 provider 对应的模型列表环境变量。

第三类是解析器：

- `parseSSOProviders`
- `parseSystemAgent`
- `parseAgentConfig`
- `parseFilesConfig`
- `getPublicMemoryExtractionConfig`
- `genServerAiProvidersConfig`

这些函数负责把字符串型环境变量转换成应用内部可消费的结构。

第四类是类型和工具：

- `GlobalServerConfig`
- `cleanObject`

`GlobalServerConfig` 约束最终返回结构。`cleanObject` 用于清理对象中的空值，避免把无意义字段下发给客户端或后续消费者。

### 2. `getBetterAuthSSOProviders`

```ts
const getBetterAuthSSOProviders = () => {
  return parseSSOProviders(authEnv.AUTH_SSO_PROVIDERS);
};
```

这是一个很小的本地辅助函数，作用是把 `AUTH_SSO_PROVIDERS` 解析成可用的 SSO provider 列表。

它被用于：

- `getServerGlobalConfig`
- 同目录的 `getServerAuthConfig.ts` 中也有同样逻辑

这里体现了一个模式：认证相关配置也属于 server config 的一部分，但某些场景只需要 auth 配置，因此同目录下单独存在 `getServerAuthConfig.ts`。

### 3. `getServerGlobalConfig`

这是核心函数：

```ts
export const getServerGlobalConfig = async () => {
  const { DEFAULT_AGENT_CONFIG } = getAppConfig();

  const config: GlobalServerConfig = {
    ...
  };

  return config;
};
```

它首先通过 `getAppConfig()` 读取 `DEFAULT_AGENT_CONFIG`，然后组装 `GlobalServerConfig`。

#### `aiProvider`

```ts
aiProvider: await genServerAiProvidersConfig({...})
```

这是配置中最重的一块，因为它需要异步加载模型列表。

`genServerAiProvidersConfig` 的核心逻辑在同目录的 `genServerAiProviderConfig.ts`：

- 调用 `getLLMConfig()` 获取 LLM 相关开关。
- 调用 `loadModels()` 加载内置模型列表。
- 从 `model-bank` 的 `ModelProvider` 遍历全部 provider。
- 对每个 provider 生成：
  - `enabled`
  - `enabledModels`
  - `serverModelLists`
  - 可选的 `fetchOnClient`

`index.ts` 传给它的是每个 provider 的特殊规则。例如：

- `azure`
  - `enabledKey: 'ENABLED_AZURE_OPENAI'`
  - `withDeploymentName: true`
- `bedrock`
  - `enabledKey: 'ENABLED_AWS_BEDROCK'`
  - `modelListKey: 'AWS_BEDROCK_MODEL_LIST'`
- `ollama`
  - 桌面端默认启用
  - 非桌面端根据 `OLLAMA_PROXY_URL` 决定是否让客户端 fetch
- `lmstudio`
  - 桌面端不在客户端 fetch
- `deepseek`
  - 强制 `enabled: true`
- `lobehub`
  - 只有 `ENABLE_BUSINESS_FEATURES` 为真时才启用

这说明 `index.ts` 不是简单透传环境变量，而是在这里编码了 LobeHub 对不同 provider 的产品策略。

#### `defaultAgent`

```ts
defaultAgent: {
  config: parseAgentConfig(DEFAULT_AGENT_CONFIG),
}
```

`DEFAULT_AGENT_CONFIG` 是字符串型配置，交给 `parseAgentConfig` 转成对象。

`parseAgentConfig` 支持：

- `key=value`
- 嵌套 key，例如通过 `set(config, key, value)` 支持类似 `params.temperature=0.7`
- 数字
- 布尔值
- 英文逗号和中文逗号数组
- 双引号包裹的字符串
- `plugins` 特殊处理为数组

因此默认 agent 配置可以比较紧凑地写在环境变量中。

#### auth 和登录相关开关

包括：

- `disableEmailPassword`
- `enableEmailVerification`
- `enableMagicLink`
- `oAuthSSOProviders`

这些都来自 `authEnv` 和 `parseSSOProviders`。

它们会影响登录页、认证 UI、认证流程是否展示或启用相应能力。

#### 商业和市场相关开关

包括：

- `enableBusinessFeatures`
- `enableLobehubSkill`
- `enableMarketTrustedClient`

其中：

```ts
enableLobehubSkill: !!(appEnv.MARKET_TRUSTED_CLIENT_SECRET && appEnv.MARKET_TRUSTED_CLIENT_ID)
```

和：

```ts
enableMarketTrustedClient: !!(
  appEnv.MARKET_TRUSTED_CLIENT_SECRET && appEnv.MARKET_TRUSTED_CLIENT_ID
)
```

判断条件相同，都是要求 `MARKET_TRUSTED_CLIENT_SECRET` 和 `MARKET_TRUSTED_CLIENT_ID` 同时存在。

根据当前片段推断，`enableLobehubSkill` 更偏具体功能开关，`enableMarketTrustedClient` 更偏客户端信任/市场访问能力开关。依据是二者命名不同，但都来自同一组市场 trusted client 凭据。

#### 文件上传能力

```ts
enableUploadFileToServer: !!fileEnv.S3_SECRET_ACCESS_KEY
```

这里只检查 `S3_SECRET_ACCESS_KEY` 是否存在。也就是说这个开关不是完整校验 S3 配置是否全部有效，而是用 secret key 作为启用信号。

常见阅读点是：它只是 feature flag，不等于文件服务一定能完整工作。真正上传时还会依赖其他 S3 配置。

#### 视觉理解能力

```ts
enableVisualUnderstanding: !!(
  toolsEnv.VISUAL_UNDERSTANDING_PROVIDER && toolsEnv.VISUAL_UNDERSTANDING_MODEL
)
```

如果 provider 和 model 都存在，还会额外下发：

```ts
visualUnderstanding: {
  model: toolsEnv.VISUAL_UNDERSTANDING_MODEL,
  provider: toolsEnv.VISUAL_UNDERSTANDING_PROVIDER,
}
```

这里使用条件展开，只有配置完整时才出现 `visualUnderstanding` 字段。

#### Agent Gateway

```ts
...(appEnv.AGENT_GATEWAY_URL ? { agentGatewayUrl: appEnv.AGENT_GATEWAY_URL } : undefined)
```

注释说明：

```ts
// Expose Agent Gateway URL to client (used by hetero agents; also required for queue mode)
```

这表示 `AGENT_GATEWAY_URL` 会暴露给客户端，用于 heterogeneous agents，也就是外部/异构 agent 场景；queue mode 也依赖它。

#### image 配置

```ts
image: cleanObject({
  defaultImageNum: imageEnv.AI_IMAGE_DEFAULT_IMAGE_NUM,
})
```

这里把默认图片数量配置下发到 `image.defaultImageNum`，并用 `cleanObject` 清理空值。

#### memory 配置

```ts
memory: {
  userMemory: cleanObject(getPublicMemoryExtractionConfig()),
}
```

`getPublicMemoryExtractionConfig` 来自 `parseMemoryExtractionConfig.ts`。它内部会读取大量 `MEMORY_USER_MEMORY_*` 环境变量，但对外只返回公开配置。

从同目录文件可以看到，它会通过 `sanitizeAgent` 删除 agent 配置里的 `apiKey`：

```ts
delete sanitized.apiKey;
```

最终公开的 memory 配置包括：

- `agentGateKeeper`
- `agentLayerExtractor`
- `embedding`
- `concurrency`

其中 `agentLayerExtractor` 还会带上不同记忆层的模型配置，例如：

- `activity`
- `context`
- `experience`
- `identity`
- `preference`

因此 `index.ts` 暴露的是“客户端或上层服务可知道的记忆抽取配置”，不是完整私密执行配置。

#### systemAgent

```ts
systemAgent: parseSystemAgent(appEnv.SYSTEM_AGENT)
```

`parseSystemAgent` 解析 `SYSTEM_AGENT` 字符串。

同目录实现显示，它支持类似：

```txt
default=provider/model
```

也支持针对具体系统 agent key 配置：

```txt
promptRewrite=provider/model
```

它会：

- 只接受 `DEFAULT_SYSTEM_AGENT_CONFIG` 中存在的 key。
- 支持中文逗号。
- 对 `promptRewrite`、`autoSuggestion` 这类默认开启项设置 `enabled: true`。
- 如果配置了 `default`，会把默认 provider/model 应用到未单独配置的系统 agent。

#### telemetry

```ts
telemetry: {
  langfuse: langfuseEnv.ENABLE_LANGFUSE,
}
```

这里只暴露 Langfuse 是否启用，不暴露 Langfuse 密钥等敏感信息。

### 4. `getServerDefaultAgentConfig`

```ts
export const getServerDefaultAgentConfig = () => {
  const { DEFAULT_AGENT_CONFIG } = getAppConfig();

  return parseAgentConfig(DEFAULT_AGENT_CONFIG) || {};
};
```

这个函数只关心默认 agent 配置，不返回完整 server config。

调用方包括：

- `src/server/services/agent/index.ts`
- `src/server/services/agentGroup/index.ts`
- `src/server/routers/lambda/config/index.ts`

用途通常是创建 agent 或 agent group 时，把服务端默认配置合并进去。

这里返回 `parseAgentConfig(DEFAULT_AGENT_CONFIG) || {}`，说明解析失败或无内容时，上层仍然拿到一个对象，避免空值破坏后续合并逻辑。

### 5. `getServerDefaultFilesConfig`

```ts
export const getServerDefaultFilesConfig = () => {
  return parseFilesConfig(knowledgeEnv.DEFAULT_FILES_CONFIG);
};
```

这个函数只关心默认文件/知识库配置。

`parseFilesConfig` 支持的 key 包括：

- `embedding_model`
- `reranker_model`
- `query_mode`

其中模型格式要求是：

```txt
provider/model
```

例如根据实现逻辑，`embedding_model=openai/text-embedding-3-small` 会被解析成：

```ts
{
  embeddingModel: {
    provider: 'openai',
    model: 'text-embedding-3-small'
  }
}
```

调用方包括：

- `src/server/services/knowledgeBase/index.ts`
- `src/server/services/toolExecution/serverRuntimes/memory.ts`
- `src/server/routers/async/file.ts`
- `src/server/routers/lambda/chunk.ts`
- `src/server/routers/lambda/userMemories.ts`

这说明它主要服务于知识库、文件切块、embedding、用户记忆等需要默认 embedding/reranker 配置的后端流程。

## 上下游关系

### 上游：配置来源

`index.ts` 的上游主要是环境变量和常量配置。

直接上游包括：

- `@lobechat/business-const`
  - `ENABLE_BUSINESS_FEATURES`
- `@/envs/app`
  - `appEnv`
  - `getAppConfig`
- `@/envs/auth`
  - `authEnv`
- `@/envs/file`
  - `fileEnv`
- `@/envs/image`
  - `imageEnv`
- `@/envs/knowledge`
  - `knowledgeEnv`
- `@/envs/langfuse`
  - `langfuseEnv`
- `@/envs/tools`
  - `toolsEnv`
- `@/config/klavis`
  - `klavisEnv`
- `process.env`
  - 主要在 `genServerAiProviderConfig.ts`、`parseMemoryExtractionConfig.ts` 等解析器内部继续读取

它不是配置的源头，而是配置的聚合层。

### 中游：解析器和清洗器

同目录解析器承担格式转换：

- `genServerAiProvidersConfig`
  - 把 provider 特殊规则、LLM env、模型列表合成 `aiProvider` 配置。
- `parseAgentConfig`
  - 把 `DEFAULT_AGENT_CONFIG` 字符串转成 agent config 对象。
- `parseFilesConfig`
  - 把 `DEFAULT_FILES_CONFIG` 字符串转成 embedding/reranker/query mode 配置。
- `parseSystemAgent`
  - 把 `SYSTEM_AGENT` 字符串转成系统 agent 配置。
- `getPublicMemoryExtractionConfig`
  - 从 memory 私有配置中提取可公开部分，并脱敏。
- `parseSSOProviders`
  - 把 SSO provider 字符串转成结构化列表。
- `cleanObject`
  - 清理空字段。

### 下游：谁消费它

根据调用方检索，`getServerGlobalConfig` 主要被这些模块消费：

- `src/app/spa/[variants]/[[...path]]/route.ts`
  - 用于 SPA HTML/初始化阶段，把 server config 注入前端启动上下文。
- `src/server/routers/lambda/config/index.ts`
  - 配置相关 TRPC/lambda router，向客户端提供 server config。
- `src/server/routers/lambda/aiProvider.ts`
  - 读取 `aiProvider` 配置。
- `src/server/routers/lambda/aiModel.ts`
  - 读取 `aiProvider` 配置，用于模型相关接口。
- `src/server/services/memory/userMemory/extract.ts`
  - 用户记忆抽取流程读取全局配置。

`getServerDefaultAgentConfig` 的下游包括：

- `src/server/services/agent/index.ts`
- `src/server/services/agentGroup/index.ts`
- `src/server/routers/lambda/config/index.ts`

`getServerDefaultFilesConfig` 的下游包括：

- `src/server/services/knowledgeBase/index.ts`
- `src/server/services/toolExecution/serverRuntimes/memory.ts`
- `src/server/routers/async/file.ts`
- `src/server/routers/lambda/chunk.ts`
- `src/server/routers/lambda/userMemories.ts`

前端状态侧也有相关类型和 store：

- `src/store/serverConfig/store.ts`
- `src/store/serverConfig/Provider.tsx`
- `src/store/user/slices/common/action.ts`
- `src/types/spaServerConfig.ts`

根据当前片段推断，完整流程是服务端生成 `GlobalServerConfig`，再通过 SPA 初始化或配置接口进入前端 store，前端根据这些开关控制 UI 展示和能力可用性。依据是 `route.ts`、`Provider.tsx`、`store.ts`、`spaServerConfig.ts` 都引用了 `GlobalServerConfig` 或 server config。

## 运行/调用流程

### SPA 初始化流程

1. 用户访问 SPA 页面。
2. `src/app/spa/[variants]/[[...path]]/route.ts` 处理请求。
3. route 内部调用 `getServerGlobalConfig()`。
4. `getServerGlobalConfig()` 开始组装配置：
   - 读取 `DEFAULT_AGENT_CONFIG`
   - 调用 `genServerAiProvidersConfig()` 生成 `aiProvider`
   - 解析 auth、market、file、tools、image、memory、systemAgent、telemetry 等配置
5. 生成 `GlobalServerConfig`。
6. server config 被注入 SPA 运行环境。
7. 前端的 server config store/provider 读取这些配置。
8. 前端 UI 和客户端逻辑根据配置决定：
   - 哪些 provider 可用
   - 是否展示邮箱登录/Magic Link/SSO
   - 是否启用文件上传
   - 是否启用视觉理解
   - 是否启用 Klavis
   - 是否显示商业功能
   - 默认 agent 配置是什么

### AI provider 配置流程

1. `getServerGlobalConfig()` 调用 `genServerAiProvidersConfig()`。
2. `genServerAiProvidersConfig()` 遍历 `ModelProvider` 中的所有 provider。
3. 每个 provider 查找：
   - 内置模型列表
   - 静态模型列表
   - 环境变量中的模型列表覆盖
   - provider 特殊配置
4. 调用：
   - `extractEnabledModels`
   - `transformToAiModelList`
5. 返回按 provider 分组的配置对象。
6. `getServerGlobalConfig()` 把它挂到 `config.aiProvider`。
7. 下游 `aiProvider` / `aiModel` router 和前端配置消费它。

### 默认 agent 配置流程

1. `getServerDefaultAgentConfig()` 或 `getServerGlobalConfig()` 读取 `DEFAULT_AGENT_CONFIG`。
2. 调用 `parseAgentConfig()`。
3. 字符串配置被解析为对象。
4. agent service、agent group service 或 config router 使用它。

例如配置中有：

```txt
model=gpt-4o,temperature=0.7,plugins=search
```

根据 `parseAgentConfig` 的逻辑，会被转成类似：

```ts
{
  model: 'gpt-4o',
  temperature: 0.7,
  plugins: ['search']
}
```

### 默认文件配置流程

1. `getServerDefaultFilesConfig()` 读取 `knowledgeEnv.DEFAULT_FILES_CONFIG`。
2. 调用 `parseFilesConfig()`。
3. 解析 `embedding_model`、`reranker_model`、`query_mode`。
4. 知识库、文件切块、用户记忆等服务读取默认 embedding/reranker 配置。
5. 如果没有配置，则返回 `DEFAULT_FILES_CONFIG` 常量。

### memory 公开配置流程

1. `getServerGlobalConfig()` 调用 `getPublicMemoryExtractionConfig()`。
2. `getPublicMemoryExtractionConfig()` 内部先调用 `parseMemoryExtractionConfig()`。
3. `parseMemoryExtractionConfig()` 读取 memory 相关私有环境变量。
4. 生成完整私有配置，包括 API key、baseURL、model、provider、webhook、S3 observability 等。
5. `getPublicMemoryExtractionConfig()` 对 agent 配置执行 `sanitizeAgent()`。
6. `sanitizeAgent()` 删除 `apiKey`。
7. 返回公开 memory 配置。
8. `index.ts` 再通过 `cleanObject` 清理后挂到 `memory.userMemory`。

这个流程的关键点是：私有配置可以在服务端执行链路中存在，但通过 `getServerGlobalConfig()` 暴露出去的是公开子集。

## 小白阅读顺序

1. 先读 `src/server/globalConfig/index.ts`

   先不要钻进每个解析器。只看 `getServerGlobalConfig` 的返回对象有哪些字段，建立整体地图：

   - `aiProvider`
   - `defaultAgent`
   - auth 开关
   - market/business 开关
   - upload/visual/image/memory/systemAgent/telemetry

2. 再读 `src/server/globalConfig/genServerAiProviderConfig.ts`

   这是最复杂的部分。重点理解：

   - 它遍历所有 `ModelProvider`
   - 它如何决定 provider 是否 enabled
   - 它如何生成 `enabledModels`
   - 它如何生成 `serverModelLists`
   - `specificConfig` 如何覆盖默认规则

3. 然后读 `src/server/globalConfig/parseDefaultAgent.ts`

   这个文件短，但很重要。它解释了 `DEFAULT_AGENT_CONFIG` 这种字符串配置为什么能变成嵌套对象、数字、布尔值和数组。

4. 接着读 `src/server/globalConfig/parseFilesConfig.ts`

   重点看默认知识库/文件配置的格式：

   - `embedding_model=provider/model`
   - `reranker_model=provider/model`
   - `query_mode=xxx`

5. 再读 `src/server/globalConfig/parseSystemAgent.ts`

   重点看：

   - `default=provider/model`
   - 单独系统 agent 配置
   - `promptRewrite`、`autoSuggestion` 默认启用逻辑

6. 最后读 `src/server/globalConfig/parseMemoryExtractionConfig.ts`

   这个文件更长，建议只关注两条线：

   - 私有配置如何从 `MEMORY_USER_MEMORY_*` 环境变量生成
   - `getPublicMemoryExtractionConfig()` 如何删除 `apiKey` 后返回公开配置

7. 有余力再看调用方

   推荐看：

   - `src/app/spa/[variants]/[[...path]]/route.ts`
   - `src/server/routers/lambda/config/index.ts`
   - `src/server/routers/lambda/aiProvider.ts`
   - `src/server/services/agent/index.ts`
   - `src/server/services/knowledgeBase/index.ts`

   这样可以理解配置如何从服务端进入前端，以及如何被后端业务服务复用。

## 常见误区

### 误区 1：以为 `getServerGlobalConfig` 只是读取环境变量

它不是简单读取环境变量，而是会做多层转换：

- provider 特殊规则合并
- 模型列表解析
- 默认 agent 字符串解析
- 文件配置字符串解析
- SSO provider 解析
- system agent 配置解析
- memory 配置脱敏
- 空字段清理

所以修改它时要考虑下游结构，而不是只看某个 env 名称。

### 误区 2：以为所有配置都会暴露给客户端

不会。

例如 memory 配置内部可能包含 `apiKey`，但 `getPublicMemoryExtractionConfig()` 会通过 `sanitizeAgent()` 删除 `apiKey`。

`getServerGlobalConfig()` 的语义更接近“可给客户端或公共接口使用的 server config”，不是服务端所有私密配置的全集。

### 误区 3：以为 provider 的 enabled 都来自统一环境变量

大多数 provider 默认使用类似 `ENABLED_${PROVIDER}` 的环境变量，但 `index.ts` 会传入 provider 特殊规则。

例如：

- `azure` 使用 `ENABLED_AZURE_OPENAI`
- `bedrock` 使用 `ENABLED_AWS_BEDROCK`
- `deepseek` 直接 `enabled: true`
- `ollama` 在桌面端默认启用
- `lobehub` 受 `ENABLE_BUSINESS_FEATURES` 控制

所以判断某个 provider 是否启用时，要同时看 `index.ts` 的 `specificConfig` 和 `genServerAiProviderConfig.ts` 的默认逻辑。

### 误区 4：以为 `enableUploadFileToServer` 表示 S3 配置完整可用

当前逻辑只判断：

```ts
!!fileEnv.S3_SECRET_ACCESS_KEY
```

它是一个启用信号，不是完整健康检查。真正上传链路可能还需要 bucket、region、endpoint 等其他配置。

### 误区 5：以为 `visualUnderstanding` 字段总是存在

不是。

只有同时配置了：

- `toolsEnv.VISUAL_UNDERSTANDING_PROVIDER`
- `toolsEnv.VISUAL_UNDERSTANDING_MODEL`

才会出现：

```ts
visualUnderstanding: {
  provider,
  model,
}
```

否则只有 `enableVisualUnderstanding: false`，不会展开 `visualUnderstanding` 对象。

### 误区 6：忽略桌面端和 Web 端差异

`lmstudio` 和 `ollama` 的配置明显依赖 `isDesktop`。

例如 `ollama`：

- 桌面端 `enabled: true`
- 桌面端 `fetchOnClient: false`
- 非桌面端根据 `OLLAMA_PROXY_URL` 判断是否客户端 fetch

所以调试 provider 行为时，要确认当前运行环境是 desktop 还是 web/server。

### 误区 7：把 `getServerDefaultAgentConfig` 和 `getServerGlobalConfig().defaultAgent.config` 当成完全不同来源

它们来源相同，都是：

```ts
getAppConfig().DEFAULT_AGENT_CONFIG
```

并且都通过：

```ts
parseAgentConfig(DEFAULT_AGENT_CONFIG)
```

区别只是返回范围不同：

- `getServerGlobalConfig()` 返回完整 server config。
- `getServerDefaultAgentConfig()` 只返回默认 agent config，方便后端服务直接使用。

### 误区 8：以为 `parseFilesConfig` 接受任意 key

不接受。

它只处理受保护的 key：

- `embedding_model`
- `reranker_model`
- `query_mode`

其他 key 会被忽略或在格式错误时抛错。模型值还必须符合 `provider/model` 格式，否则会抛出格式错误。

### 误区 9：忽略 `cleanObject`

`image` 和 `memory.userMemory` 都使用了 `cleanObject`。这意味着最终返回对象可能不会保留值为空的字段。

调试前端拿不到某个字段时，不要只看对象字面量里有没有写，还要看该字段是否被 `cleanObject` 清理掉。

### 误区 10：以为同目录的 `getServerAuthConfig.ts` 和 `index.ts` 是重复代码

`getServerAuthConfig.ts` 返回的是一个精简版 `GlobalServerConfig`，主要包含认证相关字段：

- `disableEmailPassword`
- `enableEmailVerification`
- `enableMagicLink`
- `enableMarketTrustedClient`
- `oAuthSSOProviders`
- `enableBusinessFeatures`
- 空的 `aiProvider`
- 空的 `telemetry`

它适合只需要 auth 配置的场景。`index.ts` 则是完整全局配置入口。
