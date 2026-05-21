# 文件：src/server/services/messenger/installations/index.ts

## 文件职责
这个文件位于 `src/server/services/messenger/installations`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { MessengerPlatform } from '@/config/messenger';
import type { ConnectionMode } from '../../bot/platforms';
import { DiscordInstallationStore } from './discord';
import { SlackInstallationStore } from './slack';
import { TelegramInstallationStore } from './telegram';
import type { MessengerInstallationStore } from './types';
export const getInstallationStore = (
export const messengerConnectionId = (platform: string): string =>
export const messengerConnectionIdForUser = (params: {
export { DISCORD_INSTALLATION_KEY, DiscordInstallationStore } from './discord';
export { SlackInstallationStore } from './slack';
export { TELEGRAM_INSTALLATION_KEY, TelegramInstallationStore } from './telegram';
export type { InstallationCredentials, MessengerInstallationStore } from './types';
```

## 主要对外内容
```text
const stores: Partial<Record<MessengerPlatform, MessengerInstallationStore>> = {};
const create = (platform: MessengerPlatform): MessengerInstallationStore | null => {
export const getInstallationStore = (
const SINGLETON_SUFFIX = ':singleton';
export const messengerConnectionId = (platform: string): string =>
export const messengerConnectionIdForUser = (params: {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { MessengerPlatform } from '@/config/messenger';

import type { ConnectionMode } from '../../bot/platforms';
import { DiscordInstallationStore } from './discord';
import { SlackInstallationStore } from './slack';
import { TelegramInstallationStore } from './telegram';
import type { MessengerInstallationStore } from './types';

/**
 * One InstallationStore singleton per platform — they're stateless apart
 * from the in-process refresh single-flight cache (Slack), so a single
 * instance per process is correct.
 */
const stores: Partial<Record<MessengerPlatform, MessengerInstallationStore>> = {};

const create = (platform: MessengerPlatform): MessengerInstallationStore | null => {
  switch (platform) {
    case 'slack': {
      return new SlackInstallationStore();
    }
    case 'telegram': {
      return new TelegramInstallationStore();
    }
    case 'discord': {
      return new DiscordInstallationStore();
    }
    default: {
      return null;
    }
  }
};

export const getInstallationStore = (
  platform: MessengerPlatform,
): MessengerInstallationStore | null => {
  if (!stores[platform]) {
    const store = create(platform);
    if (!store) return null;
    stores[platform] = store;
  }
  return stores[platform] ?? null;
};

const SINGLETON_SUFFIX = ':singleton';

/**
 * Singleton gateway connectionId for a platform-level install.
 *
 * Mirrors what dc-center registers when it brings a SystemBot online —
 * websocket platforms (Discord today) keep exactly one persistent WS at
 * `messenger:<platform>:singleton`, and typing must route to that same DO
 * because there's no per-user WS to fall back on.
 */
export const messengerConnectionId = (platform: string): string =>
  `messenger:${platform}:singleton`;

/**
 * Build the gateway connection id used for a messenger run's typing DO.
 *
 * Two regimes:
 *
 * 1. **Websocket + singleton install** (Discord SystemBot today) — the WS
 *    is platform-wide and registered by dc-center at
 *    `messenger:<platform>:singleton`. Per-user sharding does not exist on
 *    the gateway, so we must return that exact connectionId; otherwise
 *    `startTyping` targets a non-existent DO and typing is invisible.
 *
 * 2. **Everything else** — per-user shard `(platform, lobeUserId)` so each
 *    user gets their own webhook-mode DO. Solves the cross-conversation
 *    `TypingState` overwrite bug from a shared DO and avoids piling 200K-MAU
 *    load onto a single hot DO.
 *      - Telegram / single-token platforms: `messenger:<platform>:user-<userId>`
 *      - Slack: `messenger:slack:<tenantId>:user-<userId>` — tenant retained
 *        because the same `lobeUserId` may link multiple workspaces, each
 *        with its own rotating OAuth token.
 *
 * Single source of truth: derives directly from the `installationKey`
 * shape (`<platform>:<tenantId>` or `<platform>:singleton`) and the
 * effective `connectionMode` so callers never branch on platform name.
 */
export const messengerConnectionIdForUser = (params: {
  connectionMode?: ConnectionMode;
  installationKey: string;
  userId: string;
}): string => {
  const { connectionMode, installationKey, userId } = params;

  if (installationKey.endsWith(SINGLETON_SUFFIX)) {
    const platform = installationKey.slice(0, -SINGLETON_SUFFIX.length);
    if (connectionMode === 'websocket') return messengerConnectionId(platform);
    return `messenger:${platform}:user-${userId}`;
  }
  return `messenger:${installationKey}:user-${userId}`;
};

export { DISCORD_INSTALLATION_KEY, DiscordInstallationStore } from './discord';
export { SlackInstallationStore } from './slack';
export { TELEGRAM_INSTALLATION_KEY, TelegramInstallationStore } from './telegram';
export type { InstallationCredentials, MessengerInstallationStore } from './types';

```
