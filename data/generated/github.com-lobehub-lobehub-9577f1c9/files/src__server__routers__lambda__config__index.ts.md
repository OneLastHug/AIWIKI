# 文件：src/server/routers/lambda/config/index.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
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
