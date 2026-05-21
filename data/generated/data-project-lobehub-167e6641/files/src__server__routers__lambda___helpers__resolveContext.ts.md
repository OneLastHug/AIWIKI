# 文件：src/server/routers/lambda/_helpers/resolveContext.ts

## 文件职责
这个文件位于 `src/server/routers/lambda/_helpers`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { and, eq, inArray } from 'drizzle-orm';
import { agentsToSessions } from '@/database/schemas';
import { type LobeChatDatabase } from '@/database/type';
import { type ConversationContextInput } from '../_schema/context';
export interface ResolvedContext {
export const resolveContext = async (
export const resolveAgentIdFromSession = async (
export const batchResolveAgentIdFromSessions = async (
```

## 主要对外内容
```text
export interface ResolvedContext {
export const resolveContext = async (
export const resolveAgentIdFromSession = async (
export const batchResolveAgentIdFromSessions = async (
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { and, eq, inArray } from 'drizzle-orm';

import { agentsToSessions } from '@/database/schemas';
import { type LobeChatDatabase } from '@/database/type';

import { type ConversationContextInput } from '../_schema/context';

export interface ResolvedContext {
  agentId: string | null;
  groupId: string | null;
  sessionId: string | null;
  threadId: string | null;
  topicId: string | null;
}

/**
 * Resolve conversation context
 *
 * Resolves agentId to sessionId (if agentId is provided)
 * Priority: agentId > sessionId
 *
 * @param input - Input context parameters
 * @param db - Database instance
 * @param userId - User ID
 * @returns Resolved context with sessionId resolved from agentId
 */
export const resolveContext = async (
  input: ConversationContextInput,
  db: LobeChatDatabase,
  userId: string,
): Promise<ResolvedContext> => {
  let resolvedSessionId: string | null = input.sessionId ?? null;

  // If agentId is provided, prioritize looking up the corresponding sessionId from agentsToSessions table
  if (input.agentId) {
    const [relation] = await db
      .select({ sessionId: agentsToSessions.sessionId })
      .from(agentsToSessions)
      .where(and(eq(agentsToSessions.agentId, input.agentId), eq(agentsToSessions.userId, userId)))
      .limit(1);

    if (relation) {
      resolvedSessionId = relation.sessionId;
    }
  }

  return {
    agentId: input.agentId ?? null,
    groupId: input.groupId ?? null,
    sessionId: resolvedSessionId,
    threadId: input.threadId ?? null,
    topicId: input.topicId ?? null,
  };
};

/**
 * Reverse resolution: Get agentId from sessionId
 *
 * Used in scenarios like Topic Router where agentId is needed for queries
 *
 * @param sessionId - session ID
 * @param db - Database instance
 * @param userId - User ID
 * @returns agentId or undefined
 */
export const resolveAgentIdFromSession = async (
  sessionId: string,
  db: LobeChatDatabase,
  userId: string,
): Promise<string | undefined> => {
  const [relation] = await db
    .select({ agentId: agentsToSessions.agentId })
    .from(agentsToSessions)
    .where(and(eq(agentsToSessions.sessionId, sessionId), eq(agentsToSessions.userId, userId)))
    .limit(1);

  return relation?.agentId;
};

/**
 * Batch reverse resolution: Get agentId mapping from multiple sessionIds
 *
 * Used in scenarios requiring batch sessionId -> agentId resolution (e.g., recentTopics)
 *
 * @param sessionIds - Array of session IDs
 * @param db - Database instance
 * @param userId - User ID
 * @returns Map of sessionId -> agentId
 */
export const batchResolveAgentIdFromSessions = async (
  sessionIds: string[],
  db: LobeChatDatabase,
  userId: string,
): Promise<Map<string, string>> => {
  if (sessionIds.length === 0) return new Map();

  const relations = await db
    .select({ agentId: agentsToSessions.agentId, sessionId: agentsToSessions.sessionId })
    .from(agentsToSessions)
    .where(
      and(eq(agentsToSessions.userId, userId), inArray(agentsToSessions.sessionId, sessionIds)),
    );

  return new Map(relations.map((r) => [r.sessionId, r.agentId]));
};

```
