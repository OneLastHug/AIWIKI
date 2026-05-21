# 文件：src/server/services/bot/BotMessageRouter.ts

## 文件职责
这个文件位于 `src/server/services/bot`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { createIoRedisState } from '@chat-adapter/state-ioredis';
import { DEFAULT_BOT_DEBOUNCE_MS } from '@lobechat/const';
import { Chat, ConsoleLogger, type Message, type MessageContext } from 'chat';
import debug from 'debug';
import { getServerDB } from '@/database/core/db-adaptor';
import type { DecryptedBotProvider } from '@/database/models/agentBotProvider';
import { AgentBotProviderModel } from '@/database/models/agentBotProvider';
import type { LobeChatDatabase } from '@/database/type';
import { appEnv } from '@/envs/app';
import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';
import { KeyVaultsGateKeeper } from '@/server/modules/KeyVaultsEncrypt';
import { emitAgentSignalSourceEvent } from '@/server/services/agentSignal';
import { AiAgentService } from '@/server/services/aiAgent';
import { AgentBridgeService } from './AgentBridgeService';
import { buildBotContext } from './buildBotContext';
import {
import {
import {
export class BotMessageRouter {
```

## 主要对外内容
```text
const log = debug('lobe-server:bot:message-router');
const summarizeMessageAttachments = (message: Message): Array<Record<string, unknown>> => {
interface ResolvedAgentInfo {
interface RegisteredBot {
interface CommandContext {
interface BotCommand {
export class BotMessageRouter {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { createIoRedisState } from '@chat-adapter/state-ioredis';
import { DEFAULT_BOT_DEBOUNCE_MS } from '@lobechat/const';
import { Chat, ConsoleLogger, type Message, type MessageContext } from 'chat';
import debug from 'debug';

import { getServerDB } from '@/database/core/db-adaptor';
import type { DecryptedBotProvider } from '@/database/models/agentBotProvider';
import { AgentBotProviderModel } from '@/database/models/agentBotProvider';
import type { LobeChatDatabase } from '@/database/type';
import { appEnv } from '@/envs/app';
import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';
import { KeyVaultsGateKeeper } from '@/server/modules/KeyVaultsEncrypt';
import { emitAgentSignalSourceEvent } from '@/server/services/agentSignal';
import { AiAgentService } from '@/server/services/aiAgent';

import { AgentBridgeService } from './AgentBridgeService';
import { buildBotContext } from './buildBotContext';
import {
  createOrGetPairingRequest,
  deletePairingRequest,
  peekPairingRequest,
  releasePairingClaim,
} from './dmPairingStore';
import {
  type BotPlatformRuntimeContext,
  type BotReplyLocale,
  buildRuntimeKey,
  type DmDecision,
  type DmSettings,
  extractDmSettings,
  extractGroupSettings,
  extractUserAllowlist,
  extractWatchKeywordEntries,
  findMatchingWatchKeywordEntries,
  getBotReplyLocale,
  type GroupSettings,
  messageMatchesWatchKeyword,
  normalizeAllowFromEntries,
  normalizeBotReplyLocale,
  type PlatformClient,
  type PlatformDefinition,
  platformRegistry,
  resolveBotProviderConfig,
  shouldAllowSender,
  shouldHandleDm,
  shouldHandleGroup,
  type UserAllowlist,
  type WatchKeywordEntry,
} from './platforms';
import {
  renderApproveSuccess,
  renderCommandReply,
  renderDmPairing,
  renderDmRejected,
  renderError,
  renderGroupRejected,
  renderInlineError,
  renderSenderRejected,
} from './replyTemplate';

const log = debug('lobe-server:bot:message-router');

/**
 * Compact summary of a Chat SDK Message's attachments for debug logging.
 * Lets us trace exactly what the platform adapter handed us at the point
 * where the bot router receives it (before merge / extractFiles run).
 */
const summarizeMessageAttachments = (message: Message): Array<Record<string, unknown>> => {
  const attachments = (message as any).attachments as
    | Array<{
        buffer?: Buffer;
        fetchData?: () => Promise<Buffer>;
        mimeType?: string;
        name?: string;
        size?: number;
        type?: string;
        url?: string;
      }>
    | undefined;
  if (!attachments?.length) return [];
  return attachments.map((att) => ({
    hasBuffer: !!att.buffer,
    hasFetchData: typeof att.fetchData === 'function',
    hasUrl: !!att.url,
    mimeType: att.mimeType,
    name: att.name,
    size: att.size,
    type: att.type,
  }));
};

interface ResolvedAgentInfo {
  agentId: string;
  userId: string;
}

interface RegisteredBot {
  agentInfo: ResolvedAgentInfo;
  chatBot: Chat<any>;
  client: PlatformClient;
}

/** Context passed to every command handler — a minimal surface shared by both
 *  native slash-command events and text-based message events. */
interface CommandContext {
  /** Text after the command name (e.g. "/new foo" → "foo"). */
  args: string;
  /** Platform user ID of the invoking user. Optional because the source
   *  event may not carry one (best-effort), but commands that gate on
   *  identity (e.g. `/approve` requires the owner) treat its absence as
   *  failure. */
  authorUserId?: string;
  /** Display name of the invoking user. Optional because some platforms
   *  surface only the ID, not a friendly label. */
  authorUserName?: string;
  post: (text: string) => Promise<any>;
  /** Locale to use for any system-generated reply text. Plumbed in by the
   *  caller — text-based commands derive it per-message via the platform's
   *  `extractAuthorLocale`, native slash commands fall back to the platform
   *  default since their event shape doesn't always carry user locale. */
  replyLocale: BotReplyLocale;
  setState: (state: Record<string, any>, opts?: { replace?: boolean }) => Promise<any>;
  threadId: string;
}

/** A single bot command definition.
 *  Add new entries to `buildCommands()` to register additional commands. */
interface BotCommand {
  description: string;
  handler: (ctx: CommandContext) => Promise<void>;
  name: string;
  /**
   * Native slash-command argument schema for platforms that require
   * arguments to be declared up-front (Discord, Slack). Without this,
   * Discord registers the command as zero-arg — clicking it from the
   * slash menu fires the handler with `ctx.args` empty even when the
   * user expected to pass a value. Adapters flatten option values back
   * into `event.text`, so the handler still reads `ctx.args` as before.
   *
   * Text-based platforms (Telegram / Feishu) ignore this and parse args
   * from the trailing message text via the dispatch regex.
   */
  options?: Array<{
    description: string;
    name: string;
    required?: boolean;
  }>;
}

/**
 * Routes incoming webhook events to the correct Chat SDK Bot instance
 * and triggers message processing via AgentBridgeService.
 *
 * All platforms require appId in the webhook URL:
 *   POST /api/agent/webhooks/[platform]/[appId]
 *
 * Bots are loaded on-demand: only the bot targeted by the incoming webhook
 * is created, not all bots across all platforms.
 */
export class BotMessageRouter {
  /** "platform:applicationId" → registered bot */
  private bots = new Map<string, RegisteredBot>();

  /** Per-key init promises to avoid duplicate concurrent loading */
  private loadingPromises = new Map<string, Promise<RegisteredBot | null>>();

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  /**
   * Get the webhook handler for a given platform + appId.
   * Returns a function compatible with Next.js Route Handler: `(req: Request) => Promise<Response>`
   */
  getWebhookHandler(platform: string, appId?: string): (req: Request) => Promise<Response> {
    return async (req: Request) => {
      const entry = platformRegistry.getPlatform(platform);
      if (!entry) {
        return new Response('No bot configured for this platform', { status: 404 });
      }

      if (!appId) {
        return new Response(`Missing appId for ${platform} webhook`, { status: 400 });
      }

      return this.handleWebhook(req, platform, appId);
    };
  }

  /**
   * Invalidate a cached bot so it gets reloaded with fresh config on next webhook.
   * Call this after settings or credentials are updated.
   */
  async invalidateBot(platform: string, appId: string): Promise<void> {
    const key = buildRuntimeKey(platform, appId);
    const existing = this.bots.get(key);
    if (!existing) return;

    log('invalidateBot: removing cached bot %s', key);
    this.bots.delete(key);
  }

  // ------------------------------------------------------------------
  // Webhook handling
  // ------------------------------------------------------------------

  private async handleWebhook(req: Request, platform: string, appId: string): Promise<Response> {
    log('handleWebhook: platform=%s, appId=%s', platform, appId);

    const bot = await this.getOrCreateBot(platform, appId);
    if (!bot) {
      return new Response(`No bot configured for ${platform}`, { status: 404 });
    }

    if (bot.chatBot.webhooks && platform in bot.chatBot.webhooks) {
      return (bot.chatBot.webhooks as any)[platform](req);
    }

    return new Response(`No bot configured for ${platform}`, { status: 404 });
  }

  // ------------------------------------------------------------------
  // On-demand bot loading
  // ------------------------------------------------------------------

  /**
   * Get an existing bot or create one on-demand from DB.
   * Concurrent calls for the same key are deduplicated.
   */
  private async getOrCreateBot(platform: string, appId: string): Promise<RegisteredBot | null> {
    const key = buildRuntimeKey(platform, appId);

    // Return cached bot
    const existing = this.bots.get(key);
    if (existing) return existing;

    // Deduplicate concurrent loads for the same key
    const inflight = this.loadingPromises.get(key);
    if (inflight) return inflight;

    const promise = this.loadBot(platform, appId);
    this.loadingPromises.set(key, promise);

    try {
      return await promise;
    } finally {
      this.loadingPromises.delete(key);
    }
  }

  private async loadBot(platform: string, appId: string): Promise<RegisteredBot | null> {
    const key = buildRuntimeKey(platform, appId);

    try {
      const entry = platformRegistry.getPlatform(platform);
      if (!entry) {
        log('No definition for platform: %s', platform);
        return null;
      }

      const serverDB = await getServerDB();
      const gateKeeper = await KeyVaultsGateKeeper.initWithEnvKey();

      // Find the specific provider — search across all users
      const providers = await AgentBotProviderModel.findEnabledByPlatform(
        serverDB,
        platform,
        gateKeeper,
      );
      const provider = providers.find((p) => p.applicationId === appId);

      if (!provider) {
        log('No enabled provider found for %s', key);
        return null;
      }

      const registered = await this.createAndRegisterBot(entry, provider, serverDB);
      log('Created %s bot on-demand for agent=%s, appId=%s', platform, provider.agentId, appId);
      return registered;
    } catch (error) {
      log('Failed to load bot %s: %O', key, error);
      return null;
    }
  }

  private async createAndRegisterBot(
    entry: PlatformDefinition,
    provider: DecryptedBotProvider,
    serverDB: LobeChatDatabase,
  ): Promise<RegisteredBot> {
    const { agentId, userId, applicationId } = provider;
    const platform = entry.id;
    const key = buildRuntimeKey(platform, applicationId);

    const { config: providerConfig, settings } = resolveBotProviderConfig(entry, provider);

    log(
      'createAndRegisterBot: %s settings merge: userSettings=%j, merged=%j',
      key,
      provider.settings,
      settings,
    );

    const runtimeContext: BotPlatformRuntimeContext = {
      appUrl: appEnv.APP_URL,
      redisClient: getAgentRuntimeRedisClient() as any,
    };

    const client = entry.clientFactory.createClient(providerConfig, runtimeContext);
    const adapters = client.createAdapter();

    // dmSettings + operatorUserId are needed by `/approve` (to enforce the
    // owner-only gate and to know whether pairing is even enabled), and by
    // the DM pairing branch in registerHandlers. Extract once, share with
    // both — registerHandlers re-derives from `settings` to keep its own
    // closure-internal contract self-contained.
    const dmSettings: DmSettings = extractDmSettings(settings);
    const operatorUserId =
      typeof settings.userId === 'string'
        ? (settings.userId as string).trim() || undefined
        : undefined;

    const commands = this.buildCommands(serverDB, {
      agentId,
      applicationId,
      client,
      dmSettings,
      operatorUserId,
      platform,
      providerId: provider.id,
      userId,
    });

    // Default to 'queue' for legacy providers that don't have `concurrency`
    // in their saved settings. Historically this defaulted to 'debounce', but
    // chat-sdk's debounce semantics are "drop all but the latest" (Lodash-style),
    // which silently evicts media messages when followed by a quick text query.
    // 'queue' preserves all pending messages and merges them via
    // `mergeSkippedMessages`, which is the right default for chat UX.
    const concurrencyStrategy = (settings.concurrency as string) || 'queue';
    const debounceMs = (settings.debounceMs as number) || DEFAULT_BOT_DEBOUNCE_MS;
    const chatBot = this.createChatBot(
      adapters,
      `agent-${agentId}`,
      concurrencyStrategy,
      debounceMs,
    );
    this.registerHandlers(chatBot, serverDB, client, commands, {
      agentId,
      applicationId,
      platform,
      settings,
      userId,
    });
    await chatBot.initialize();
    client.applyChatPatches?.(chatBot);

    // Register platform-specific bot commands (e.g., Telegram setMyCommands menu)
    if (client.registerBotCommands) {
      const commandList = commands.map((c) => ({
        command: c.name,
        description: c.description,
        options: c.options,
      }));
      client.registerBotCommands(commandList).catch((error) => {
        log('registerBotCommands failed for %s: %O', key, error);
      });
    }

    const registered: RegisteredBot = {
      agentInfo: { agentId, userId },
      chatBot,
      client,
    };

    this.bots.set(key, registered);

    return registered;
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  /**
   * A proxy around the shared Redis client that suppresses duplicate `on('error', ...)`
   * registrations. Each `createIoRedisState()` call adds an error listener to the client;
   * with many bot instances sharing one client this would trigger
   * MaxListenersExceededWarning. The proxy lets the first error listener through and
   * silently drops subsequent ones, so it scales to any number of bots.
   */
  private sharedRedisProxy: ReturnType<typeof getAgentRuntimeRedisClient> | undefined;

  private getSharedRedisProxy() {
    if (this.sharedRedisProxy !== undefined) return this.sharedRedisProxy;

    const redisClient = getAgentRuntimeRedisClient();
    if (!redisClient) {
      this.sharedRedisProxy = null;
      return null;
    }

    let errorListenerRegistered = false;
    this.sharedRedisProxy = new Proxy(redisClient, {
      get(target, prop, receiver) {
        if (prop === 'on') {
          return (event: string, listener: (...args: any[]) => void) => {
            if (event === 'error') {
              if (errorListenerRegistered) return target;
              errorListenerRegistered = true;
            }
            return target.on(event, listener);
          };
        }
        return Reflect.get(target, prop, receiver);
      },
    });

    return this.sharedRedisProxy;
  }

  private createChatBot(
    adapters: Record<string, any>,
    label: string,
    concurrencyStrategy: string,
    debounceMs: number,
  ): Chat<any> {
    const config: any = {
      adapters,
      concurrency:
        concurrencyStrategy === 'debounce' ? { debounceMs, strategy: 'debounce' } : 'queue',
      userName: `lobehub-bot-${label}`,
    };

    const redisClient = getAgentRuntimeRedisClient();
    if (redisClient) {
      config.state = createIoRedisState({
        client: redisClient,
        keyPrefix: `chat-sdk:${label}`,
        logger: new ConsoleLogger(),
      });
    }

    return new Chat(config);
  }

  /**
   * Merge messages skipped by the Chat SDK concurrency strategy (debounce/queue)
   * with the current message. Returns a single message with combined text and
   * attachments so the agent sees the full user intent.
   */
  private static mergeSkippedMessages(
    message: Message,
    context?: { skipped?: Message[] },
  ): Message {
    if (!context?.skipped?.length) return message;

    // context.skipped is chronological; current message is the latest
    const allMessages = [...context.skipped, message];
    const mergedText = allMessages
      .map((m) => m.text)
      .filter(Boolean)
      .join('\n');
    const mergedAttachments = allMessages.flatMap((m) => (m as any).attachments || []);

    return Object.assign(Object.create(Object.getPrototypeOf(message)), message, {
      attachments: mergedAttachments,
      text: mergedText,
    });
  }

  /**
   * Prepend the operator-authored `instruction` of every matched watch
   * keyword to the merged user message. Used on the keyword-wake paths
   * (subscribed-thread `onSubscribedMessage` and the channel catch-all)
   * so a bare trigger like "bug" can carry a directive into the agent
   * call without an explicit mention.
   *
   * Duplicated instructions are de-duplicated (operators routinely paste
   * the same directive under several keywords like "bug" / "outage").
   * If no matched entry has an instruction, the original `merged` is
   * returned unchanged so the caller doesn't need to branch.
   */
  private static applyWatchKeywordInstructions(
    merged: Message,
    entries: ReadonlyArray<WatchKeywordEntry>,
  ): { instructionCount: number; merged: Message; prefixLength: number } {
    const matched = findMatchingWatchKeywordEntries(merged.text, entries);
    const instructions = Array.from(
      new Set(
        matched
          .map((entry) => entry.instruction?.trim())
          .filter((value): value is string => !!value),
      ),
    );
    if (instructions.length === 0) {
      return { instructionCount: 0, merged, prefixLength: 0 };
    }
    const prefix = instructions.join('\n\n');
    const originalText = merged.text ?? '';
    const augmentedText = originalText ? `${prefix}\n\n${originalText}` : prefix;
    const next = Object.assign(Object.create(Object.getPrototypeOf(merged)), merged, {
      text: augmentedText,
    }) as Message;
    return { instructionCount: instructions.length, merged: next, prefixLength: prefix.length };
  }

  private registerHandlers(
    bot: Chat<any>,
    serverDB: LobeChatDatabase,
    client: PlatformClient,
    commands: BotCommand[],
    info: ResolvedAgentInfo & {
      applicationId: string;
      platform: string;
      settings?: Record<string, any>;
    },
  ): void {
    const { agentId, applicationId, platform, userId } = info;
    const bridge = new AgentBridgeService(serverDB, userId);
    const charLimit = (info.settings?.charLimit as number) || undefined;
    const displayToolCalls = info.settings?.displayToolCalls === true;
    const dmSettings: DmSettings = extractDmSettings(info.settings);
    const groupSettings: GroupSettings = extractGroupSettings(info.settings);
    const userAllowlist: UserAllowlist = extractUserAllowlist(info.settings);
    /**
     * Operator-configured keywords (LOBE-8891). When non-empty, a non-@mention
     * non-command message in a subscribed group thread still wakes the bot if
     * its text contains any keyword — case-insensitive, word-boundary aware
     * (see `messageMatchesWatchKeyword`). Empty list keeps the legacy
     * mention-only behaviour exactly. DMs and explicit mentions are unaffected;
     * keyword matching only relaxes the gate in subscribed group threads.
     *
     * `watchKeywordEntries` carries the operator-authored `instruction` for
     * each keyword. When a keyword (and not a mention) is what wakes the
     * bot, the matched entries' instructions are prepended to the user
     * message as a prompt prefix before dispatch — so a bare trigger word
     * can drive a specific directive ("scan the recent thread for a bug
     * report", "summarise the last 20 messages", …).
     */
    const watchKeywordEntries = extractWatchKeywordEntries(info.settings);
    const watchKeywords: ReadonlyArray<string> = watchKeywordEntries.map((e) => e.keyword);
    /**
     * The provider's owner platform user ID. Only consulted under the
     * `pairing` policy, where the gate gives the owner a free pass so they
     * can DM their own bot before any approvals exist (otherwise the
     * shouldHandleDm gate would tell the owner to ask themselves to
     * approve via `/approve`).
     */
    const operatorUserId =
      typeof info.settings?.userId === 'string'
        ? (info.settings.userId as string).trim() || undefined
        : undefined;
    const fallbackReplyLocale: BotReplyLocale = getBotReplyLocale(platform);

    /**
     * Resolve the reply locale for a single inbound event. Prefer the
     * sender's platform-reported locale (e.g. Telegram's
     * `from.language_code`) so a Brazilian Telegram user sees Portuguese,
     * even though Telegram's channel-level default is English. Fall back to
     * the platform default when the platform doesn't expose a locale or the
     * value is empty.
     */
    const detectReplyLocale = (message: { author?: unknown }): BotReplyLocale => {
      const detected = normalizeBotReplyLocale(client.extractAuthorLocale?.(message as any));
      return detected ?? fallbackReplyLocale;
    };

    /**
     * Global user-level gate. Applied **before** any per-scope policy so a
     * populated `allowFrom` restricts every inbound surface (DMs, group
     * @mentions, threads) to listed users. Empty list = no filter.
     */
    const passesGlobalAllowlist = (message: { author?: { userId?: string } }): boolean =>
      shouldAllowSender({
        authorUserId: message.author?.userId,
        userAllowlist,
      });

    /**
     * Gate inbound events on DM policy. Non-DM threads pass through — their
     * group-policy / @mention rules apply instead. The `'pair'` decision
     * is distinct from `'reject'` because the router branches on it (issue
     * a pairing code) — see `passGatesOrNotify` below.
     */
    const passesDmPolicy = (
      thread: { isDM?: boolean },
      message: { author?: { userId?: string } },
    ): DmDecision =>
      shouldHandleDm({
        authorUserId: message.author?.userId,
        dmSettings,
        isDM: thread.isDM === true,
        operatorUserId,
        userAllowlist,
      });

    /**
     * Gate inbound events on group policy. DM threads pass through — they
     * are governed by `passesDmPolicy` instead. Non-DM threads are blocked
     * when disabled, and filtered against `groupAllowFrom` (channel / group
     * / chat IDs) when set to `allowlist`.
     *
     * Operators paste **raw** platform IDs (what Discord's "Copy Channel
     * ID" or Telegram's chat-id tools yield), but `thread.channelId` is a
     * *composi
```
