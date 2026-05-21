# 文件：src/server/routers/lambda/aiAgent.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type AgentStreamEvent } from '@lobechat/agent-gateway-client';
import { parse } from '@lobechat/conversation-flow';
import { type TaskCurrentActivity, type TaskStatusResult } from '@lobechat/types';
import {
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import pMap from 'p-map';
import { z } from 'zod';
import { MessageModel } from '@/database/models/message';
import { TaskModel } from '@/database/models/task';
import { TaskTopicModel } from '@/database/models/taskTopic';
import { ThreadModel } from '@/database/models/thread';
import { TopicModel } from '@/database/models/topic';
import { authedProcedure, heteroAuthedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { AgentRuntimeService } from '@/server/services/agentRuntime';
import { AiAgentService } from '@/server/services/aiAgent';
import { AiChatService } from '@/server/services/aiChat';
import { HeterogeneousAgentService } from '@/server/services/heterogeneousAgent';
import { TaskLifecycleService } from '@/server/services/taskLifecycle';
export const aiAgentRouter = router({
```

## 主要对外内容
```text
const log = debug('lobe-server:ai-agent-router');
const extractTaskErrorMessage = (error: unknown): string | undefined => {
const formatTaskError = (error: unknown): Record<string, unknown> | undefined => {
const GetOperationStatusSchema = z.object({
const ProcessHumanInterventionSchema = z.object({
const GetPendingInterventionsSchema = z
const StartExecutionSchema = z.object({
const ExecAgentSchema = z
const ExecGroupAgentSchema = z.object({
const ExecAgentsSchema = z.object({
const ExecSubAgentTaskSchema = z.object({
const CreateClientTaskThreadSchema = z.object({
const CreateClientGroupAgentTaskThreadSchema = z.object({
const UpdateClientTaskThreadStatusSchema = z.object({
const InterruptTaskSchema = z
const AgentStreamEventSchema = z.object({
const HeteroIngestSchema = z.object({
const HeteroFinishSchema = z.object({
const aiAgentProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
const heteroAgentProcedure = heteroAuthedProcedure.use(serverDatabase).use(async (opts) => {
export const aiAgentRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type AgentStreamEvent } from '@lobechat/agent-gateway-client';
import { parse } from '@lobechat/conversation-flow';
import { type TaskCurrentActivity, type TaskStatusResult } from '@lobechat/types';
import {
  RequestTrigger,
  ThreadStatus,
  ThreadType,
  UserInterventionConfigSchema,
} from '@lobechat/types';
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import pMap from 'p-map';
import { z } from 'zod';

import { MessageModel } from '@/database/models/message';
import { TaskModel } from '@/database/models/task';
import { TaskTopicModel } from '@/database/models/taskTopic';
import { ThreadModel } from '@/database/models/thread';
import { TopicModel } from '@/database/models/topic';
import { authedProcedure, heteroAuthedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { AgentRuntimeService } from '@/server/services/agentRuntime';
import { AiAgentService } from '@/server/services/aiAgent';
import { AiChatService } from '@/server/services/aiChat';
import { HeterogeneousAgentService } from '@/server/services/heterogeneousAgent';
import { TaskLifecycleService } from '@/server/services/taskLifecycle';

const log = debug('lobe-server:ai-agent-router');

const extractTaskErrorMessage = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object') return undefined;

  const taskError = error as Record<string, any>;
  const candidates = [
    taskError.body?.error?.message,
    taskError.body?.message,
    taskError.error?.error?.message,
    taskError.error?.message,
    taskError.message,
    taskError.type,
    taskError.errorType,
    taskError.name,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate !== '[object Object]' && candidate !== 'error') {
      return candidate;
    }
  }

  return undefined;
};

const formatTaskError = (error: unknown): Record<string, unknown> | undefined => {
  if (!error) return undefined;

  if (error instanceof Error) {
    return {
      message: error.message,
      name: error.name,
    };
  }

  if (typeof error === 'string') {
    return { message: error };
  }

  if (typeof error !== 'object') {
    return { message: String(error) };
  }

  const taskError = error as Record<string, unknown>;
  const message = extractTaskErrorMessage(error);

  return message ? { ...taskError, message } : taskError;
};

const GetOperationStatusSchema = z.object({
  historyLimit: z.number().optional().default(10),
  includeHistory: z.boolean().optional().default(false),
  operationId: z.string(),
});

const ProcessHumanInterventionSchema = z.object({
  action: z.enum(['approve', 'reject', 'reject_continue', 'input', 'select']),
  data: z
    .object({
      approvedToolCall: z.any().optional(),
      input: z.any().optional(),
      selection: z.any().optional(),
    })
    .optional(),
  operationId: z.string(),
  reason: z.string().optional(),
  stepIndex: z.number().optional().default(0),
  /**
   * ID of the pending `role='tool'` message targeted by this intervention.
   * Required for approve / reject / reject_continue so the server can update
   * the message's intervention status, content, and — on approve — hand the
   * id to the `call_tool` short-circuit via `skipCreateToolMessage`.
   */
  toolMessageId: z.string().optional(),
});

const GetPendingInterventionsSchema = z
  .object({
    operationId: z.string().optional(),
    userId: z.string().optional(),
  })
  .refine((data) => data.operationId || data.userId, {
    message: 'Either operationId or userId must be provided',
  });

const StartExecutionSchema = z.object({
  context: z.any().optional(),
  delay: z.number().optional().default(1000),
  operationId: z.string(),
  priority: z.enum(['high', 'normal', 'low']).optional().default('normal'),
});

/**
 * Schema for execAgent - execute a single Agent
 */
const ExecAgentSchema = z
  .object({
    /** The agent ID to run (either agentId or slug is required) */
    agentId: z.string().optional(),
    /** Application context for message storage */
    appContext: z
      .object({
        defaultTaskAssigneeAgentId: z.string().optional(),
        documentId: z.string().optional().nullable(),
        groupId: z.string().optional().nullable(),
        initialTopicMetadata: z
          .object({
            repos: z.array(z.string()).optional(),
            workingDirectory: z.string().optional(),
          })
          .optional(),
        scope: z.string().optional().nullable(),
        sessionId: z.string().optional(),
        taskId: z.string().optional().nullable(),
        threadId: z.string().optional().nullable(),
        topicId: z.string().optional().nullable(),
      })
      .optional(),
    /** Whether to auto-start execution after creating operation */
    autoStart: z.boolean().optional().default(true),
    /**
     * Runtime of the client initiating this request.
     * 'desktop' enables `executor: 'client'` tools (local-system, stdio MCP)
     * to be dispatched over the Agent Gateway WS.
     */
    clientRuntime: z.enum(['desktop', 'web']).optional(),
    /** Explicit device ID to bind to the topic and activate for this run */
    deviceId: z.string().optional(),
    /** Optional existing message IDs to include in context */
    existingMessageIds: z.array(z.string()).optional().default([]),
    /** File IDs of already-uploaded attachments to attach to the new user message */
    fileIds: z.array(z.string()).optional(),
    /** Parent message ID for regeneration/continue (skip user message creation, branch from this message) */
    parentMessageId: z.string().optional(),
    /** The user input/prompt */
    prompt: z.string(),
    /**
     * Resume a previous op paused on `human_approve_required`. When set, the
     * new op writes the decision to the target tool message and either runs
     * the approved tool (`approved`), halts with reason=`human_rejected`
     * (`rejected`), or surfaces the rejection as user feedback so the LLM
     * can continue (`rejected_continue`).
     */
    resumeApproval: z
      .object({
        decision: z.enum(['approved', 'rejected', 'rejected_continue']),
        /** ID of the pending `role='tool'` message this decision targets. */
        parentMessageId: z.string(),
        /** Optional user-supplied rejection reason (only meaningful for rejected variants). */
        rejectionReason: z.string().optional(),
        /** tool_call_id of the pending tool call being approved/rejected. */
        toolCallId: z.string(),
      })
      .optional(),
    /** The agent slug to run (either agentId or slug is required) */
    slug: z.string().optional(),
    /**
     * What initiated this operation, persisted to `agent_operations.trigger`.
     * Defaults to `'chat'` when omitted — first-party SPA / desktop user
     * messages are the dominant caller. Pass a more specific value (`'cli'`,
     * `'openapi'`, `'eval'`, …) to override.
     */
    trigger: z.string().optional(),
    /**
     * User intervention configuration for tool approvals.
     * Pass `{ approvalMode: 'headless' }` from headless clients (CLI, cron, bots)
     * so tool calls auto-execute without waiting for human approval.
     */
    userInterventionConfig: UserInterventionConfigSchema.optional(),
  })
  .refine((data) => data.agentId || data.slug, {
    message: 'Either agentId or slug must be provided',
  });

/**
 * Schema for execGroupAgent - execute Supervisor Agent in Group chat
 */
const ExecGroupAgentSchema = z.object({
  /** The Supervisor agent ID */
  agentId: z.string(),
  /** File IDs attached to the message */
  files: z.array(z.string()).optional(),
  /** The Group ID */
  groupId: z.string(),
  /** User message content */
  message: z.string(),
  /** Optional: Create a new topic */
  newTopic: z
    .object({
      title: z.string().optional(),
      topicMessageIds: z.array(z.string()).optional(),
    })
    .optional(),
  /** Existing topic ID */
  topicId: z.string().optional().nullable(),
});

/**
 * Schema for execAgents - batch execution of multiple agents
 */
const ExecAgentsSchema = z.object({
  /** Whether to execute tasks in parallel (default: true) */
  parallel: z.boolean().optional().default(true),
  /** Array of agent tasks to execute */
  tasks: z.array(ExecAgentSchema).min(1),
});

/**
 * Schema for execSubAgentTask - execute SubAgent task
 * Supports both Group mode (with groupId) and Single Agent mode (without groupId)
 */
const ExecSubAgentTaskSchema = z.object({
  /** The SubAgent ID to execute the task */
  agentId: z.string(),
  /** The Group ID (optional, only for Group mode) */
  groupId: z.string().optional(),
  /** Task instruction/prompt for the SubAgent */
  instruction: z.string(),
  /** The parent message ID (Supervisor's tool call message or task message) */
  parentMessageId: z.string(),
  /** Timeout in milliseconds (optional) */
  timeout: z.number().optional(),
  /** Task title (shown in UI, used as thread title) */
  title: z.string().optional(),
  /** The Topic ID */
  topicId: z.string(),
});

/**
 * Schema for createClientTaskThread - create Thread for client-side task execution
 * This is used when runInClient=true on desktop client (single agent mode)
 */
const CreateClientTaskThreadSchema = z.object({
  /** The Agent ID to execute the task */
  agentId: z.string(),
  /** The Group ID (optional, only for Group mode) */
  groupId: z.string().optional(),
  /** Initial user message content (task instruction) */
  instruction: z.string(),
  /** The parent message ID (task message) */
  parentMessageId: z.string(),
  /** Task title (shown in UI, used as thread title) */
  title: z.string().optional(),
  /** The Topic ID */
  topicId: z.string(),
});

/**
 * Schema for createClientGroupAgentTaskThread - create Thread for client-side task execution in Group mode
 * This is specifically for Group Chat where messages may have different agentIds
 */
const CreateClientGroupAgentTaskThreadSchema = z.object({
  /** The Group ID (required for Group mode) */
  groupId: z.string(),
  /** Initial user message content (task instruction) */
  instruction: z.string(),
  /** The parent message ID (task message) */
  parentMessageId: z.string(),
  /** The Sub-Agent ID that will execute the task (worker agent in group) */
  subAgentId: z.string(),
  /** Task title (shown in UI, used as thread title) */
  title: z.string().optional(),
  /** The Topic ID */
  topicId: z.string(),
});

/**
 * Schema for updateClientTaskThreadStatus - update Thread status after client-side execution
 */
const UpdateClientTaskThreadStatusSchema = z.object({
  /** Completion reason */
  completionReason: z.enum(['done', 'error', 'interrupted']),
  /** Error message if failed */
  error: z.string().optional(),
  /** Thread metadata to update */
  metadata: z
    .object({
      totalCost: z.number().optional(),
      totalMessages: z.number().optional(),
      totalSteps: z.number().optional(),
      totalTokens: z.number().optional(),
      totalToolCalls: z.number().optional(),
    })
    .optional(),
  /** Result content (last assistant message) */
  resultContent: z.string().optional(),
  /** The Thread ID */
  threadId: z.string(),
});

/**
 * Schema for interruptTask - interrupt a running task
 */
const InterruptTaskSchema = z
  .object({
    /** Operation ID */
    operationId: z.string().optional(),
    /** Thread ID */
    threadId: z.string().optional(),
  })
  .refine((data) => data.threadId || data.operationId, {
    message: 'Either threadId or operationId must be provided',
  });

/**
 * Wire shape of an `AgentStreamEvent` produced by `lh hetero exec`. Mirrors
 * `AgentStreamEvent` in `@lobechat/agent-gateway-client` (kept here as a Zod
 * schema for tRPC input validation; tRPC's type inference takes care of the
 * client-side typing). Republished verbatim through `StreamEventManager` so
 * gateway WS subscribers see the same shape regardless of producer.
 */
const AgentStreamEventSchema = z.object({
  data: z.any(),
  operationId: z.string(),
  stepIndex: z.number().int().nonnegative(),
  timestamp: z.number().int().nonnegative(),
  type: z.enum([
    'agent_runtime_init',
    'agent_runtime_end',
    'stream_start',
    'stream_chunk',
    'stream_end',
    'stream_retry',
    'tool_start',
    'tool_end',
    'tool_execute',
    'tool_result',
    'agent_intervention_request',
    'agent_intervention_response',
    'step_start',
    'step_complete',
    'error',
  ]),
});

/**
 * Schema for `aiAgent.heteroIngest` — accepts a batch of producer-side
 * `AgentStreamEvent`s from `lh hetero exec`. `topicId` is required (operationId
 * → topic reverse-lookup is unreliable per LOBE-8516 design decision).
 */
const HeteroIngestSchema = z.object({
  agentType: z.enum(['claude-code', 'codex']),
  events: z.array(AgentStreamEventSchema).min(1),
  operationId: z.string().min(1),
  topicId: z.string().min(1),
});

/**
 * Schema for `aiAgent.heteroFinish` — terminal call, mirrors the CLI process
 * exit. `result` is the high-level outcome; `error` carries CLI-classified
 * details when `result === 'error'`. `sessionId` is the native CLI session
 * (CC's per-cwd id), kept here so the server can resume next time.
 */
const HeteroFinishSchema = z.object({
  agentType: z.enum(['claude-code', 'codex']),
  error: z
    .object({
      message: z.string(),
      type: z.string(),
    })
    .optional(),
  operationId: z.string().min(1),
  result: z.enum(['success', 'error', 'cancelled']),
  sessionId: z.string().optional(),
  topicId: z.string().min(1),
});

const aiAgentProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      agentRuntimeService: new AgentRuntimeService(ctx.serverDB, ctx.userId),
      aiAgentService: new AiAgentService(ctx.serverDB, ctx.userId),
      aiChatService: new AiChatService(ctx.serverDB, ctx.userId),
      heterogeneousAgentService: new HeterogeneousAgentService(ctx.serverDB, ctx.userId),
      messageModel: new MessageModel(ctx.serverDB, ctx.userId),
      threadModel: new ThreadModel(ctx.serverDB, ctx.userId),
      topicModel: new TopicModel(ctx.serverDB, ctx.userId),
    },
  });
});

// Dedicated procedure for hetero-agent ingest/finish endpoints.
// Requires a `hetero-operation` JWT (4h expiry) — normal user tokens are rejected,
// so only the sandbox/device that received the JWT from execAgent can call these.
const heteroAgentProcedure = heteroAuthedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      heterogeneousAgentService: new HeterogeneousAgentService(ctx.serverDB, ctx.userId),
    },
  });
});

export const aiAgentRouter = router({
  /**
   * Create Thread for client-side task execution in Group mode
   *
   * This endpoint is specifically designed for Group Chat scenarios where:
   * - Messages in the thread may have different agentIds (supervisor, workers)
   * - The subAgentId is the worker agent that executes the task
   * - Thread messages query should not filter by agentId to include all parent messages
   */
  createClientGroupAgentTaskThread: aiAgentProcedure
    .input(CreateClientGroupAgentTaskThreadSchema)
    .mutation(async ({ input, ctx }) => {
      const { groupId, instruction, parentMessageId, subAgentId, title, topicId } = input;

      log('createClientGroupAgentTaskThread: subAgentId=%s, groupId=%s', subAgentId, groupId);

      try {
        // 1. Create Thread for isolated task execution
        // Use subAgentId as the thread's agentId (the executing agent)
        const startedAt = new Date().toISOString();
        const thread = await ctx.threadModel.create({
          agentId: subAgentId,
          groupId,
          metadata: { clientMode: true, startedAt },
          sourceMessageId: parentMessageId,
          status: ThreadStatus.Processing,
          title,
          topicId,
          type: ThreadType.Isolation,
        });

        if (!thread) {
          throw new TRPCError({
            code: 'INTERNAL_SERVER_ERROR',
            message: 'Failed to create thread for task execution',
          });
        }

        log('createClientGroupAgentTaskThread: created thread %s', thread.id);

        // 2. Create initial user message (persisted to database)
        // Use subAgentId as the message's agentId
        const userMessage = await ctx.messageModel.create({
          agentId: subAgentId,
          content: instruction,
          groupId,
          parentId: parentMessageId,
          role: 'user',
          threadId: thread.id,
          topicId,
        });

        log('createClientGroupAgentTaskThread: created user message %s', userMessage.id);

        // 3. Query thread messages and main chat messages in parallel
        const [threadMessages, messages] = await Promise.all([
          // Thread messages (messages within this thread)
          // DON'T pass agentId - thread query fetches parent messages via sourceMessageId
          // which may have different agentIds (supervisor vs worker in group chat)
          ctx.messageModel.query({ threadId: thread.id, topicId }),
          // Main chat messages (messages without threadId)
          // Only filter by groupId + topicId (not agentId) to include all agents' messages
          ctx.messageModel.query({ groupId, topicId }),
        ]);

        log(
          'createClientGroupAgentTaskThread: queried %d thread messages, %d main messages',
          threadMessages.length,
          messages.length,
        );

        // 4. Return Thread, userMessageId, threadMessages and messages
        return {
          messages,
          startedAt,
          success: true,
          threadId: thread.id,
          threadMessages,
          userMessageId: userMessage.id,
        };
      } catch (error: any) {
        log('createClientGroupAgentTaskThread failed: %O', error);

        if (error instanceof TRPCError) {
          throw error;
        }

        throw new TRPCError({
          cause: error,
          code: 'INTERNAL_SERVER_ERROR',
          message: `Failed to create client group agent task thread: ${error.message}`,
        });
      }
    }),

  /**
   * Create Thread for client-side task execution
   *
   * This endpoint is called by desktop client when runInClient=true.
   * It creates the Thread but does NOT execute the task - execution happens on client side.
   */
  createClientTaskThread: aiAgentProcedure
    .input(CreateClientTaskThreadSchema)
    .mutation(async ({ input, ctx }) => {
      const { agentId, groupId, instruction, parentMessageId, title, topicId } = input;

      log('createClientTaskThread: agentId=%s, groupId=%s', agentId, groupId);

      try {
        // 1. Create Thread for isolated task execution
        const startedAt = new Date().toISOString();
        const thread = await ctx.threadModel.create({
          agentId,
          groupId,
          metadata: { clientMode: true, startedAt },
          sourceMessageId: parentMessageId,
          status: ThreadStatus.Processing,
          title,
          topicId,
          type: ThreadType.Isolation,
        });

        if (!thread) {
          throw new TRPCError({
            code: 'INTERNAL_SERVER_ERROR',
            message: 'Failed to create thread for task execution',
          });
        }

        log('createClientTaskThread: created thread %s', thread.id);

        // 2. Create initial user message (persisted to database)
        const userMessage = await ctx.messageModel.create({
          agentId,
          content: instruction,
          groupId,
          parentId: parentMessageId,
          role: 'user',
          threadId: thread.id,
          topicId,
        });

        log('createClientTaskThread: created user message %s', userMessage.id);

        // 3. Query thread messages and main chat messages in parallel
        const [threadMessages, messages] = await Promise.all([
          // Thread messages (messages within this thread)
          ctx.messageModel.query({ agentId, threadId: thread.id, topicId }),
          // Main chat messages (messages without threadId, includes updated taskDetail)
          // Pass both agentId and groupId - query() prioritizes groupId when present
          ctx.messageModel.query({ agentId, groupId, topicId }),
        ]);

        log(
          'createClientTaskThread: queried %d thread messages, %d main messages',
          threadMessages.length,
          messages.length,
        );

        // 4. Return Thread, userMessageId, threadMessages and messages
        return {
          messages,
          startedAt,
          success: true,
          threadId: thread.id,
          threadMessages,
          userMessageId: userMessage.id,
        };
      } catch (error: any) {
        log('createClientTaskThread failed: %O', error);

        if (error instanceof TRPCError) {
          throw error;
        }

        throw new TRPCError({
          cause: error,
          code: 'INTERNAL_SERVER_ERROR',
          message: `Failed to create client task thread: ${error.message}`,
        });
      }
    }),

  execAgent: aiAgentProcedure.input(ExecAgentSchema).mutation(async ({ input, ctx }) => {
    const {
      agentId,
      slug,
      prompt,
      appContext,
      autoStart = true,
      clientRuntime,
      deviceId,
      existingMessageIds = [],
      fileIds,
      parentMessageId,
      resumeApproval,
      trigger,
      userInterventionConfig,
    } = input;

    log('execAgent: identifier=%s, prompt=%s', agentId || slug, prompt.slice(0, 50));

    try {
      return await ctx.aiAgentService.execAgent({
        agentId,
        appContext,
        autoStart,
        clientRuntime,
        deviceId,
        existingMessageIds,
        fileIds,
        parentMessageId,
        prompt,
        // When parentMessageId is provided, this is a regeneration/c
```
