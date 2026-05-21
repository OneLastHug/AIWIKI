# 文件：src/server/services/bot/platforms/qq/schema.ts

## 文件职责
这个文件位于 `src/server/services/bot/platforms/qq`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { MAX_BOT_DEBOUNCE_MS } from '@lobechat/const';
import {
import type { FieldSchema } from '../types';
import { DEFAULT_QQ_CONNECTION_MODE } from './const';
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
import { MAX_BOT_DEBOUNCE_MS } from '@lobechat/const';

import {
  allowFromField,
  displayToolCallsField,
  makeDmPolicyField,
  makeGroupPolicyFields,
  makeUserIdField,
  watchKeywordsField,
} from '../const';
import type { FieldSchema } from '../types';
import { DEFAULT_QQ_CONNECTION_MODE } from './const';

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
        key: 'appSecret',
        description: 'channel.appSecretHint',
        label: 'channel.appSecret',
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
      makeUserIdField('qq'),
      {
        key: 'connectionMode',
        default: DEFAULT_QQ_CONNECTION_MODE,
        description: 'channel.connectionModeHint',
        enum: ['websocket', 'webhook'],
        enumDescriptions: [
          'channel.connectionModeWebSocketHint',
          'channel.connectionModeWebhookHint',
        ],
        enumLabels: ['channel.connectionModeWebSocket', 'channel.connectionModeWebhook'],
        label: 'channel.connectionMode',
        type: 'string',
      },
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
        default: 5000,
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
      makeDmPolicyField({ policy: 'open' }),
      ...makeGroupPolicyFields({ policy: 'open' }),
      allowFromField,
      watchKeywordsField,
    ],
    type: 'object',
  },
];

```
