# 文件：src/server/routers/lambda/_schema/context.ts

## 文件职责
这个文件位于 `src/server/routers/lambda/_schema`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
export const conversationContextSchema = z.object({
export const basicContextSchema = z.object({
export type ConversationContextInput = z.infer<typeof conversationContextSchema>;
export type BasicContextInput = z.infer<typeof basicContextSchema>;
```

## 主要对外内容
```text
export const conversationContextSchema = z.object({
export const basicContextSchema = z.object({
export type ConversationContextInput = z.infer<typeof conversationContextSchema>;
export type BasicContextInput = z.infer<typeof basicContextSchema>;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

/**
 * Conversation context schema
 * Supports both agentId and sessionId for backward compatibility
 *
 * Priority: agentId > sessionId
 * When both are provided, agentId will be used to resolve the corresponding sessionId
 */
export const conversationContextSchema = z.object({
  agentId: z.string().optional(),
  groupId: z.string().nullable().optional(),
  sessionId: z.string().nullable().optional(),
  threadId: z.string().nullable().optional(),
  topicId: z.string().nullable().optional(),
});

/**
 * Simplified context
 * Used for CRUD operations of messages and topics
 */
export const basicContextSchema = z.object({
  agentId: z.string().optional(),
  groupId: z.string().nullable().optional(),
  sessionId: z.string().nullable().optional(),
  threadId: z.string().nullable().optional(),
  topicId: z.string().nullable().optional(),
});

export type ConversationContextInput = z.infer<typeof conversationContextSchema>;
export type BasicContextInput = z.infer<typeof basicContextSchema>;

```
