# 文件：src/server/routers/lambda/agentNotify.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { RequestTrigger } from '@lobechat/types';
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import { z } from 'zod';
import { TopicModel } from '@/database/models/topic';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { AiAgentService } from '@/server/services/aiAgent';
export const agentNotifyRouter = router({
```

## 主要对外内容
```text
const log = debug('lobe-server:agent-notify-router');
const agentNotifyProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
const NotifySchema = z.object({
export const agentNotifyRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { RequestTrigger } from '@lobechat/types';
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import { z } from 'zod';

import { TopicModel } from '@/database/models/topic';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { AiAgentService } from '@/server/services/aiAgent';

const log = debug('lobe-server:agent-notify-router');

const agentNotifyProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      aiAgentService: new AiAgentService(ctx.serverDB, ctx.userId),
      topicModel: new TopicModel(ctx.serverDB, ctx.userId),
    },
  });
});

const NotifySchema = z.object({
  /** Agent ID to trigger (overrides the topic's default agent) */
  agentId: z.string().optional(),
  /** Message content from the external agent */
  content: z.string(),
  /** Thread ID for threaded conversations */
  threadId: z.string().optional(),
  /** Topic ID to send the message to */
  topicId: z.string(),
});

export const agentNotifyRouter = router({
  /**
   * Receive a callback message from an external agent (e.g. Claude Code),
   * write it into a topic, and trigger the agent loop to process it.
   */
  notify: agentNotifyProcedure.input(NotifySchema).mutation(async ({ input, ctx }) => {
    const { topicId, content, agentId: inputAgentId, threadId } = input;

    log('notify: topicId=%s, agentId=%s, content=%s', topicId, inputAgentId, content.slice(0, 80));

    // 1. Verify the topic exists and get its agentId
    const topic = await ctx.topicModel.findById(topicId);
    if (!topic) {
      throw new TRPCError({
        code: 'NOT_FOUND',
        message: `Topic ${topicId} not found`,
      });
    }

    const agentId = inputAgentId ?? topic.agentId;
    if (!agentId) {
      throw new TRPCError({
        code: 'BAD_REQUEST',
        message: `Topic ${topicId} has no associated agent and no agentId was provided`,
      });
    }

    // 2. Trigger the agent loop (execAgent handles message creation internally)
    try {
      const result = await ctx.aiAgentService.execAgent({
        agentId,
        appContext: { threadId, topicId },
        prompt: content,
        trigger: RequestTrigger.Notify,
      });

      return {
        operationId: result.operationId,
        topicId,
      };
    } catch (error: any) {
      console.error('agentNotify execAgent failed: %O', error);

      if (error instanceof TRPCError) {
        throw error;
      }

      throw new TRPCError({
        cause: error,
        code: 'INTERNAL_SERVER_ERROR',
        message: `Failed to trigger agent: ${error.message}`,
      });
    }
  }),
});

```
