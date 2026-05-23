# 文件：packages/model-runtime/src/providers/openrouter/type.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
interface ModelPricing {
  completion: string;
  image?: string;
  input_cache_read?: string;
  input_cache_write?: string;
  internal_reasoning?: string;
  prompt: string;
  request?: string;
  web_search?: string;
}

interface TopProvider {
  context_length: number;
  is_moderated: boolean;
  max_completion_tokens: number | null;
}

interface Architecture {
  input_modalities: string[];
  instruct_type: string | null;
  modality: string;
  output_modalities: string[];
  tokenizer: string;
}

export interface OpenRouterModelCard {
  architecture: Architecture;
  canonical_slug: string;
  context_length: number;
  created: number;
  default_parameters?: any | null;
  description?: string;
  hugging_face_id?: string;
  id: string;
  name: string;
  per_request_limits?: any | null;
  pricing: ModelPricing;
  supported_parameters: string[];
  top_provider: TopProvider;
}

export interface OpenRouterReasoning {
  effort?: 'none' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
  enabled?: boolean;
  exclude?: boolean;
  max_tokens?: number;
}

```
