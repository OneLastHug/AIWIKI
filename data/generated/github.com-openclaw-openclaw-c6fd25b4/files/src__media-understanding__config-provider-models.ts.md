# 文件：src/media-understanding/config-provider-models.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { OpenClawConfig } from "../config/types.js";
import { normalizeMediaProviderId } from "./provider-id.js";

type ConfigProvider = NonNullable<
  NonNullable<NonNullable<OpenClawConfig["models"]>["providers"]>[string]
>;

type ConfigProviderModel = NonNullable<ConfigProvider["models"]>[number];

function hasImageCapableModel(providerCfg: ConfigProvider): boolean {
  const models = providerCfg.models ?? [];
  return models.some(
    (model: ConfigProviderModel) => Array.isArray(model?.input) && model.input.includes("image"),
  );
}

export function resolveImageCapableConfigProviderIds(cfg?: OpenClawConfig): string[] {
  const configProviders = cfg?.models?.providers;
  if (!configProviders || typeof configProviders !== "object") {
    return [];
  }

  const providerIds: string[] = [];
  for (const [providerKey, providerCfg] of Object.entries(configProviders)) {
    if (!providerKey?.trim() || !hasImageCapableModel(providerCfg)) {
      continue;
    }
    providerIds.push(normalizeMediaProviderId(providerKey));
  }
  return providerIds;
}

```
