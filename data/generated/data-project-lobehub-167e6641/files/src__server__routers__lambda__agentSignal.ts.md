# 文件：src/server/routers/lambda/agentSignal.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import {
import debug from 'debug';
import { z } from 'zod';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { enqueueAgentSignalSourceEvent } from '@/server/services/agentSignal';
import { listAgentSignalReceipts } from '@/server/services/agentSignal/services/receiptService';
export const agentSignalRouter = router({
```

## 主要对外内容
```text
const log = debug('lobe-server:agent-signal:router');
const agentSignalProcedure = authedProcedure;
const clientSourceTypes = AGENT_SIGNAL_CLIENT_SOURCE_TYPES;
type ClientSourceType = (typeof clientSourceTypes)[number];
type ClientSourceEventInput = AgentSignalSourceEventInput<ClientSourceType>;
export const agentSignalRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import {
  AGENT_SIGNAL_CLIENT_SOURCE_TYPES,
  type AgentSignalSourceEventInput,
} from '@lobechat/agent-signal/source';
import debug from 'debug';
import { z } from 'zod';

import { authedProcedure, router } from '@/libs/trpc/lambda';
import { enqueueAgentSignalSourceEvent } from '@/server/services/agentSignal';
import { listAgentSignalReceipts } from '@/server/services/agentSignal/services/receiptService';

const log = debug('lobe-server:agent-signal:router');

const agentSignalProcedure = authedProcedure;
const clientSourceTypes = AGENT_SIGNAL_CLIENT_SOURCE_TYPES;

type ClientSourceType = (typeof clientSourceTypes)[number];
type ClientSourceEventInput = AgentSignalSourceEventInput<ClientSourceType>;

export const agentSignalRouter = router({
  emitSourceEvent: agentSignalProcedure
    .input(
      z.object({
        payload: z.record(z.string(), z.unknown()),
        scopeKey: z.string().optional(),
        sourceId: z.string(),
        sourceType: z.enum(clientSourceTypes),
        timestamp: z.number().optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      log('Received emitSourceEvent payload=%O', {
        agentId: typeof input.payload.agentId === 'string' ? input.payload.agentId : undefined,
        payload: input.payload,
        scopeKey: input.scopeKey,
        sourceId: input.sourceId,
        sourceType: input.sourceType,
        timestamp: input.timestamp,
        userId: ctx.userId,
      });

      return enqueueAgentSignalSourceEvent(input as unknown as ClientSourceEventInput, {
        agentId: typeof input.payload.agentId === 'string' ? input.payload.agentId : undefined,
        userId: ctx.userId,
      });
    }),
  listReceipts: agentSignalProcedure
    .input(
      z.object({
        agentId: z.string().min(1),
        cursor: z.number().int().min(0).optional(),
        limit: z.number().int().min(1).max(50).default(20),
        sinceCreatedAt: z.number().int().min(0).optional(),
        topicId: z.string().min(1),
      }),
    )
    .query(async ({ ctx, input }) => {
      return listAgentSignalReceipts({
        agentId: input.agentId,
        cursor: input.cursor,
        limit: input.limit,
        sinceCreatedAt: input.sinceCreatedAt,
        topicId: input.topicId,
        userId: ctx.userId,
      });
    }),
});

```
