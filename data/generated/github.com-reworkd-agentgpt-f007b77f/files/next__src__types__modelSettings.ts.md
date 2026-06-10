# 文件：next/src/types/modelSettings.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { type Language } from "../utils/languages";

export const [GPT_35_TURBO, GPT_35_TURBO_16K, GPT_4] = [
  "gpt-3.5-turbo" as const,
  "gpt-3.5-turbo-16k" as const,
  "gpt-4" as const,
];
export const GPT_MODEL_NAMES = [GPT_35_TURBO, GPT_35_TURBO_16K, GPT_4];
export type GPTModelNames = "gpt-3.5-turbo" | "gpt-3.5-turbo-16k" | "gpt-4";

export const MAX_TOKENS: Record<GPTModelNames, number> = {
  "gpt-3.5-turbo": 4000,
  "gpt-3.5-turbo-16k": 16000,
  "gpt-4": 4000,
};

export interface ModelSettings {
  language: Language;
  customApiKey: string;
  customModelName: GPTModelNames;
  customTemperature: number;
  customMaxLoops: number;
  maxTokens: number;
}

```
