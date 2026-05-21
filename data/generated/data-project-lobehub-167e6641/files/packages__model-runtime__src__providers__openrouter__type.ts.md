# 文件：packages/model-runtime/src/providers/openrouter/type.ts

## 文件职责
这个文件位于 `packages/model-runtime/src/providers/openrouter`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
export interface OpenRouterModelCard {
export interface OpenRouterReasoning {
```

## 主要对外内容
```text
interface ModelPricing {
interface TopProvider {
interface Architecture {
export interface OpenRouterModelCard {
export interface OpenRouterReasoning {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
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
