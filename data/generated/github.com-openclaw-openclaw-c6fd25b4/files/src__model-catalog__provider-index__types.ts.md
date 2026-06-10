# 文件：src/model-catalog/provider-index/types.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { ModelCatalogProvider } from "../types.js";

export type OpenClawProviderIndexPluginInstall = {
  clawhubSpec?: string;
  npmSpec?: string;
  defaultChoice?: "clawhub" | "npm";
  minHostVersion?: string;
  expectedIntegrity?: string;
};

export type OpenClawProviderIndexPlugin = {
  id: string;
  package?: string;
  source?: string;
  install?: OpenClawProviderIndexPluginInstall;
};

export type OpenClawProviderIndexProviderAuthChoice = {
  method: string;
  choiceId: string;
  choiceLabel: string;
  choiceHint?: string;
  assistantPriority?: number;
  assistantVisibility?: "visible" | "manual-only";
  groupId?: string;
  groupLabel?: string;
  groupHint?: string;
  optionKey?: string;
  cliFlag?: string;
  cliOption?: string;
  cliDescription?: string;
  onboardingScopes?: readonly ("text-inference" | "image-generation" | "music-generation")[];
};

export type OpenClawProviderIndexProvider = {
  id: string;
  name: string;
  plugin: OpenClawProviderIndexPlugin;
  docs?: string;
  categories?: readonly string[];
  authChoices?: readonly OpenClawProviderIndexProviderAuthChoice[];
  previewCatalog?: ModelCatalogProvider;
};

export type OpenClawProviderIndex = {
  version: number;
  providers: Readonly<Record<string, OpenClawProviderIndexProvider>>;
};

```
