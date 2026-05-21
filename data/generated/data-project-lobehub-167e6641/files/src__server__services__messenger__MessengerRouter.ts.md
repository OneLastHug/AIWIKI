# 文件：src/server/services/messenger/MessengerRouter.ts

## 文件职责
这个文件位于 `src/server/services/messenger`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { createIoRedisState } from '@chat-adapter/state-ioredis';
import { INBOX_SESSION_ID } from '@lobechat/const';
import {
import debug from 'debug';
import { and, desc, eq, ne, or } from 'drizzle-orm';
import type { MessengerPlatform } from '@/config/messenger';
import { getServerDB } from '@/database/core/db-adaptor';
import { MessengerAccountLinkModel } from '@/database/models/messengerAccountLink';
import type { MessengerAccountLinkItem } from '@/database/schemas';
import { agents } from '@/database/schemas';
import type { LobeChatDatabase } from '@/database/type';
import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';
import { AiAgentService } from '@/server/services/aiAgent';
import { AgentBridgeService } from '@/server/services/bot/AgentBridgeService';
import { buildBotContext } from '@/server/services/bot/buildBotContext';
import type { PlatformClient } from '@/server/services/bot/platforms';
import { renderInlineError } from '@/server/services/bot/replyTemplate';
import { getInstallationStore } from './installations';
import type { InstallationCredentials } from './installations/types';
import { messengerPlatformRegistry } from './platforms';
import type { AgentPickerEntry, InboundCallbackAction, MessengerPlatformBinder } from './types';
export class MessengerRouter {
```

## 主要对外内容
```text
const log = debug('lobe-server:messenger:router');
interface RegisteredMessengerBot {
interface CommandMatch {
interface AgentSummary {
interface MessengerCommandContext {
interface MessengerCommand {
const HELP_TEXT = [
const extractDiscordInteractionContext = (
const parseCommand = (text: string | undefined): CommandMatch | null => {
const reconstructRequest = (req: Request, rawBody: string): Request =>
export class MessengerRouter {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { createIoRedisState } from '@chat-adapter/state-ioredis';
import { INBOX_SESSION_ID } from '@lobechat/const';
import {
  Chat,
  ConsoleLogger,
  type Message,
  type MessageContext,
  type SlashCommandEvent,
} from 'chat';
import debug from 'debug';
import { and, desc, eq, ne, or } from 'drizzle-orm';

import type { MessengerPlatform } from '@/config/messenger';
import { getServerDB } from '@/database/core/db-adaptor';
import { MessengerAccountLinkModel } from '@/database/models/messengerAccountLink';
import type { MessengerAccountLinkItem } from '@/database/schemas';
import { agents } from '@/database/schemas';
import type { LobeChatDatabase } from '@/database/type';
import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';
import { AiAgentService } from '@/server/services/aiAgent';
import { AgentBridgeService } from '@/server/services/bot/AgentBridgeService';
import { buildBotContext } from '@/server/services/bot/buildBotContext';
import type { PlatformClient } from '@/server/services/bot/platforms';
import { renderInlineError } from '@/server/services/bot/replyTemplate';

import { getInstallationStore } from './installations';
import type { InstallationCredentials } from './installations/types';
import { messengerPlatformRegistry } from './platforms';
import type { AgentPickerEntry, InboundCallbackAction, MessengerPlatformBinder } from './types';

const log = debug('lobe-server:messenger:router');

interface RegisteredMessengerBot {
  binder: MessengerPlatformBinder;
  chatBot: Chat<any>;
  client: PlatformClient;
  /** Cached resolved credentials — null for global-bot platforms (Telegram). */
  creds: InstallationCredentials;
}

interface CommandMatch {
  args: string;
  name: string;
}

interface AgentSummary {
  id: string;
  title: string;
}

/**
 * Per-message context passed to every command handler. Mirrors
 * `BotMessageRouter`'s `CommandContext`: handlers stay platform-agnostic and
 * read whatever they need (`thread`, `link`, `binder`, …) off the context
 * rather than threading parameters through every entry point.
 *
 * `source` discriminates the dispatch path: `'text'` carries a chat-sdk
 * `thread` + `message` (commands like `/new` and `/stop` use these to drive
 * the runtime); `'slash'` is a native slash-command event without a thread.
 */
interface MessengerCommandContext {
  args: string;
  authorUserId: string;
  authorUserName?: string;
  binder: MessengerPlatformBinder;
  /** Conversation id for outbound replies. For slash invocations from a
   *  public channel this is the slash-invocation channel; for text it's the
   *  DM thread. */
  chatId: string;
  /** Discord slash command interaction handle. Present only when dispatched
   *  by `handleSlashCommand` on Discord — handlers that emit interactive UI
   *  (e.g. `/agents` picker) must complete the deferred interaction via the
   *  follow-up webhook, otherwise Discord shows "Thinking..." indefinitely
   *  and eventually flips to "The application did not respond". */
  interaction?: { applicationId: string; token: string };
  /** True when the command was invoked from a 1:1 DM. Commands that surface
   *  user-private UI (e.g. `/agents` picker) widen private replies into
   *  ephemerals when this is false so the channel doesn't see them. */
  isDM: boolean;
  link: MessengerAccountLinkItem | undefined;
  message?: Message;
  platform: MessengerPlatform;
  /** Platform-aware reply: ephemeral on Slack slash, DM on Discord slash,
   *  `binder.sendDmText` on text dispatch. */
  reply: (text: string) => Promise<void>;
  serverDB: LobeChatDatabase;
  source: 'text' | 'slash';
  tenantId: string;
  thread?: any;
}

interface MessengerCommand {
  description: string;
  handler: (ctx: MessengerCommandContext) => Promise<void>;
  name: string;
}

const HELP_TEXT = [
  'Commands:',
  '• /start — bind (or rebind) your LobeHub account',
  '• /agents — list your agents and switch the active one',
  '• /new — start a new conversation',
  '• /stop — stop the current execution',
].join('\n');

/**
 * Pull the Discord interaction id + token off a chat-sdk slash event so
 * handlers can complete the deferred interaction via the follow-up webhook.
 *
 * chat-adapter-discord exposes the raw Discord interaction object on
 * `event.raw` (see `chat` SlashCommandEvent: "Platform-specific raw payload"),
 * which carries `application_id` and `token`. Returns undefined for other
 * platforms or when the shape doesn't match (defensive — the patch only
 * fires for Discord today).
 */
const extractDiscordInteractionContext = (
  platform: MessengerPlatform,
  event: SlashCommandEvent,
): { applicationId: string; token: string } | undefined => {
  if (platform !== 'discord') return undefined;
  const raw = event.raw as { application_id?: unknown; token?: unknown } | null | undefined;
  if (!raw || typeof raw !== 'object') return undefined;
  if (typeof raw.application_id !== 'string' || typeof raw.token !== 'string') {
    return undefined;
  }
  return { applicationId: raw.application_id, token: raw.token };
};

/** Parse a leading `/cmd` (with optional args) out of a message. Returns null
 *  when the message isn't a command. Strips a trailing `@BotName` so commands
 *  invoked from group chats also match (Telegram appends the bot username). */
const parseCommand = (text: string | undefined): CommandMatch | null => {
  if (!text) return null;
  const trimmed = text.trim();
  if (!trimmed.startsWith('/')) return null;
  const match = trimmed.match(/^\/([a-z][\w-]*)(?:@\S+)?(?:\s(.*))?$/is);
  if (!match) return null;
  return { args: (match[2] ?? '').trim(), name: match[1].toLowerCase() };
};

/**
 * Re-pack a request body that was already drained by `req.text()` so we can
 * pass it on to chat-sdk / the binder. Original headers + URL preserved.
 */
const reconstructRequest = (req: Request, rawBody: string): Request =>
  new Request(req.url, {
    body: rawBody,
    // `Request.duplex` is required when supplying a body to `new Request` in
    // some runtimes; cast to avoid TS narrowing differences across DOM lib
    // versions.
    headers: req.headers,
    method: req.method,
  } as RequestInit);

/**
 * Routes inbound messages from the shared Messenger bots to the right
 * LobeHub user + agent.
 *
 * **Multi-tenant routing (PR2)**: per-tenant platforms (Slack today) keep
 * one Chat SDK instance per `installationKey` (e.g. `slack:T0123`). Global-
 * bot platforms (Telegram, future Discord) collapse to a single bot per
 * platform via the special `telegram:singleton` key.
 *
 * Account model: each `(LobeHub user, platform, tenant_id)` triple has at
 * most one row in `messenger_account_links`, so a single LobeHub user can
 * link into multiple Slack workspaces simultaneously without collisions.
 *
 * **Platform abstraction**: command logic and tap-action handling live in a
 * single platform-agnostic registry. Per-platform differences (private
 * interaction reply mechanism, webhook-time vs chat-sdk-delivered actions)
 * are hidden behind optional `MessengerPlatformBinder` fields
 * (`replyPrivately`, `extractActionFromEvent`, `acknowledgeCallback`).
 * Adding a new platform is a binder-only change — the router does not
 * branch on `platform === 'foo'`.
 */
export class MessengerRouter {
  private bots = new Map<string, RegisteredMessengerBot>();
  private loadingPromises = new Map<string, Promise<RegisteredMessengerBot | null>>();

  /** Static command registry — reused across every install since command
   *  logic is platform-agnostic. Handlers reach platform-specific reply
   *  surfaces through `ctx.reply` and `ctx.binder`. */
  private readonly commands: MessengerCommand[] = this.buildCommands();

  /**
   * Webhook handler for `/api/agent/messenger/webhooks/[platform]`. The flow:
   *
   *   1. Read the raw body (must happen before any parsing — Slack's signature
   *      is over the exact bytes Slack sent)
   *   2. Slack: verify the signing secret, short-circuit `url_verification`
   *      and `app_uninstalled` / `tokens_revoked`
   *   3. Resolve the install via the platform's `MessengerInstallationStore`
   *      (Slack: DB lookup by `team_id` / `enterprise_id`; Telegram: env
   *      singleton)
   *   4. Lazy-load (and cache) a Chat SDK bot for that install
   *   5. Run `binder.extractCallbackAction` to intercept tap-action callbacks
   *      that chat-sdk doesn't surface
   *   6. Otherwise hand the (reconstructed) request to chat-sdk's webhook handler
   */
  getWebhookHandler(platform: string): (req: Request) => Promise<Response> {
    return async (req: Request) => {
      const definition = messengerPlatformRegistry.getPlatform(platform);
      if (!definition) {
        return new Response(`Unknown messenger platform: ${platform}`, { status: 404 });
      }

      const rawBody = await req.text();

      // ----- Per-platform gate (signature verification, setup challenges,
      //       lifecycle events). Returning a Response short-circuits the
      //       shared flow; null means continue.
      if (definition.webhookGate) {
        const early = await definition.webhookGate.preprocess(req, rawBody, {
          invalidateBot: (key) => this.bots.delete(key),
        });
        if (early) return early;
      }

      // ----- Resolve install + lazy-load bot -------------------------------
      const store = getInstallationStore(definition.id);
      if (!store) {
        return new Response(`Messenger ${platform} has no installation store`, { status: 500 });
      }

      const creds = await store.resolveByPayload(reconstructRequest(req, rawBody), rawBody);
      if (!creds) {
        log('webhook: no install resolved for platform=%s', platform);
        return new Response('install not found', { status: 404 });
      }

      const bot = await this.getOrCreateBot(creds);
      if (!bot) {
        return new Response(`Messenger ${platform} bot unavailable`, { status: 503 });
      }

      // ----- App Home `Messages` tab opener (Slack marketplace welcome) ---
      // Slack requires a welcome message the first time a user opens the
      // Messages tab. chat-sdk's slack adapter drops these events, so peek
      // the raw body here and dispatch via the binder. Dedupe is handled
      // inside `handleAppHomeOpened` so a per-user welcome fires once.
      if (bot.binder.extractAppHomeOpened) {
        try {
          const opener = await bot.binder.extractAppHomeOpened(reconstructRequest(req, rawBody));
          if (opener) {
            await this.handleAppHomeOpened(bot, creds, opener);
            return new Response('OK', { status: 200 });
          }
        } catch (error) {
          log('extractAppHomeOpened failed for %s: %O', platform, error);
        }
      }

      // ----- Tap-action callbacks (binder peeks raw body) -----------------
      if (bot.binder.extractCallbackAction) {
        try {
          const action = await bot.binder.extractCallbackAction(reconstructRequest(req, rawBody));
          if (action) {
            await this.handleCallbackAction(bot.binder, creds, action);
            return new Response('OK', { status: 200 });
          }
        } catch (error) {
          log('extractCallbackAction failed for %s: %O', platform, error);
        }
      }

      // ----- Normal message → chat-sdk handler ----------------------------
      const handler = (bot.chatBot.webhooks as any)?.[platform];
      if (!handler) {
        return new Response(`Messenger ${platform} webhook unavailable`, { status: 500 });
      }
      return handler(reconstructRequest(req, rawBody));
    };
  }

  // -------------------------------------------------------------------------

  private async getOrCreateBot(
    creds: InstallationCredentials,
  ): Promise<RegisteredMessengerBot | null> {
    const key = creds.installationKey;
    const existing = this.bots.get(key);
    if (existing) return existing;

    const inflight = this.loadingPromises.get(key);
    if (inflight) return inflight;

    const promise = this.loadBot(creds);
    this.loadingPromises.set(key, promise);

    try {
      return await promise;
    } finally {
      this.loadingPromises.delete(key);
    }
  }

  private async loadBot(creds: InstallationCredentials): Promise<RegisteredMessengerBot | null> {
    const binder = messengerPlatformRegistry.createBinder(creds);
    if (!binder) {
      log('loadBot: no binder available for %s', creds.installationKey);
      return null;
    }

    const client = await binder.createClient();
    if (!client) {
      log('loadBot: binder %s returned no client', creds.installationKey);
      return null;
    }

    const adapters = client.createAdapter();
    const chatBot = this.createChatBot(adapters, creds);

    // Apply platform-specific chat-sdk patches (Discord forwarded interaction
    // ack, Discord thread recovery, etc.) so the messenger Chat handles
    // gateway-forwarded events the same way the per-agent BotMessageRouter does.
    client.applyChatPatches?.(chatBot);

    const serverDB = await getServerDB();
    this.registerHandlers(chatBot, serverDB, client, binder, creds);

    await chatBot.initialize();

    if (client.registerBotCommands) {
      client
        .registerBotCommands(
          this.commands.map((cmd) => ({ command: cmd.name, description: cmd.description })),
        )
        .catch((error) =>
          log('registerBotCommands failed for %s: %O', creds.installationKey, error),
        );
    }

    const registered: RegisteredMessengerBot = { binder, chatBot, client, creds };
    this.bots.set(creds.installationKey, registered);

    log('loadBot: registered messenger %s bot', creds.installationKey);
    return registered;
  }

  private createChatBot(adapters: Record<string, any>, creds: InstallationCredentials): Chat<any> {
    const config: any = {
      adapters,
      concurrency: 'queue',
      // Per-install Chat SDK identity so the queue / state / debounce keys
      // never overlap across workspaces.
      userName: `messenger-bot-${creds.installationKey}`,
    };

    const redisClient = getAgentRuntimeRedisClient();
    if (redisClient) {
      config.state = createIoRedisState({
        client: redisClient,
        // Per-install key prefix → Redis state isolation per workspace.
        keyPrefix: `chat-sdk:messenger-${creds.installationKey}`,
        logger: new ConsoleLogger(),
      });
    }

    return new Chat(config);
  }

  private registerHandlers(
    bot: Chat<any>,
    serverDB: LobeChatDatabase,
    client: PlatformClient,
    binder: MessengerPlatformBinder,
    creds: InstallationCredentials,
  ): void {
    const platform = creds.platform;
    const tenantId = creds.tenantId;

    const handle = async (
      thread: any,
      message: Message,
      bridgeMethod: 'handleMention' | 'handleSubscribedMessage',
    ): Promise<void> => {
      if (message.author.isBot === true) return;

      const senderId = message.author.userId;
      if (!senderId) {
        log('handle: missing author.userId, dropping');
        return;
      }

      const chatId = client.extractChatId(thread.id);
      // Channel `@mention` (Slack today) — `thread.isDM` is false. The
      // unlinked path swaps to an ephemeral so the link prompt is visible
      // only to the mentioner; the no-active-agent prompt is also routed
      // ephemerally for the same reason. The chat-sdk thread.id carries
      // the platform's thread anchor (Slack: `slack:<channel>:<threadTs>`)
      // which the binder splits when posting in-thread.
      const isChannelMention = thread.isDM === false;
      const link = await MessengerAccountLinkModel.findByPlatformUser(
        serverDB,
        platform,
        senderId,
        tenantId,
      );

      try {
        const parsed = parseCommand(message.text);
        if (parsed) {
          const command = this.commands.find((c) => c.name === parsed.name);
          if (command) {
            // Text-path command reply: in a DM `chat.postMessage` is fine
            // (the conversation is private already). In a channel `@mention`
            // we must NOT broadcast — `/new`, `/stop`, `/start` etc. all
            // surface user-private state. Route the reply through
            // `replyEphemeral` so only the invoker sees it. Anchor in the
            // mention's thread (Slack `thread_ts`) so the response sits next
            // to the trigger. Platforms without `replyEphemeral` (Telegram)
            // fall back to the regular DM path.
            const channelThreadTs = isChannelMention ? String(thread.id).split(':')[2] : undefined;
            const reply =
              isChannelMention && binder.replyEphemeral
                ? (text: string) =>
                    binder.replyEphemeral!({
                      channelId: chatId,
                      text,
                      threadTs: channelThreadTs,
                      userId: senderId,
                    })
                : (text: string) => binder.sendDmText(chatId, text);
            await command.handler({
              args: parsed.args,
              authorUserId: senderId,
              authorUserName: message.author.userName,
              binder,
              chatId,
              isDM: !isChannelMention,
              link,
              message,
              platform,
              reply,
              serverDB,
              source: 'text',
              tenantId,
              thread,
            });
            return;
          }
          // Unknown slash text — pass through to the agent so legitimate
          // "/foo" prompts the user typed still reach them.
        }

        // Unbound sender → trigger link flow. For a channel mention pass
        // the raw thread.id so the binder can post the prompt as an
        // ephemeral anchored in the mention's thread instead of a public
        // DM-style message.
        if (!link) {
          await binder.handleUnlinkedMessage({
            authorUserId: senderId,
            authorUserName: message.author.userName,
            channelMentionThreadId: isChannelMention ? thread.id : undefined,
            chatId,
            message,
          });
          return;
        }

        // Bound but no active agent → prompt the user to pick one via /agents.
        // In a channel, route the prompt ephemerally so the entire channel
        // doesn't see the system message.
        if (!link.activeAgentId) {
          const noAgentText = 'No active agent selected. Send /agents to pick one.';
          if (isChannelMention && binder.replyEphemeral) {
            const threadTs = String(thread.id).split(':')[2];
            await binder.replyEphemeral({
              channelId: chatId,
              text: noAgentText,
              threadTs,
              userId: senderId,
            });
          } else {
            await binder.sendDmText(chatId, noAgentText);
          }
          return;
        }

        await this.dispatchToAgent(
          thread,
          message,
          client,
          link,
          link.activeAgentId,
          platform,
          bridgeMethod,
        );
      } catch (error) {
        log('handle: handler error: %O', error);
        try {
          await thread.post(renderInlineError('Something went wrong'));
        } catch {
          /* ignore */
        }
      }
    };

    // We intentionally do NOT register `onDirectMessage`. Chat SDK
    // short-circuits the DM dispatch when that handler is registered
    // (`chat` core: `dispatchToHandlers` fires DM handlers and returns
    // before the `isSubscribed` check), which kills the subscription-based
    // routing that lets follow-up messages reuse the cached topicId.
    //
    // Without an `onDirectMessage` handler, chat-sdk forces `isMention =
    // true` for DMs and falls through to the standard subscription dispatch
    // (mirrors `BotMessageRouter`, which doesn't register `onDirectMessage`
    // either):
    //   - First DM → not subscribed yet → `onNewMention` →
    //     `handleMention` opens a topic and subscribes the thread.
    //   - Follow-up DM → subscribed → `onSubscribedMessage` →
    //     `handleSubscribedMessage` reads the cached topicId and continues.
    //
    // Track distinct humans who have spoken in a channel thread. A
    // single-user thread is effectively a private 1:1 with the bot (just
    // hosted in a channel), so we relax the @mention requirement and let
    // every follow-up reach the agent. Once a second human joins we revert
    // to mention-only mode and announce the switch once so newcomers
    // understand why follow-ups are suddenly silent.
    //
    // Tracking lives in chat-sdk state so the count survives webhook
    // boundaries (each Slack event delivery is a fresh request). DMs and
    // bot authors are excluded — DMs are already 1:1 and bots can't drive
    // a conversation.
    const PARTICIPANTS_TTL_MS = 7 * 24 * 60 * 60 * 1000;
    const participantsKey = (threadId: string): string => `messenger:thread-humans:${threadId}`;
    const mentionRequiredAnnouncedKey = (threadId: string): string =>
      `messenger:thread-mention-required-announced:${threadId}`;

    const trackThreadParticipant = async (
      thread: any,
      message: Message,
    ): Promise<{ count: number; isNewParticipant: boolean }> => {
      if (thread.isDM) return { count: 0, isNewParticipant: false };
      const senderId = message.author?.userId;
      const isHuman =
        !!senderId &&
        message.author?.isBot !== true &&
        (message.author as { isMe?: boolean })?.isMe !== true;
      if (!isHuman) return { count: 0, isNewParticipant: false };

      const stateAdapter = bot.getState();
      const key = participantsKey(thread.id);
      let participants: string[] = [];
      try {
        participants = (await stateAdapter.getList<string>(key)) ?? [];
      } catch (error) {
        log('
```
