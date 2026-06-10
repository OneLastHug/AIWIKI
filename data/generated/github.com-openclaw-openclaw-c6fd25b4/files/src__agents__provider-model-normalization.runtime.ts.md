# 文件：src/agents/provider-model-normalization.runtime.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { createRequire } from "node:module";

type ProviderRuntimeModule = Pick<
  typeof import("../plugins/provider-runtime.js"),
  "normalizeProviderModelIdWithPlugin"
>;

const require = createRequire(import.meta.url);
const PROVIDER_RUNTIME_CANDIDATES = [
  "../plugins/provider-runtime.js",
  "../plugins/provider-runtime.ts",
] as const;

let providerRuntimeModule: ProviderRuntimeModule | undefined;
let providerRuntimeLoadAttempted = false;

function loadProviderRuntime(): ProviderRuntimeModule | null {
  if (providerRuntimeModule) {
    return providerRuntimeModule;
  }
  if (providerRuntimeLoadAttempted) {
    return null;
  }
  providerRuntimeLoadAttempted = true;
  for (const candidate of PROVIDER_RUNTIME_CANDIDATES) {
    try {
      providerRuntimeModule = require(candidate) as ProviderRuntimeModule;
      return providerRuntimeModule;
    } catch {
      // Try source/runtime candidates in order.
    }
  }
  return null;
}

export function normalizeProviderModelIdWithRuntime(params: {
  provider: string;
  context: {
    provider: string;
    modelId: string;
  };
}): string | undefined {
  return loadProviderRuntime()?.normalizeProviderModelIdWithPlugin(params);
}

```
