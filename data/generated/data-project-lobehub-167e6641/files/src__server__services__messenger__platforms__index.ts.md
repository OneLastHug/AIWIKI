# 文件：src/server/services/messenger/platforms/index.ts

## 文件职责
这个文件位于 `src/server/services/messenger/platforms`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { discord } from './discord';
import { MessengerPlatformRegistry } from './registry';
import { slack } from './slack';
import { telegram } from './telegram';
export { MessengerDiscordBinder } from './discord';
export { MessengerPlatformRegistry } from './registry';
export { MessengerSlackBinder, slackWebhookGate } from './slack';
export { MessengerTelegramBinder } from './telegram';
export type {
export const messengerPlatformRegistry = new MessengerPlatformRegistry()
```

## 主要对外内容
```text
export const messengerPlatformRegistry = new MessengerPlatformRegistry()
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { discord } from './discord';
import { MessengerPlatformRegistry } from './registry';
import { slack } from './slack';
import { telegram } from './telegram';

export { MessengerDiscordBinder } from './discord';
export { MessengerPlatformRegistry } from './registry';
export { MessengerSlackBinder, slackWebhookGate } from './slack';
export { MessengerTelegramBinder } from './telegram';
export type {
  MessengerPlatformDefinition,
  MessengerPlatformWebhookGate,
  MessengerWebhookContext,
  SerializedMessengerPlatformDefinition,
} from './types';

/**
 * Singleton registry — one per process. Each platform definition lives
 * alongside its binder + (optional) webhook gate, mirroring `bot/platforms/`.
 */
export const messengerPlatformRegistry = new MessengerPlatformRegistry()
  .register(slack)
  .register(telegram)
  .register(discord);

```
