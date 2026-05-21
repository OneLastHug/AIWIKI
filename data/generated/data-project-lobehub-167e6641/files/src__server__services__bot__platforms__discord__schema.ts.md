# 文件：src/server/services/bot/platforms/discord/schema.ts

## 文件职责
这个文件位于 `src/server/services/bot/platforms/discord`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import {
import {
import type { FieldSchema } from '../types';
import { MAX_DISCORD_HISTORY_LIMIT } from './const';
export const schema: FieldSchema[] = [
```

## 主要对外内容
```text
export const schema: FieldSchema[] = [
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import {
  DEFAULT_BOT_DEBOUNCE_MS,
  DEFAULT_BOT_HISTORY_LIMIT,
  MAX_BOT_DEBOUNCE_MS,
  MIN_BOT_HISTORY_LIMIT,
} from '@lobechat/const';

import {
  allowFromField,
  displayToolCallsField,
  makeDmPolicyField,
  makeGroupPolicyFields,
  makeServerIdField,
  makeUserIdField,
  watchKeywordsField,
} from '../const';
import type { FieldSchema } from '../types';
import { MAX_DISCORD_HISTORY_LIMIT } from './const';

export const schema: FieldSchema[] = [
  {
    key: 'applicationId',
    description: 'channel.applicationIdHint',
    label: 'channel.applicationId',
    required: true,
    type: 'string',
  },
  {
    key: 'credentials',
    label: 'channel.credentials',
    properties: [
      {
        key: 'publicKey',
        description: 'channel.publicKeyHint',
        label: 'channel.publicKey',
        required: true,
        type: 'string',
      },
      {
        key: 'botToken',
        description: 'channel.botTokenEncryptedHint',
        label: 'channel.botToken',
        required: true,
        type: 'password',
      },
    ],
    type: 'object',
  },
  {
    key: 'settings',
    label: 'channel.settings',
    properties: [
      makeUserIdField('discord'),
      makeServerIdField('discord'),
      {
        key: 'charLimit',
        default: 2000,
        description: 'channel.charLimitHint',
        label: 'channel.charLimit',
        maximum: 2000,
        minimum: 100,
        type: 'number',
      },
      {
        key: 'concurrency',
        default: 'queue',
        description: 'channel.concurrencyHint',
        enum: ['queue', 'debounce'],
        enumDescriptions: ['channel.concurrencyQueueHint', 'channel.concurrencyDebounceHint'],
        enumLabels: ['channel.concurrencyQueue', 'channel.concurrencyDebounce'],
        label: 'channel.concurrency',
        type: 'string',
      },
      {
        key: 'debounceMs',
        default: DEFAULT_BOT_DEBOUNCE_MS,
        description: 'channel.debounceMsHint',
        label: 'channel.debounceMs',
        maximum: MAX_BOT_DEBOUNCE_MS,
        minimum: 100,
        type: 'number',
        visibleWhen: { field: 'concurrency', value: 'debounce' },
      },
      {
        key: 'showUsageStats',
        default: false,
        description: 'channel.showUsageStatsHint',
        label: 'channel.showUsageStats',
        type: 'boolean',
      },
      displayToolCallsField,
      {
        key: 'historyLimit',
        default: DEFAULT_BOT_HISTORY_LIMIT,
        description: 'channel.historyLimitHint',
        label: 'channel.historyLimit',
        maximum: MAX_DISCORD_HISTORY_LIMIT,
        minimum: MIN_BOT_HISTORY_LIMIT,
        type: 'number',
      },
      makeDmPolicyField({ policy: 'open' }),
      ...makeGroupPolicyFields({ policy: 'open' }),
      allowFromField,
      watchKeywordsField,
    ],
    type: 'object',
  },
];

```
