# 文件：src/server/services/aiAgent/index.ts

## 文件职责
这个文件位于 `src/server/services/aiAgent`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { AgentRuntimeContext, AgentState } from '@lobechat/agent-runtime';
import { BUILTIN_AGENT_SLUGS, getAgentRuntimeConfig } from '@lobechat/builtin-agents';
import { builtinSkills } from '@lobechat/builtin-skills';
import { LobeAgentManifest } from '@lobechat/builtin-tool-lobe-agent';
import { LocalSystemManifest } from '@lobechat/builtin-tool-local-system';
import { MessageToolIdentifier } from '@lobechat/builtin-tool-message';
import { PageAgentIdentifier } from '@lobechat/builtin-tool-page-agent';
import type { DeviceAttachment } from '@lobechat/builtin-tool-remote-device';
import { generateSystemPrompt, RemoteDeviceManifest } from '@lobechat/builtin-tool-remote-device';
import {
import { TaskIdentifier } from '@lobechat/builtin-tool-task';
import { builtinTools, manualModeExcludeToolIds } from '@lobechat/builtin-tools';
import { LOADING_FLAT } from '@lobechat/const';
import type {
import { SkillEngine } from '@lobechat/context-engine';
import type { LobeChatDatabase } from '@lobechat/database';
import { buildTaskManagerDefaultsPrompt } from '@lobechat/prompts';
import type {
import { RequestTrigger, ThreadStatus, ThreadType } from '@lobechat/types';
import { nanoid } from '@lobechat/utils';
import debug from 'debug';
import { AgentModel } from '@/database/models/agent';
import { AgentOperationModel } from '@/database/models/agentOperation';
import { AgentSkillModel } from '@/database/models/agentSkill';
import { AiModelModel } from '@/database/models/aiModel';
import { FileModel } from '@/database/models/file';
import { MessageModel } from '@/database/models/message';
import { PluginModel } from '@/database/models/plugin';
import { TaskModel } from '@/database/models/task';
import { ThreadModel } from '@/database/models/thread';
import { TopicModel } from '@/database/models/topic';
import { UserModel } from '@/database/models/user';
import { UserPersonaModel } from '@/database/models/userMemory/persona';
import { toolsEnv } from '@/envs/tools';
import { shouldEnableBuiltinSkill } from '@/helpers/skillFilters';
import { signOperationJwt, signUserJWT } from '@/libs/trpc/utils/internalJwt';
import type { EvalContext, ServerAgentToolsContext } from '@/server/modules/Mecha';
import { createServerAgentToolsEngine } from '@/server/modules/Mecha';
import type { ServerUserMemoryConfig } from '@/server/modules/Mecha/ContextEngineering/types';
import { AgentService } from '@/server/services/agent';
```

## 主要对外内容
```text
const log = debug('lobe-server:ai-agent-service');
function formatErrorForMetadata(error: unknown): Record<string, any> | undefined {
const getVisualAvailabilityFromFileTypes = (fileTypes: string[]) => ({
interface VisualAvailabilityMessage {
const getVisualAvailabilityFromMessages = (messages: VisualAvailabilityMessage[]) => ({
const isVisualUnderstandingConfigured = () => {
interface InternalExecAgentParams extends ExecAgentParams {
export class AiAgentService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { AgentRuntimeContext, AgentState } from '@lobechat/agent-runtime';
import { BUILTIN_AGENT_SLUGS, getAgentRuntimeConfig } from '@lobechat/builtin-agents';
import { builtinSkills } from '@lobechat/builtin-skills';
import { LobeAgentManifest } from '@lobechat/builtin-tool-lobe-agent';
import { LocalSystemManifest } from '@lobechat/builtin-tool-local-system';
import { MessageToolIdentifier } from '@lobechat/builtin-tool-message';
import { PageAgentIdentifier } from '@lobechat/builtin-tool-page-agent';
import type { DeviceAttachment } from '@lobechat/builtin-tool-remote-device';
import { generateSystemPrompt, RemoteDeviceManifest } from '@lobechat/builtin-tool-remote-device';
import {
  injectSelfFeedbackIntentTool,
  shouldExposeSelfFeedbackIntentTool,
} from '@lobechat/builtin-tool-self-iteration';
import { TaskIdentifier } from '@lobechat/builtin-tool-task';
import { builtinTools, manualModeExcludeToolIds } from '@lobechat/builtin-tools';
import { LOADING_FLAT } from '@lobechat/const';
import type {
  AgentManagementContext,
  BotPlatformContext,
  LobeToolManifest,
  ToolExecutor,
  ToolSource,
} from '@lobechat/context-engine';
import { SkillEngine } from '@lobechat/context-engine';
import type { LobeChatDatabase } from '@lobechat/database';
import { buildTaskManagerDefaultsPrompt } from '@lobechat/prompts';
import type {
  ChatFileItem,
  ChatTopicBotContext,
  ChatVideoItem,
  ExecAgentParams,
  ExecAgentResult,
  ExecGroupAgentParams,
  ExecGroupAgentResult,
  ExecSubAgentTaskParams,
  ExecSubAgentTaskResult,
  MessagePluginItem,
  UserInterventionConfig,
} from '@lobechat/types';
import { RequestTrigger, ThreadStatus, ThreadType } from '@lobechat/types';
import { nanoid } from '@lobechat/utils';
import debug from 'debug';

import { AgentModel } from '@/database/models/agent';
import { AgentOperationModel } from '@/database/models/agentOperation';
import { AgentSkillModel } from '@/database/models/agentSkill';
import { AiModelModel } from '@/database/models/aiModel';
import { FileModel } from '@/database/models/file';
import { MessageModel } from '@/database/models/message';
import { PluginModel } from '@/database/models/plugin';
import { TaskModel } from '@/database/models/task';
import { ThreadModel } from '@/database/models/thread';
import { TopicModel } from '@/database/models/topic';
import { UserModel } from '@/database/models/user';
import { UserPersonaModel } from '@/database/models/userMemory/persona';
import { toolsEnv } from '@/envs/tools';
import { shouldEnableBuiltinSkill } from '@/helpers/skillFilters';
import { signOperationJwt, signUserJWT } from '@/libs/trpc/utils/internalJwt';
import type { EvalContext, ServerAgentToolsContext } from '@/server/modules/Mecha';
import { createServerAgentToolsEngine } from '@/server/modules/Mecha';
import type { ServerUserMemoryConfig } from '@/server/modules/Mecha/ContextEngineering/types';
import { AgentService } from '@/server/services/agent';
import { AgentDocumentsService } from '@/server/services/agentDocuments';
import type { AgentRuntimeServiceOptions } from '@/server/services/agentRuntime';
import { AgentRuntimeService } from '@/server/services/agentRuntime';
import { getAbortError, isAbortError, throwIfAborted } from '@/server/services/agentRuntime/abort';
import { hookDispatcher } from '@/server/services/agentRuntime/hooks';
import type { AgentHook } from '@/server/services/agentRuntime/hooks/types';
import type { StepLifecycleCallbacks } from '@/server/services/agentRuntime/types';
import { enqueueAgentSignalSourceEvent } from '@/server/services/agentSignal';
import {
  isAgentSignalEnabledForUser,
  isLobeAiAgentSlug,
  resolveAgentSelfIterationCapability,
} from '@/server/services/agentSignal/featureGate';
import { DocumentService } from '@/server/services/document';
import { FileService } from '@/server/services/file';
import { HeterogeneousAgentService } from '@/server/services/heterogeneousAgent';
import { KlavisService } from '@/server/services/klavis';
import { MarketService } from '@/server/services/market';
import { deviceProxy } from '@/server/services/toolExecution/deviceProxy';

import { resolveDeviceAccessPolicy } from './deviceAccessPolicy';
import { buildAllowedBuiltinTools, isDeviceToolIdentifier } from './deviceToolRegistry';
import { ingestAttachment } from './ingestAttachment';

const log = debug('lobe-server:ai-agent-service');

/**
 * Format error for storage in thread metadata
 * Handles Error objects which don't serialize properly with JSON.stringify
 */
function formatErrorForMetadata(error: unknown): Record<string, any> | undefined {
  if (!error) return undefined;

  // Handle Error objects
  if (error instanceof Error) {
    return {
      message: error.message,
      name: error.name,
    };
  }

  // Handle objects with message property (like ChatMessageError)
  if (typeof error === 'object' && 'message' in error) {
    return error as Record<string, any>;
  }

  // Fallback: wrap in object
  return { message: String(error) };
}

const getVisualAvailabilityFromFileTypes = (fileTypes: string[]) => ({
  hasImages: fileTypes.some((fileType) => fileType.startsWith('image')),
  hasVideos: fileTypes.some((fileType) => fileType.startsWith('video')),
});

interface VisualAvailabilityMessage {
  imageList?: unknown[];
  role?: string;
  videoList?: unknown[];
}

const getVisualAvailabilityFromMessages = (messages: VisualAvailabilityMessage[]) => ({
  hasImages: messages.some(
    (message) => message.role === 'user' && (message.imageList?.length ?? 0) > 0,
  ),
  hasVideos: messages.some(
    (message) => message.role === 'user' && (message.videoList?.length ?? 0) > 0,
  ),
});

const isVisualUnderstandingConfigured = () => {
  try {
    return !!toolsEnv.VISUAL_UNDERSTANDING_PROVIDER && !!toolsEnv.VISUAL_UNDERSTANDING_MODEL;
  } catch {
    // The env proxy rejects server-only keys in client-like runtimes; treat that as disabled.
    return false;
  }
};

/**
 * Internal params for execAgent with step lifecycle callbacks
 * This extends the public ExecAgentParams with server-side only options
 */
interface InternalExecAgentParams extends ExecAgentParams {
  /** Additional plugin IDs to inject (e.g., task tool during task execution) */
  additionalPluginIds?: string[];
  /** Bot context for topic metadata (platform, applicationId, platformThreadId) */
  botContext?: ChatTopicBotContext;
  /** Bot platform context for injecting platform capabilities (e.g. markdown support) */
  botPlatformContext?: BotPlatformContext;
  /** Cron job ID that triggered this execution (if trigger is 'cron') */
  cronJobId?: string;
  /** Disable only local-system while preserving other tools. Useful for signal-only evals. */
  disableLocalSystem?: boolean;
  /** Disable the self-iteration declaration tool for reviewer/runtime paths. */
  disableSelfFeedbackIntentTool?: boolean;
  /** Disable all tools (no plugins, no system manifests). Useful for eval/benchmark scenarios. */
  disableTools?: boolean;
  /** Discord context for injecting channel/guild info into agent system message */
  discordContext?: any;
  /** Eval context for injecting environment prompts into system message */
  evalContext?: EvalContext;
  /** External files to upload to S3 and attach to the user message */
  files?: Array<{
    /** Pre-downloaded buffer (from adapter/platform layer) */
    buffer?: Buffer;
    mimeType?: string;
    name?: string;
    size?: number;
    /** External URL — fetched if no buffer provided */
    url?: string;
  }>;
  /** Client-side function tools from Response API — injected into LLM with source='client' */
  functionTools?: Array<{ description?: string; name: string; parameters?: Record<string, any> }>;
  /** External lifecycle hooks (auto-adapt to local/production mode) */
  hooks?: AgentHook[];
  /** Initial step count offset for resumed operations (accumulated from previous runs) */
  initialStepCount?: number;
  /** Maximum steps for the agent operation */
  maxSteps?: number;
  /** Parent message ID to continue from. Only takes effect when resume is true */
  parentMessageId?: string;
  queueRetries?: number;
  queueRetryDelay?: string;
  /** Whether to continue execution from an existing persisted message */
  resume?: boolean;
  /**
   * When present, this execAgent call acts as the "continue" step for a
   * previous op that hit `human_approve_required`. The service writes the
   * decision to the target tool message and either runs the approved tool
   * (`approved`), halts with `reason='human_rejected'` (`rejected`), or
   * surfaces the rejection as user feedback so the LLM can respond
   * (`rejected_continue`). `parentMessageId` must point at the pending tool
   * message.
   */
  resumeApproval?: {
    decision: 'approved' | 'rejected' | 'rejected_continue';
    parentMessageId: string;
    rejectionReason?: string;
    toolCallId: string;
  };
  /** Abort startup before the agent runtime operation is created */
  signal?: AbortSignal;
  /**
   * Whether the LLM call should use streaming.
   * Defaults to true. Set to false for non-streaming scenarios (e.g., bot integrations).
   */
  stream?: boolean;
  /** Task ID that triggered this execution (if trigger is 'task') */
  taskId?: string;
  /**
   * Custom title for the topic.
   * When provided (including empty string), overrides the default prompt-based title.
   * When undefined, falls back to prompt.slice(0, 50).
   */
  title?: string;
  /** Topic creation trigger source ('cron' | 'chat' | 'api' | 'task') */
  trigger?: string;
  /**
   * User intervention configuration
   * Use { approvalMode: 'headless' } for async tasks that should never wait for human approval
   */
  userInterventionConfig?: UserInterventionConfig;
}

/**
 * AI Agent Service
 *
 * Encapsulates agent execution logic that can be triggered via:
 * - tRPC router (aiAgent.execAgent)
 * - REST API endpoint (/api/agent)
 * - Cron jobs / scheduled tasks
 */
export class AiAgentService {
  private readonly userId: string;
  private readonly db: LobeChatDatabase;
  private readonly agentDocumentsService: AgentDocumentsService;
  private readonly agentModel: AgentModel;
  private readonly agentService: AgentService;
  private readonly messageModel: MessageModel;
  private readonly pluginModel: PluginModel;
  private readonly taskModel: TaskModel;
  private readonly threadModel: ThreadModel;
  private readonly topicModel: TopicModel;
  private readonly agentRuntimeService: AgentRuntimeService;
  private readonly marketService: MarketService;
  private readonly klavisService: KlavisService;

  constructor(
    db: LobeChatDatabase,
    userId: string,
    options?: { runtimeOptions?: AgentRuntimeServiceOptions },
  ) {
    this.userId = userId;
    this.db = db;
    this.agentDocumentsService = new AgentDocumentsService(db, userId);
    this.agentModel = new AgentModel(db, userId);
    this.agentService = new AgentService(db, userId);
    this.messageModel = new MessageModel(db, userId);
    this.pluginModel = new PluginModel(db, userId);
    this.taskModel = new TaskModel(db, userId);
    this.threadModel = new ThreadModel(db, userId);
    this.topicModel = new TopicModel(db, userId);
    this.agentRuntimeService = new AgentRuntimeService(db, userId, {
      ...options?.runtimeOptions,
      execSubAgentTask: this.execSubAgentTask.bind(this),
    });
    this.marketService = new MarketService({ userInfo: { userId } });
    this.klavisService = new KlavisService({ db, userId });
  }

  private async resolveOperationTaskId(
    idOrIdentifier?: string | null,
  ): Promise<string | undefined> {
    if (!idOrIdentifier) return;

    // Task detail routes use human-readable identifiers such as `T-1`, while
    // operation runtimes store this value in FK-backed records.
    const task = await this.taskModel.resolve(idOrIdentifier);
    return task?.id;
  }

  /**
   * Execute agent with just a prompt
   *
   * This is a simplified API that requires agent identifier (id or slug) and prompt.
   * All necessary data (agent config, tools, messages) will be fetched from the database.
   *
   * Architecture:
   * execAgent({ agentId | slug, prompt })
   *   → AgentModel.getAgentConfig(idOrSlug)
   *   → ServerMechaModule.AgentToolsEngine(config)
   *   → ServerMechaModule.ContextEngineering(input, config, messages)
   *   → AgentRuntimeService.createOperation(...)
   */
  async execAgent(params: InternalExecAgentParams): Promise<ExecAgentResult> {
    const {
      additionalPluginIds,
      agentId,
      slug,
      prompt,
      appContext,
      autoStart = true,
      botContext,
      clientRuntime,
      deviceId: requestedDeviceId,
      botPlatformContext,
      discordContext,
      existingMessageIds = [],
      fileIds: attachedFileIds,
      files,
      functionTools,
      hooks,
      instructions,
      model: modelOverride,
      provider: providerOverride,
      stream,
      title,
      trigger,
      cronJobId,
      taskId,
      evalContext,
      maxSteps,
      disableLocalSystem,
      initialStepCount,
      signal,
      userInterventionConfig = { approvalMode: 'headless' },
      queueRetries,
      queueRetryDelay,
      parentMessageId,
      parentOperationId,
      resume,
      resumeApproval,
    } = params;

    // Validate that either agentId or slug is provided
    if (!agentId && !slug) {
      throw new Error('Either agentId or slug must be provided');
    }

    // Determine the identifier to use (agentId takes precedence)
    const identifier = agentId || slug!;

    log('execAgent: identifier=%s, prompt=%s', identifier, prompt.slice(0, 50));

    const operationTaskId = await this.resolveOperationTaskId(taskId ?? appContext?.taskId);

    const assistantMessageRef: { current?: string } = {};
    const updateAbortedAssistantMessage = async (errorMessage: string) => {
      if (!assistantMessageRef.current) return;

      try {
        await this.messageModel.update(assistantMessageRef.current, {
          content: '',
          error: {
            body: {
              detail: errorMessage,
            },
            message: errorMessage,
            type: 'ServerAgentRuntimeError',
          },
        });
      } catch (error) {
        log(
          'execAgent: failed to update aborted assistant message %s: %O',
          assistantMessageRef.current,
          error,
        );
      }
    };
    const throwIfExecutionAborted = async (stage: string) => {
      if (!signal?.aborted) return;

      const error = getAbortError(signal, `Agent execution aborted during ${stage}`);
      await updateAbortedAssistantMessage(error.message);
      throw error;
    };

    throwIfAborted(signal, 'Agent execution aborted before startup');

    // 1. Get agent configuration with default config merged (supports both id and slug)
    const agentConfig = await this.agentService.getAgentConfig(identifier);
    if (!agentConfig) {
      throw new Error(`Agent not found: ${identifier}`);
    }

    // Use actual agent ID from config for subsequent operations
    const resolvedAgentId = agentConfig.id;

    // Apply per-call model/provider overrides (e.g. from task.config)
    if (modelOverride) agentConfig.model = modelOverride;
    if (providerOverride) agentConfig.provider = providerOverride;

    log(
      'execAgent: got agent config for %s (id: %s), model: %s, provider: %s',
      identifier,
      resolvedAgentId,
      agentConfig.model,
      agentConfig.provider,
    );

    // 2. Merge builtin agent runtime config (systemRole, plugins)
    // The DB only stores persist config. Runtime config (e.g. inbox systemRole) is generated dynamically.
    const agentSlug = agentConfig.slug;
    const builtinSlugs = Object.values(BUILTIN_AGENT_SLUGS) as string[];
    if (agentSlug && builtinSlugs.includes(agentSlug)) {
      const runtimeConfig = getAgentRuntimeConfig(agentSlug, {
        model: agentConfig.model,
        plugins: agentConfig.plugins ?? [],
      });
      if (runtimeConfig) {
        // Runtime systemRole takes effect only if DB has no user-customized systemRole
        if (!agentConfig.systemRole && runtimeConfig.systemRole) {
          agentConfig.systemRole = runtimeConfig.systemRole;
          log('execAgent: merged builtin agent runtime systemRole for slug=%s', agentSlug);
        }
        // Runtime plugins merged (runtime plugins take priority if provided)
        if (runtimeConfig.plugins && runtimeConfig.plugins.length > 0) {
          agentConfig.plugins = runtimeConfig.plugins;
          log('execAgent: merged builtin agent runtime plugins for slug=%s', agentSlug);
        }
      }
    }

    if (appContext?.scope !== 'page') {
      agentConfig.plugins = agentConfig.plugins?.filter((id) => id !== PageAgentIdentifier);
    }

    if (appContext?.scope === 'page' && agentSlug !== BUILTIN_AGENT_SLUGS.pageAgent) {
      const pageAgentRuntime = getAgentRuntimeConfig(BUILTIN_AGENT_SLUGS.pageAgent, {
        model: agentConfig.model,
        plugins: agentConfig.plugins ?? [],
      });
      const pageAgentSystemRole = pageAgentRuntime?.systemRole || '';

      if (pageAgentSystemRole) {
        agentConfig.systemRole = agentConfig.systemRole
          ? `${agentConfig.systemRole}\n\n${pageAgentSystemRole}`
          : pageAgentSystemRole;
      }

      agentConfig.plugins = agentConfig.plugins?.includes(PageAgentIdentifier)
        ? agentConfig.plugins
        : [PageAgentIdentifier, ...(agentConfig.plugins ?? [])];
      agentConfig.chatConfig = {
        ...agentConfig.chatConfig,
        enableHistoryCount: false,
      };
      log('execAgent: injected page-agent runtime for page scope');
    }

    if (appContext?.scope === 'task' && agentSlug !== BUILTIN_AGENT_SLUGS.taskAgent) {
      const taskAgentRuntime = getAgentRuntimeConfig(BUILTIN_AGENT_SLUGS.taskAgent, {
        model: agentConfig.model,
        plugins: agentConfig.plugins ?? [],
      });
      const taskAgentSystemRole = taskAgentRuntime?.systemRole || '';

      if (taskAgentSystemRole) {
        agentConfig.systemRole = agentConfig.systemRole
          ? `${agentConfig.systemRole}\n\n${taskAgentSystemRole}`
          : taskAgentSystemRole;
      }

      agentConfig.plugins = agentConfig.plugins?.includes(TaskIdentifier)
        ? agentConfig.plugins
        : [TaskIdentifier, ...(agentConfig.plugins ?? [])];
      log('execAgent: injected task-agent runtime for task scope');
    }

    await throwIfExecutionAborted('agent configuration');

    // 2.5. Append additional instructions to agent's systemRole
    if (instructions) {
      agentConfig.systemRole = agentConfig.systemRole
        ? `${agentConfig.systemRole}\n\n${instructions}`
        : instructions;
      log('execAgent: appended additional instructions to systemRole');
    }

    let resumeParentMessage;

    // `resumeApproval` implies the same "load parent message + skip user
    // message creation" semantics as `resume`. Callers that go through the
    // tRPC router get `resume: true` via the router, but the service-level
    // API allows resumeApproval alone — fold both into a single effective
    // flag so downstream resume branches don't need to know about approval.
    const effectiveResume = resume || !!resumeApproval;

    if (effectiveResume) {
      if (!parentMessageId) {
        throw new Error('parentMessageId is required when resume is true');
      }

      if (!appContext) {
        throw new Error('appContext is required when resume is true');
      }

      if (!appContext.topicId) {
        throw new Error('appContext.topicId is required when resume is true');
      }

      resumeParentMessage = await this.messageModel.findById(parentMessageId);

      if (!resumeParentMessage) {
        throw new Error(`Parent message not found: ${parentMessageId}`);
      }

      if (resumeParentMessage.topicId !== appContext.topicId) {
        throw new Error('appContext.topicId does not match parent message');
      }

      if (
        resumeParentMessage.threadId &&
        resumeParentMessage.threadId !== (appContext.threadId ?? undefined)
      ) {
        throw new Error('appContext.threadId does not match parent message');
      }

      if (resumeParentMessage.sessionId && resumeParentMessage.sessionId !== appContext.sessionId) {
        throw new Error('appContext.sessionId does not match parent message');
      }
    }

    // 2.6. Human-approval resume: write the user's decision to the target tool
    // message in the DB so the history fetched below (step 11) + the runtime
    // state both reflect the decision before the first step runs. Validates
    // the parent is actually a pending tool message tied to the tool call we
    // were asked about — guards against stale / double-clicks.
    //
    // Note: `messages` and `message_plugins` live in separate tables. The
    // `messageModel.findById` query returns the `messages` row only — the
    // tool_call_id / apiName / identifier / arguments / type fields live on
    // the plugin row and must be fetched separately.
    let resumeApprovalPlugin: MessagePluginItem | undefined;

    if (resumeApproval) {
      if (!resumeParentMessage) {
        throw new Error('resumeApproval requires parentMessageId to point at a tool message');
      }
      if (resumeParentMessage.role !== 'tool') {
        throw new Error(
          `resumeApproval.parentMessageId must point at a role='tool' message, got role='${resumeParentMessage.role}'`,
        );
      }

      resumeApprovalPlugin = await this.messageModel.findMessagePlugin(
        resumeApproval.parentMessageId,
      );
      if (!resumeApprovalPlugin) {
        throw new Error(
          `resumeApproval: no plugin row for tool message ${resumeApproval.parentMessageId}`,
        );
      }
      if (
        resumeApprovalPlugin.toolCallId &&
        resumeApprovalPlugin.toolCallId !== resumeApproval.toolCallId
      ) {
        throw new Error(
          `resume
```
