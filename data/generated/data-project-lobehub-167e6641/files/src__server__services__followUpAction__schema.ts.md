# 文件：src/server/services/followUpAction/schema.ts

## 文件职责
这个文件位于 `src/server/services/followUpAction`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { GenerateObjectSchema } from '@lobechat/model-runtime';
import { z } from 'zod';
export const RawChipSchema = z.object({
export const RawResponseSchema = z.object({
export const SUGGESTION_RESPONSE_JSON_SCHEMA: GenerateObjectSchema = {
```

## 主要对外内容
```text
export const RawChipSchema = z.object({
export const RawResponseSchema = z.object({
export const SUGGESTION_RESPONSE_JSON_SCHEMA: GenerateObjectSchema = {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { GenerateObjectSchema } from '@lobechat/model-runtime';
import { z } from 'zod';

/**
 * Lenient schemas used to parse raw LLM output.
 * Length validation is performed manually in the service layer so individual
 * malformed chips can be dropped without rejecting the whole response.
 */
export const RawChipSchema = z.object({
  label: z.string(),
  message: z.string(),
});

export const RawResponseSchema = z.object({
  chips: z.array(RawChipSchema),
});

/** JSON schema form for LLM structured-output binding */
export const SUGGESTION_RESPONSE_JSON_SCHEMA: GenerateObjectSchema = {
  name: 'follow_up_suggestions',
  schema: {
    additionalProperties: false,
    properties: {
      chips: {
        items: {
          additionalProperties: false,
          properties: {
            label: { maxLength: 40, minLength: 1, type: 'string' },
            message: { maxLength: 200, minLength: 1, type: 'string' },
          },
          required: ['label', 'message'],
          type: 'object',
        },
        maxItems: 8,
        type: 'array',
      },
    },
    required: ['chips'],
    type: 'object',
  },
  strict: true,
};

```
