# 文件：src/server/routers/lambda/config/index.ts

## 文件职责
这个文件位于 `src/server/routers/lambda/config`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { EdgeConfig } from '@lobechat/edge-config';
import debug from 'debug';
import { businessConfigEndpoints } from '@/business/server/lambda-routers/config';
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { getServerFeatureFlagsStateFromRuntimeConfig } from '@/server/featureFlags';
import { getServerDefaultAgentConfig, getServerGlobalConfig } from '@/server/globalConfig';
import {
export const configRouter = router({
```

## 主要对外内容
```text
const log = debug('config-router');
const isObject = (value: unknown): value is Record<string, unknown> =>
const normalizeBillboardItem = (raw: unknown): GlobalBillboardItem | null => {
const normalizeBillboard = (raw: unknown): GlobalBillboard | null => {
const getActiveBillboard = async (): Promise<GlobalBillboard | null> => {
export const configRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { EdgeConfig } from '@lobechat/edge-config';
import debug from 'debug';

import { businessConfigEndpoints } from '@/business/server/lambda-routers/config';
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { getServerFeatureFlagsStateFromRuntimeConfig } from '@/server/featureFlags';
import { getServerDefaultAgentConfig, getServerGlobalConfig } from '@/server/globalConfig';
import {
  type GlobalBillboard,
  type GlobalBillboardItem,
  type GlobalRuntimeConfig,
} from '@/types/serverConfig';

const log = debug('config-router');

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const normalizeBillboardItem = (raw: unknown): GlobalBillboardItem | null => {
  if (!isObject(raw)) return null;
  if (typeof raw.title !== 'string') return null;
  if (typeof raw.description !== 'string') return null;
  return raw as unknown as GlobalBillboardItem;
};

const normalizeBillboard = (raw: unknown): GlobalBillboard | null => {
  if (!isObject(raw)) return null;
  if (typeof raw.slug !== 'string' || raw.slug.length === 0) return null;
  if (typeof raw.title !== 'string') return null;
  if (typeof raw.startAt !== 'string' || typeof raw.endAt !== 'string') return null;
  if (!Array.isArray(raw.items)) return null;

  const items = raw.items
    .map((item) => normalizeBillboardItem(item))
    .filter((item): item is GlobalBillboardItem => item !== null);

  return { ...(raw as unknown as GlobalBillboard), items };
};

const getActiveBillboard = async (): Promise<GlobalBillboard | null> => {
  if (!EdgeConfig.isEnabled()) return null;
  try {
    const data = await new EdgeConfig().getBillboards();
    if (!data) return null;
    const normalized = normalizeBillboard(data);
    if (!normalized) {
      log('[Billboard] EdgeConfig payload failed validation, ignoring:', data);
      return null;
    }
    return normalized;
  } catch (err) {
    log('[Billboard] Failed to read from EdgeConfig:', err);
    return null;
  }
};

export const configRouter = router({
  getDefaultAgentConfig: publicProcedure.query(async () => {
    return getServerDefaultAgentConfig();
  }),

  getGlobalConfig: publicProcedure.query(async ({ ctx }): Promise<GlobalRuntimeConfig> => {
    log('[GlobalConfig] Starting global config retrieval for user:', ctx.userId || 'anonymous');

    const [serverConfig, serverFeatureFlags, billboard] = await Promise.all([
      getServerGlobalConfig(),
      getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined),
      getActiveBillboard(),
    ]);

    log('[GlobalConfig] Server config retrieved');

    return { billboard, serverConfig, serverFeatureFlags };
  }),

  ...businessConfigEndpoints,
});

```
