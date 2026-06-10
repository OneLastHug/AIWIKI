# 文件：src/agents/models-config.providers.policy.lookup.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { MODEL_APIS } from "../config/types.models.js";
import { normalizeOptionalString } from "../shared/string-coerce.js";
import type { ProviderConfig } from "./models-config.providers.secrets.js";

const GENERIC_PROVIDER_APIS = new Set<string>([
  "openai-completions",
  "openai-responses",
  "anthropic-messages",
  "google-generative-ai",
]);

export function resolveProviderPluginLookupKey(
  providerKey: string,
  provider?: ProviderConfig,
): string {
  const api = normalizeOptionalString(provider?.api) ?? "";
  if (
    providerKey === "google-antigravity" ||
    providerKey === "google-vertex" ||
    api === "google-generative-ai"
  ) {
    return "google";
  }
  // Runtime plugin data can be looser than ProviderConfig; guard before .some().
  if (
    Array.isArray(provider?.models) &&
    provider.models.some((model) => normalizeOptionalString(model.api) === "google-generative-ai")
  ) {
    return "google";
  }
  if (
    api &&
    MODEL_APIS.includes(api as (typeof MODEL_APIS)[number]) &&
    !GENERIC_PROVIDER_APIS.has(api)
  ) {
    return api;
  }
  return providerKey;
}

```
