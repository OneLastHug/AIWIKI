# 文件：src/server/services/bot/platforms/index.ts

## 文件职责
这个文件位于 `src/server/services/bot/platforms`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { discord } from './discord/definition';
import { feishu } from './feishu/definitions/feishu';
import { lark } from './feishu/definitions/lark';
import { line } from './line/definition';
import { qq } from './qq/definition';
import { PlatformRegistry } from './registry';
import { slack } from './slack/definition';
import { telegram } from './telegram/definition';
import { wechat } from './wechat/definition';
export {
export { PlatformRegistry } from './registry';
export type {
export { ClientFactory } from './types';
export type { ProviderConfigInput, ResolvedBotProviderConfig } from './utils';
export {
export { discord } from './discord/definition';
export { feishu } from './feishu/definitions/feishu';
export { lark } from './feishu/definitions/lark';
export { line } from './line/definition';
export { qq } from './qq/definition';
export { slack } from './slack/definition';
export { telegram } from './telegram/definition';
export { wechat } from './wechat/definition';
export const platformRegistry = new PlatformRegistry();
```

## 主要对外内容
```text
export const platformRegistry = new PlatformRegistry();
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
// --------------- Core types & utilities ---------------
// --------------- Registry singleton ---------------
import { discord } from './discord/definition';
import { feishu } from './feishu/definitions/feishu';
import { lark } from './feishu/definitions/lark';
import { line } from './line/definition';
import { qq } from './qq/definition';
import { PlatformRegistry } from './registry';
import { slack } from './slack/definition';
import { telegram } from './telegram/definition';
import { wechat } from './wechat/definition';

export {
  allowFromField,
  type BotReplyLocale,
  displayToolCallsField,
  type DmDecision,
  type DmPolicy,
  type DmSettings,
  extractDmSettings,
  extractGroupSettings,
  extractUserAllowlist,
  extractWatchKeywordEntries,
  extractWatchKeywords,
  findMatchingWatchKeywordEntries,
  getBotReplyLocale,
  getStepReactionEmoji,
  type GroupPolicy,
  type GroupSettings,
  makeDmPolicyField,
  makeGroupPolicyFields,
  makeServerIdField,
  makeUserIdField,
  messageMatchesWatchKeyword,
  normalizeAllowFromEntries,
  normalizeBotReplyLocale,
  RECEIVED_REACTION_EMOJI,
  shouldAllowSender,
  shouldHandleDm,
  shouldHandleGroup,
  THINKING_REACTION_EMOJI,
  type UserAllowlist,
  validateAccessSettings,
  type WatchKeywordEntry,
  watchKeywordsField,
  WORKING_REACTION_EMOJI,
} from './const';
export { PlatformRegistry } from './registry';
export type {
  BotPlatformRedisClient,
  BotPlatformRuntimeContext,
  BotProviderConfig,
  ConnectionMode,
  ExtractFilesResult,
  FieldSchema,
  PlatformClient,
  PlatformDefinition,
  PlatformDocumentation,
  PlatformMessenger,
  SerializedPlatformDefinition,
  UsageStats,
  ValidationResult,
} from './types';
export { ClientFactory } from './types';
export type { ProviderConfigInput, ResolvedBotProviderConfig } from './utils';
export {
  buildRuntimeKey,
  extractDefaults,
  formatDuration,
  formatTokens,
  formatUsageStats,
  getEffectiveConnectionMode,
  mergeWithDefaults,
  parseRuntimeKey,
  resolveBotProviderConfig,
  resolveConnectionMode,
} from './utils';

// --------------- Platform definitions ---------------
export { discord } from './discord/definition';
export { feishu } from './feishu/definitions/feishu';
export { lark } from './feishu/definitions/lark';
export { line } from './line/definition';
export { qq } from './qq/definition';
export { slack } from './slack/definition';
export { telegram } from './telegram/definition';
export { wechat } from './wechat/definition';

export const platformRegistry = new PlatformRegistry();

platformRegistry.register(discord);
platformRegistry.register(telegram);
platformRegistry.register(slack);
platformRegistry.register(feishu);
platformRegistry.register(lark);
platformRegistry.register(qq);
platformRegistry.register(wechat);
platformRegistry.register(line);

```
