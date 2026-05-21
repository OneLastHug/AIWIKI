# 文件：src/server/globalConfig/index.ts

## 文件职责
这个文件位于 `src/server/globalConfig`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ENABLE_BUSINESS_FEATURES } from '@lobechat/business-const';
import { klavisEnv } from '@/config/klavis';
import { isDesktop } from '@/const/version';
import { appEnv, getAppConfig } from '@/envs/app';
import { authEnv } from '@/envs/auth';
import { fileEnv } from '@/envs/file';
import { imageEnv } from '@/envs/image';
import { knowledgeEnv } from '@/envs/knowledge';
import { langfuseEnv } from '@/envs/langfuse';
import { toolsEnv } from '@/envs/tools';
import { parseSSOProviders } from '@/libs/better-auth/utils/server';
import { parseSystemAgent } from '@/server/globalConfig/parseSystemAgent';
import { type GlobalServerConfig } from '@/types/serverConfig';
import { cleanObject } from '@/utils/object';
import { genServerAiProvidersConfig } from './genServerAiProviderConfig';
import { parseAgentConfig } from './parseDefaultAgent';
import { parseFilesConfig } from './parseFilesConfig';
import { getPublicMemoryExtractionConfig } from './parseMemoryExtractionConfig';
export const getServerGlobalConfig = async () => {
export const getServerDefaultAgentConfig = () => {
export const getServerDefaultFilesConfig = () => {
```

## 主要对外内容
```text
const getBetterAuthSSOProviders = () => {
export const getServerGlobalConfig = async () => {
export const getServerDefaultAgentConfig = () => {
export const getServerDefaultFilesConfig = () => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { ENABLE_BUSINESS_FEATURES } from '@lobechat/business-const';

import { klavisEnv } from '@/config/klavis';
import { isDesktop } from '@/const/version';
import { appEnv, getAppConfig } from '@/envs/app';
import { authEnv } from '@/envs/auth';
import { fileEnv } from '@/envs/file';
import { imageEnv } from '@/envs/image';
import { knowledgeEnv } from '@/envs/knowledge';
import { langfuseEnv } from '@/envs/langfuse';
import { toolsEnv } from '@/envs/tools';
import { parseSSOProviders } from '@/libs/better-auth/utils/server';
import { parseSystemAgent } from '@/server/globalConfig/parseSystemAgent';
import { type GlobalServerConfig } from '@/types/serverConfig';
import { cleanObject } from '@/utils/object';

import { genServerAiProvidersConfig } from './genServerAiProviderConfig';
import { parseAgentConfig } from './parseDefaultAgent';
import { parseFilesConfig } from './parseFilesConfig';
import { getPublicMemoryExtractionConfig } from './parseMemoryExtractionConfig';

/**
 * Get Better-Auth SSO providers list
 * Parses AUTH_SSO_PROVIDERS and returns enabled providers
 */
const getBetterAuthSSOProviders = () => {
  return parseSSOProviders(authEnv.AUTH_SSO_PROVIDERS);
};

export const getServerGlobalConfig = async () => {
  const { DEFAULT_AGENT_CONFIG } = getAppConfig();

  const config: GlobalServerConfig = {
    aiProvider: await genServerAiProvidersConfig({
      ...(ENABLE_BUSINESS_FEATURES
        ? {
            lobehub: {
              enabled: true,
            },
          }
        : {}),
      azure: {
        enabledKey: 'ENABLED_AZURE_OPENAI',
        withDeploymentName: true,
      },
      azureai: {
        withDeploymentName: true,
      },
      bedrock: {
        enabledKey: 'ENABLED_AWS_BEDROCK',
        modelListKey: 'AWS_BEDROCK_MODEL_LIST',
      },
      deepseek: {
        enabled: true,
      },
      giteeai: {
        enabledKey: 'ENABLED_GITEE_AI',
        modelListKey: 'GITEE_AI_MODEL_LIST',
      },
      kimicodingplan: {
        withDeploymentName: true,
      },
      lmstudio: {
        fetchOnClient: isDesktop ? false : undefined,
      },
      ollama: {
        enabled: isDesktop ? true : undefined,
        fetchOnClient: isDesktop ? false : !process.env.OLLAMA_PROXY_URL,
      },
      ollamacloud: {
        enabledKey: 'ENABLED_OLLAMA_CLOUD',
      },
      qwen: {
        withDeploymentName: true,
      },
      spark: {
        withDeploymentName: true,
      },
      tencentcloud: {
        enabledKey: 'ENABLED_TENCENT_CLOUD',
        modelListKey: 'TENCENT_CLOUD_MODEL_LIST',
      },
      volcengine: {
        withDeploymentName: true,
      },
      volcenginecodingplan: {
        withDeploymentName: true,
      },
    }),
    defaultAgent: {
      config: parseAgentConfig(DEFAULT_AGENT_CONFIG),
    },
    disableEmailPassword: authEnv.AUTH_DISABLE_EMAIL_PASSWORD,
    enableBusinessFeatures: ENABLE_BUSINESS_FEATURES,
    enableEmailVerification: authEnv.AUTH_EMAIL_VERIFICATION,
    enableKlavis: !!klavisEnv.KLAVIS_API_KEY,
    enableLobehubSkill: !!(appEnv.MARKET_TRUSTED_CLIENT_SECRET && appEnv.MARKET_TRUSTED_CLIENT_ID),
    enableMagicLink: authEnv.AUTH_ENABLE_MAGIC_LINK,
    enableMarketTrustedClient: !!(
      appEnv.MARKET_TRUSTED_CLIENT_SECRET && appEnv.MARKET_TRUSTED_CLIENT_ID
    ),
    enableUploadFileToServer: !!fileEnv.S3_SECRET_ACCESS_KEY,
    enableVisualUnderstanding: !!(
      toolsEnv.VISUAL_UNDERSTANDING_PROVIDER && toolsEnv.VISUAL_UNDERSTANDING_MODEL
    ),
    ...(toolsEnv.VISUAL_UNDERSTANDING_PROVIDER && toolsEnv.VISUAL_UNDERSTANDING_MODEL
      ? {
          visualUnderstanding: {
            model: toolsEnv.VISUAL_UNDERSTANDING_MODEL,
            provider: toolsEnv.VISUAL_UNDERSTANDING_PROVIDER,
          },
        }
      : undefined),

    // Expose Agent Gateway URL to client (used by hetero agents; also required for queue mode)
    ...(appEnv.AGENT_GATEWAY_URL ? { agentGatewayUrl: appEnv.AGENT_GATEWAY_URL } : undefined),

    image: cleanObject({
      defaultImageNum: imageEnv.AI_IMAGE_DEFAULT_IMAGE_NUM,
    }),
    memory: {
      userMemory: cleanObject(getPublicMemoryExtractionConfig()),
    },
    oAuthSSOProviders: getBetterAuthSSOProviders(),
    systemAgent: parseSystemAgent(appEnv.SYSTEM_AGENT),
    telemetry: {
      langfuse: langfuseEnv.ENABLE_LANGFUSE,
    },
  };

  return config;
};

export const getServerDefaultAgentConfig = () => {
  const { DEFAULT_AGENT_CONFIG } = getAppConfig();

  return parseAgentConfig(DEFAULT_AGENT_CONFIG) || {};
};

export const getServerDefaultFilesConfig = () => {
  return parseFilesConfig(knowledgeEnv.DEFAULT_FILES_CONFIG);
};

```
