# 文件：packages/desktop/src/renderer/hooks/agent/useModelProviderList.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { ipcBridge } from '@/common';
import { GOOGLE_AUTH_PROVIDER_ID } from '@/common/config/constants';
import type { IProvider } from '@/common/config/storage';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import useSWR, { type SWRConfiguration } from 'swr';
import { useGoogleAuthModels } from './useGoogleAuthModels';
import { hasSpecificModelCapability } from '@/renderer/utils/model/modelCapabilities';

export interface ModelProviderListResult {
  providers: IProvider[];
  getAvailableModels: (provider: IProvider) => string[];
  formatModelLabel: (provider: { platform?: string } | undefined, modelName?: string) => string;
}

export const PROVIDERS_SWR_KEY = 'providers';

// Provider config is local application state. Keep it stable after the initial
// load and refresh only through explicit mutate() calls after CRUD operations.
export const PROVIDERS_SWR_OPTIONS: SWRConfiguration<IProvider[], Error> = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  shouldRetryOnError: false,
};

export const fetchProviders = async (): Promise<IProvider[]> => {
  return (await ipcBridge.mode.listProviders.invoke()) ?? [];
};

export const useProvidersQuery = () => {
  return useSWR<IProvider[]>(PROVIDERS_SWR_KEY, fetchProviders, PROVIDERS_SWR_OPTIONS);
};

/**
 * Shared hook that builds the provider list (including Google Auth)
 * and exposes helpers consumed by both conversation and channel settings.
 */
export const useModelProviderList = (): ModelProviderListResult => {
  const { isGoogleAuth } = useGoogleAuthModels();

  const { data: modelConfig } = useProvidersQuery();

  // Mutable cache for available-model filtering
  const available_modelsCacheRef = useRef(new Map<string, string[]>());

  // 当 modelConfig 变化时清除缓存
  useEffect(() => {
    available_modelsCacheRef.current.clear();
  }, [modelConfig]);

  const getAvailableModels = useCallback((provider: IProvider): string[] => {
    // 包含 model_enabled 状态到缓存 key 中
    const model_enabledKey = provider.model_enabled ? JSON.stringify(provider.model_enabled) : 'all-enabled';
    const cacheKey = `${provider.id}-${(provider.models || []).join(',')}-${model_enabledKey}`;
    const cache = available_modelsCacheRef.current;
    if (cache.has(cacheKey)) {
      return cache.get(cacheKey)!;
    }
    const result: string[] = [];
    for (const modelName of provider.models || []) {
      // 检查模型是否被禁用（默认为启用）
      const isModelEnabled = provider.model_enabled?.[modelName] !== false;
      if (!isModelEnabled) continue;

      const functionCalling = hasSpecificModelCapability(provider, modelName, 'function_calling');
      const excluded = hasSpecificModelCapability(provider, modelName, 'excludeFromPrimary');
      if ((functionCalling === true || functionCalling === undefined) && excluded !== true) {
        result.push(modelName);
      }
    }
    cache.set(cacheKey, result);
    return result;
  }, []);

  const providers = useMemo(() => {
    let list: IProvider[] = Array.isArray(modelConfig) ? modelConfig : [];
    // 过滤掉被禁用的 provider（默认为启用）
    list = list.filter((p) => p.enabled !== false);

    if (isGoogleAuth) {
      const googleProvider: IProvider = {
        id: GOOGLE_AUTH_PROVIDER_ID,
        name: 'Gemini Google Auth',
        platform: 'gemini-with-google-auth',
        base_url: '',
        api_key: '',
        model: [],
        capabilities: [{ type: 'text' }, { type: 'vision' }, { type: 'function_calling' }],
        enabled: true, // Google Auth provider 始终启用
      } as unknown as IProvider;
      list = [googleProvider, ...list];
    }
    // 过滤掉没有可用模型的 provider
    return list.filter((p) => getAvailableModels(p).length > 0);
  }, [getAvailableModels, isGoogleAuth, modelConfig]);

  const formatModelLabel = useCallback((_provider: { platform?: string } | undefined, modelName?: string) => {
    if (!modelName) return '';
    return modelName;
  }, []);

  return { providers, getAvailableModels, formatModelLabel };
};

```
