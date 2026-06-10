# 文件：src/agents/models-config.providers.policy.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import {
  applyProviderNativeStreamingUsagePolicy,
  normalizeProviderConfigPolicy,
  resolveProviderConfigApiKeyPolicy,
} from "./models-config.providers.policy.runtime.js";
import type { ProviderConfig } from "./models-config.providers.secrets.js";

export function applyNativeStreamingUsageCompat(
  providers: Record<string, ProviderConfig>,
): Record<string, ProviderConfig> {
  let changed = false;
  const nextProviders: Record<string, ProviderConfig> = {};

  for (const [providerKey, provider] of Object.entries(providers)) {
    const nextProvider = applyProviderNativeStreamingUsagePolicy(providerKey, provider);
    nextProviders[providerKey] = nextProvider;
    changed ||= nextProvider !== provider;
  }

  return changed ? nextProviders : providers;
}

export function normalizeProviderSpecificConfig(
  providerKey: string,
  provider: ProviderConfig,
): ProviderConfig {
  const normalized = normalizeProviderConfigPolicy(providerKey, provider);
  if (normalized && normalized !== provider) {
    return normalized;
  }
  return provider;
}

export function resolveProviderConfigApiKeyResolver(
  providerKey: string,
  provider?: ProviderConfig,
): ((env: NodeJS.ProcessEnv) => string | undefined) | undefined {
  return resolveProviderConfigApiKeyPolicy(providerKey, provider);
}

```
