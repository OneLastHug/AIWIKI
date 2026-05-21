# 文件：src/server/services/messenger/linkTokenStore.ts

## 文件职责
这个文件位于 `src/server/services/messenger`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { randomUUID } from 'node:crypto';
import debug from 'debug';
import { getMessengerLinkTokenTtl, type MessengerPlatform } from '@/config/messenger';
import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';
export type LinkToken = string;
export interface LinkTokenPayload {
export interface ConsumedLinkTokenMarker {
export const issueLinkToken = async (
export const peekLinkToken = async (token: LinkToken): Promise<LinkTokenPayload | null> => {
export const consumeLinkToken = async (token: LinkToken): Promise<LinkTokenPayload | null> => {
export const peekConsumedLinkToken = async (
```

## 主要对外内容
```text
const log = debug('lobe-server:messenger:link-token');
export type LinkToken = string;
export interface LinkTokenPayload {
const tokenKey = (token: LinkToken): string => `messenger:link-token:${token}`;
const reuseKey = (platform: MessengerPlatform, platformUserId: string): string =>
const consumedKey = (token: LinkToken): string => `messenger:link-token-consumed:${token}`;
const CONSUMED_MARKER_TTL_SECONDS = 24 * 60 * 60;
export interface ConsumedLinkTokenMarker {
export const issueLinkToken = async (
export const peekLinkToken = async (token: LinkToken): Promise<LinkTokenPayload | null> => {
export const consumeLinkToken = async (token: LinkToken): Promise<LinkTokenPayload | null> => {
export const peekConsumedLinkToken = async (
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { randomUUID } from 'node:crypto';

import debug from 'debug';

import { getMessengerLinkTokenTtl, type MessengerPlatform } from '@/config/messenger';
import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';

const log = debug('lobe-server:messenger:link-token');

/** Lower-cased random token used as the URL `random_id` query param. */
export type LinkToken = string;

export interface LinkTokenPayload {
  createdAt: number;
  platform: MessengerPlatform;
  platformUserId: string;
  /** Best-effort display name shown on the verify-im confirm screen. */
  platformUsername?: string;
  /**
   * Per-tenant install id this link belongs to. Slack `team_id` (or
   * `enterprise_id` for Grid org installs) — written into
   * `messenger_account_links.tenant_id` on confirm so the router knows which
   * workspace's bot to dispatch to. Empty / undefined for global-bot
   * platforms (Telegram).
   */
  tenantId?: string;
  /**
   * Human-readable workspace / tenant name (e.g. `"Acme Inc"`) so the
   * verify-im page can render "Linking <user> in **Acme Inc** workspace"
   * without a server-side `team.info` round-trip.
   */
  tenantName?: string;
}

const tokenKey = (token: LinkToken): string => `messenger:link-token:${token}`;

/** Existing token reuse map — same `(platform, platformUserId)` shouldn't
 * generate a fresh token each /start; reuse the live one if it hasn't expired
 * so the user's previous "Link Account" button still works. */
const reuseKey = (platform: MessengerPlatform, platformUserId: string): string =>
  `messenger:link-token-reuse:${platform}:${platformUserId}`;

/** Marker written when a token is consumed via `confirmLink`. Lets the
 * verify-im page distinguish "token expired" (TTL ran out before binding)
 * from "binding succeeded earlier" (token was deliberately consumed) when
 * the user later refreshes or revisits the URL. */
const consumedKey = (token: LinkToken): string => `messenger:link-token-consumed:${token}`;

/** TTL for the "consumed" marker. Picked to comfortably outlive the active
 * token TTL so a refresh after binding still resolves to a "consumed" hit
 * instead of a misleading "expired" message. */
const CONSUMED_MARKER_TTL_SECONDS = 24 * 60 * 60;

export interface ConsumedLinkTokenMarker {
  consumedAt: number;
  platform: MessengerPlatform;
  tenantId?: string;
}

/**
 * Issue a one-shot link token bound to a platform user. If a live token already
 * exists for the same `(platform, platformUserId)`, return it instead of
 * minting a new one.
 */
export const issueLinkToken = async (
  payload: Omit<LinkTokenPayload, 'createdAt'>,
): Promise<LinkToken> => {
  const redis = getAgentRuntimeRedisClient();
  if (!redis) {
    throw new Error('Redis is required for messenger link token storage');
  }

  const ttl = getMessengerLinkTokenTtl();
  const existing = await redis.get(reuseKey(payload.platform, payload.platformUserId));
  if (existing) {
    const live = await redis.get(tokenKey(existing));
    if (live) {
      log(
        'issueLinkToken: reusing existing token for %s:%s',
        payload.platform,
        payload.platformUserId,
      );
      return existing;
    }
  }

  const token = randomUUID().replaceAll('-', '');
  const value: LinkTokenPayload = { ...payload, createdAt: Date.now() };

  await redis.set(tokenKey(token), JSON.stringify(value), 'EX', ttl);
  await redis.set(reuseKey(payload.platform, payload.platformUserId), token, 'EX', ttl);

  log(
    'issueLinkToken: issued token for %s:%s ttl=%ds',
    payload.platform,
    payload.platformUserId,
    ttl,
  );
  return token;
};

export const peekLinkToken = async (token: LinkToken): Promise<LinkTokenPayload | null> => {
  const redis = getAgentRuntimeRedisClient();
  if (!redis) return null;

  const raw = await redis.get(tokenKey(token));
  if (!raw) return null;

  try {
    return JSON.parse(raw) as LinkTokenPayload;
  } catch {
    return null;
  }
};

export const consumeLinkToken = async (token: LinkToken): Promise<LinkTokenPayload | null> => {
  const redis = getAgentRuntimeRedisClient();
  if (!redis) return null;

  const raw = await redis.get(tokenKey(token));
  if (!raw) return null;

  let payload: LinkTokenPayload;
  try {
    payload = JSON.parse(raw) as LinkTokenPayload;
  } catch {
    await redis.del(tokenKey(token));
    return null;
  }

  await redis.del(tokenKey(token));
  await redis.del(reuseKey(payload.platform, payload.platformUserId));

  const marker: ConsumedLinkTokenMarker = {
    consumedAt: Date.now(),
    platform: payload.platform,
    tenantId: payload.tenantId,
  };
  await redis.set(consumedKey(token), JSON.stringify(marker), 'EX', CONSUMED_MARKER_TTL_SECONDS);

  return payload;
};

/**
 * Read the "consumed" marker for a token. Returns null when the token was
 * never consumed (or the marker has itself expired). Used by the verify-im
 * peek endpoint to tell the user whether their binding already succeeded.
 */
export const peekConsumedLinkToken = async (
  token: LinkToken,
): Promise<ConsumedLinkTokenMarker | null> => {
  const redis = getAgentRuntimeRedisClient();
  if (!redis) return null;

  const raw = await redis.get(consumedKey(token));
  if (!raw) return null;

  try {
    return JSON.parse(raw) as ConsumedLinkTokenMarker;
  } catch {
    return null;
  }
};

```
