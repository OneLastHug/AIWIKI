# 文件：src/server/routers/lambda/userMemories.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { BRANDING_PROVIDER, ENABLE_BUSINESS_FEATURES } from '@lobechat/business-const';
import {
import { type LobeChatDatabase } from '@lobechat/database';
import {
import type { QueryTaxonomyOptionsResult, SearchMemoryResult } from '@lobechat/types';
import { LayersEnum, queryTaxonomyOptionsSchema, searchMemorySchema } from '@lobechat/types';
import { type SQL } from 'drizzle-orm';
import { and, asc, eq, gte, lte } from 'drizzle-orm';
import pMap from 'p-map';
import { z } from 'zod';
import {
import {
import { UserMemoryTopicRepository } from '@/database/repositories/userMemory';
import {
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { getServerDefaultFilesConfig } from '@/server/globalConfig';
import { initModelRuntimeFromDB } from '@/server/modules/ModelRuntime';
import type { UserMemoryEmbeddingRuntime } from '@/server/services/memory/userMemory/embedding';
import { embedUserMemoryTexts } from '@/server/services/memory/userMemory/embedding';
import { normalizeSearchMemoryParams } from '@/server/services/memory/userMemory/searchParams';
export const userMemoriesRouter = router({
```

## 主要对外内容
```text
const EMPTY_SEARCH_RESULT: SearchMemoryResult = {
const EMPTY_TAXONOMY_RESULT: QueryTaxonomyOptionsResult = {
type MemorySearchContext = {
type MemoryEffort = 'high' | 'low' | 'medium';
const normalizeMemoryEffort = (value: unknown): MemoryEffort => {
const applySearchLimitsByEffort = (
const searchUserMemories = async (
const getEmbeddingRuntime = async (serverDB: LobeChatDatabase, userId: string) => {
const createEmbedder = (
const REEMBED_TABLE_KEYS = [
type ReEmbedTableKey = (typeof REEMBED_TABLE_KEYS)[number];
const reEmbedInputSchema = z.object({
interface ReEmbedStats {
const combineConditions = (conditions: Array<SQL | undefined>): SQL | undefined => {
const normalizeEmbeddable = (value?: string | null): string | undefined => {
const memoryProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const userMemoriesRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { BRANDING_PROVIDER, ENABLE_BUSINESS_FEATURES } from '@lobechat/business-const';
import {
  DEFAULT_SEARCH_USER_MEMORY_TOP_K,
  DEFAULT_USER_MEMORY_EMBEDDING_MODEL_ITEM,
  MEMORY_SEARCH_TOP_K_LIMITS,
} from '@lobechat/const';
import { type LobeChatDatabase } from '@lobechat/database';
import {
  ActivityMemoryItemSchema,
  AddIdentityActionSchema,
  ContextMemoryItemSchema,
  ExperienceMemoryItemSchema,
  PreferenceMemoryItemSchema,
  RemoveIdentityActionSchema,
  UpdateIdentityActionSchema,
} from '@lobechat/memory-user-memory';
import type { QueryTaxonomyOptionsResult, SearchMemoryResult } from '@lobechat/types';
import { LayersEnum, queryTaxonomyOptionsSchema, searchMemorySchema } from '@lobechat/types';
import { type SQL } from 'drizzle-orm';
import { and, asc, eq, gte, lte } from 'drizzle-orm';
import pMap from 'p-map';
import { z } from 'zod';

import {
  type IdentityEntryBasePayload,
  type IdentityEntryPayload,
} from '@/database/models/userMemory';
import {
  UserMemoryActivityModel,
  UserMemoryExperienceModel,
  UserMemoryIdentityModel,
  UserMemoryModel,
} from '@/database/models/userMemory';
import { UserMemoryTopicRepository } from '@/database/repositories/userMemory';
import {
  userMemories,
  userMemoriesActivities,
  userMemoriesContexts,
  userMemoriesExperiences,
  userMemoriesIdentities,
  userMemoriesPreferences,
  userSettings,
} from '@/database/schemas';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { getServerDefaultFilesConfig } from '@/server/globalConfig';
import { initModelRuntimeFromDB } from '@/server/modules/ModelRuntime';
import type { UserMemoryEmbeddingRuntime } from '@/server/services/memory/userMemory/embedding';
import { embedUserMemoryTexts } from '@/server/services/memory/userMemory/embedding';
import { normalizeSearchMemoryParams } from '@/server/services/memory/userMemory/searchParams';

const EMPTY_SEARCH_RESULT: SearchMemoryResult = {
  activities: [],
  contexts: [],
  experiences: [],
  identities: [],
  meta: {
    appliedFilters: {},
    appliedQueries: [],
    layers: {
      activities: { hasMore: false, returned: 0, total: 0 },
      contexts: { hasMore: false, returned: 0, total: 0 },
      experiences: { hasMore: false, returned: 0, total: 0 },
      identities: { hasMore: false, returned: 0, total: 0 },
      preferences: { hasMore: false, returned: 0, total: 0 },
    },
  },
  preferences: [],
};

const EMPTY_TAXONOMY_RESULT: QueryTaxonomyOptionsResult = {
  categories: [],
  hasMore: {},
  labels: [],
  relationships: [],
  roles: [],
  statuses: [],
  tags: [],
  types: [],
};

type MemorySearchContext = {
  memoryModel: UserMemoryModel;
  memoryEffort: MemoryEffort;
  serverDB: LobeChatDatabase;
  userId: string;
};

type MemoryEffort = 'high' | 'low' | 'medium';

const normalizeMemoryEffort = (value: unknown): MemoryEffort => {
  if (value === 'low' || value === 'medium' || value === 'high') return value;
  return 'medium';
};

const applySearchLimitsByEffort = (
  effort: MemoryEffort,
  requested: {
    activities: number;
    contexts: number;
    experiences: number;
    identities: number;
    preferences: number;
  },
) => {
  const limit = MEMORY_SEARCH_TOP_K_LIMITS[effort];
  const identityLimit = effort === 'high' ? 4 : effort === 'low' ? 1 : 2;

  return {
    activities: Math.min(requested.activities, limit.activities),
    contexts: Math.min(requested.contexts, limit.contexts),
    experiences: Math.min(requested.experiences, limit.experiences),
    identities: Math.min(requested.identities, identityLimit),
    preferences: Math.min(requested.preferences, limit.preferences),
  };
};

const searchUserMemories = async (
  ctx: MemorySearchContext,
  input: z.infer<typeof searchMemorySchema>,
): Promise<SearchMemoryResult> => {
  const normalizedInput = normalizeSearchMemoryParams(input);
  const { provider, model: embeddingModel } =
    getServerDefaultFilesConfig().embeddingModel || DEFAULT_USER_MEMORY_EMBEDDING_MODEL_ITEM;
  const modelRuntime = await initModelRuntimeFromDB(ctx.serverDB, ctx.userId, provider);
  const normalizedQueries = [
    ...new Set((normalizedInput.queries ?? []).map((query) => query.trim()).filter(Boolean)),
  ];

  const queryEmbeddings =
    normalizedQueries.length > 0
      ? (
          await embedUserMemoryTexts({
            input: normalizedQueries,
            model: embeddingModel,
            runtime: modelRuntime,
            source: 'lambda:userMemories.search',
            userId: ctx.userId,
          })
        ).filter((embedding): embedding is number[] => Boolean(embedding))
      : [];

  const effectiveEffort = normalizeMemoryEffort(normalizedInput.effort ?? ctx.memoryEffort);
  const effortDefaults = MEMORY_SEARCH_TOP_K_LIMITS[effectiveEffort];

  const requestedLimits = {
    activities: normalizedInput.topK?.activities ?? effortDefaults.activities,
    contexts: normalizedInput.topK?.contexts ?? effortDefaults.contexts,
    experiences: normalizedInput.topK?.experiences ?? effortDefaults.experiences,
    identities:
      normalizedInput.topK?.identities ??
      (effectiveEffort === 'high' ? 4 : effectiveEffort === 'low' ? 1 : 2),
    preferences: normalizedInput.topK?.preferences ?? effortDefaults.preferences,
  };

  const effortConstrainedLimits = applySearchLimitsByEffort(effectiveEffort, requestedLimits);
  return ctx.memoryModel.searchMemory(
    { ...normalizedInput, queries: normalizedQueries, topK: effortConstrainedLimits },
    queryEmbeddings,
  ) as Promise<SearchMemoryResult>;
};

const getEmbeddingRuntime = async (serverDB: LobeChatDatabase, userId: string) => {
  const { provider, model: embeddingModel } =
    getServerDefaultFilesConfig().embeddingModel || DEFAULT_USER_MEMORY_EMBEDDING_MODEL_ITEM;
  // Read user's provider config from database
  const agentRuntime = await initModelRuntimeFromDB(
    serverDB,
    userId,
    ENABLE_BUSINESS_FEATURES ? BRANDING_PROVIDER : provider,
  );

  return { agentRuntime, embeddingModel };
};

const createEmbedder = (
  agentRuntime: UserMemoryEmbeddingRuntime,
  embeddingModel: string,
  userId: string,
) => {
  return async (value?: string | null): Promise<number[] | undefined> => {
    if (!value || value.trim().length === 0) return undefined;

    const [embedding] = await embedUserMemoryTexts({
      input: [value],
      model: embeddingModel,
      runtime: agentRuntime,
      source: 'lambda:userMemories.tool',
      userId,
    });

    return embedding;
  };
};

const REEMBED_TABLE_KEYS = [
  'userMemories',
  'contexts',
  'preferences',
  'identities',
  'experiences',
  'activities',
] as const;
type ReEmbedTableKey = (typeof REEMBED_TABLE_KEYS)[number];

const reEmbedInputSchema = z.object({
  concurrency: z.coerce.number().int().min(1).max(50).optional(),
  endDate: z.coerce.date().optional(),
  limit: z.coerce.number().int().min(1).optional(),
  only: z.array(z.enum(REEMBED_TABLE_KEYS)).optional(),
  startDate: z.coerce.date().optional(),
});

interface ReEmbedStats {
  failed: number;
  skipped: number;
  succeeded: number;
  total: number;
}

const combineConditions = (conditions: Array<SQL | undefined>): SQL | undefined => {
  const filtered = conditions.filter((condition): condition is SQL => condition !== undefined);
  if (filtered.length === 0) return undefined;
  if (filtered.length === 1) return filtered[0];

  return and(...filtered);
};

const normalizeEmbeddable = (value?: string | null): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();

  return trimmed.length > 0 ? trimmed : undefined;
};

const memoryProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;
  const userSettingsRow = await ctx.serverDB.query.userSettings.findFirst({
    columns: { memory: true },
    where: eq(userSettings.id, ctx.userId),
  });
  const memoryConfig =
    typeof userSettingsRow?.memory === 'object' && userSettingsRow?.memory !== null
      ? (userSettingsRow.memory as { effort?: unknown })
      : undefined;
  const memoryEffort = normalizeMemoryEffort(memoryConfig?.effort);

  return opts.next({
    ctx: {
      activityModel: new UserMemoryActivityModel(ctx.serverDB, ctx.userId),
      experienceModel: new UserMemoryExperienceModel(ctx.serverDB, ctx.userId),
      identityModel: new UserMemoryIdentityModel(ctx.serverDB, ctx.userId),
      memoryModel: new UserMemoryModel(ctx.serverDB, ctx.userId),
      memoryEffort,
    },
  });
});

export const userMemoriesRouter = router({
  getMemoryDetail: memoryProcedure
    .input(z.object({ id: z.string(), layer: z.nativeEnum(LayersEnum) }))
    .query(async ({ ctx, input }) => {
      try {
        return await ctx.memoryModel.getMemoryDetail(input);
      } catch (error) {
        console.error('Failed to retrieve memory detail:', error);
        return null;
      }
    }),

  queryActivities: memoryProcedure
    .input(
      z
        .object({
          order: z.enum(['asc', 'desc']).optional(),
          page: z.coerce.number().int().min(1).optional(),
          pageSize: z.coerce.number().int().min(1).max(100).optional(),
          q: z.string().optional(),
          sort: z.enum(['capturedAt', 'startsAt']).optional(),
          status: z.array(z.string()).optional(),
          tags: z.array(z.string()).optional(),
          types: z.array(z.string()).optional(),
        })
        .optional(),
    )
    .query(async ({ ctx, input }) => {
      const params = input ?? {};
      const fallbackPage = params.page ?? 1;
      const fallbackPageSize = params.pageSize ?? 20;

      try {
        return await ctx.activityModel.queryList(params);
      } catch (error) {
        console.error('Failed to query activities:', error);
        return { items: [], page: fallbackPage, pageSize: fallbackPageSize, total: 0 };
      }
    }),

  queryExperiences: memoryProcedure
    .input(
      z
        .object({
          order: z.enum(['asc', 'desc']).optional(),
          page: z.coerce.number().int().min(1).optional(),
          pageSize: z.coerce.number().int().min(1).max(100).optional(),
          q: z.string().optional(),
          sort: z.enum(['capturedAt', 'scoreConfidence']).optional(),
          tags: z.array(z.string()).optional(),
          types: z.array(z.string()).optional(),
        })
        .optional(),
    )
    .query(async ({ ctx, input }) => {
      const params = input ?? {};
      const fallbackPage = params.page ?? 1;
      const fallbackPageSize = params.pageSize ?? 20;

      try {
        return await ctx.experienceModel.queryList(params);
      } catch (error) {
        console.error('Failed to query experiences:', error);
        return { items: [], page: fallbackPage, pageSize: fallbackPageSize, total: 0 };
      }
    }),

  queryIdentities: memoryProcedure
    .input(
      z
        .object({
          order: z.enum(['asc', 'desc']).optional(),
          page: z.coerce.number().int().min(1).optional(),
          pageSize: z.coerce.number().int().min(1).max(100).optional(),
          q: z.string().optional(),
          relationships: z.array(z.string()).optional(),
          sort: z.enum(['capturedAt', 'type']).optional(),
          tags: z.array(z.string()).optional(),
          types: z.array(z.string()).optional(),
        })
        .optional(),
    )
    .query(async ({ ctx, input }) => {
      const params = input ?? {};
      const fallbackPage = params.page ?? 1;
      const fallbackPageSize = params.pageSize ?? 20;

      try {
        return await ctx.identityModel.queryList(params);
      } catch (error) {
        console.error('Failed to query identities:', error);
        return { items: [], page: fallbackPage, pageSize: fallbackPageSize, total: 0 };
      }
    }),

  queryIdentitiesForInjection: memoryProcedure
    .input(z.object({ limit: z.coerce.number().int().min(1).max(100).optional() }).optional())
    .query(async ({ ctx, input }) => {
      try {
        return await ctx.identityModel.queryForInjection(input?.limit ?? 50);
      } catch (error) {
        console.error('Failed to query identities for injection:', error);
        return [];
      }
    }),

  queryIdentityRoles: memoryProcedure
    .input(
      z
        .object({
          page: z.coerce.number().int().min(1).optional(),
          size: z.coerce.number().int().min(1).max(100).optional(),
        })
        .optional(),
    )
    .query(async ({ ctx, input }) => {
      try {
        return await ctx.memoryModel.queryIdentityRoles(input ?? {});
      } catch (error) {
        console.error('Failed to query identity roles:', error);
        return { roles: [], tags: [] };
      }
    }),

  queryMemories: memoryProcedure
    .input(
      z
        .object({
          categories: z.array(z.string()).optional(),
          layer: z.nativeEnum(LayersEnum).optional(),
          order: z.enum(['asc', 'desc']).optional(),
          page: z.coerce.number().int().min(1).optional(),
          pageSize: z.coerce.number().int().min(1).max(100).optional(),
          q: z.string().optional(),
          sort: z
            .enum([
              'capturedAt',
              'scoreConfidence',
              'scoreImpact',
              'scorePriority',
              'scoreUrgency',
              'startsAt',
            ])
            .optional(),
          status: z.array(z.string()).optional(),
          tags: z.array(z.string()).optional(),
          types: z.array(z.string()).optional(),
        })
        .optional(),
    )
    .query(async ({ ctx, input }) => {
      const params = input ?? {};
      const fallbackPage = params.page ?? 1;
      const fallbackPageSize = params.pageSize ?? 20;

      try {
        return await ctx.memoryModel.queryMemories({
          ...params,
          order: params.order ?? 'desc',
          sort: params.sort,
        });
      } catch (error) {
        console.error('Failed to query memories:', error);
        return { items: [], page: fallbackPage, pageSize: fallbackPageSize, total: 0 };
      }
    }),

  queryTags: memoryProcedure
    .input(
      z
        .object({
          layers: z.array(z.nativeEnum(LayersEnum)).optional(),
          page: z.coerce.number().int().min(1).optional(),
          size: z.coerce.number().int().min(1).max(100).optional(),
        })
        .optional(),
    )
    .query(async ({ ctx, input }) => {
      try {
        return await ctx.memoryModel.queryTags(input ?? {});
      } catch (error) {
        console.error('Failed to query memory tags:', error);
        return [];
      }
    }),

  queryTaxonomyOptions: memoryProcedure
    .input(queryTaxonomyOptionsSchema.optional())
    .query(async ({ ctx, input }) => {
      try {
        return await ctx.memoryModel.queryTaxonomyOptions(input ?? {});
      } catch (error) {
        console.error('Failed to query memory taxonomy options:', error);
        return EMPTY_TAXONOMY_RESULT;
      }
    }),

  reEmbedMemories: memoryProcedure
    .input(reEmbedInputSchema.optional())
    .mutation(async ({ ctx, input }) => {
      try {
        const options = input ?? {};
        const { agentRuntime, embeddingModel } = await getEmbeddingRuntime(
          ctx.serverDB,
          ctx.userId,
        );
        const concurrency = options.concurrency ?? 10;
        const shouldProcess = (key: ReEmbedTableKey) =>
          !options.only || options.only.length === 0 || options.only.includes(key);

        const embedTexts = async (texts: string[]): Promise<number[][]> => {
          if (texts.length === 0) return [];

          const response = await embedUserMemoryTexts({
            input: texts,
            model: embeddingModel,
            runtime: agentRuntime,
            source: 'lambda:userMemories.reEmbed',
            userId: ctx.userId,
          });

          if (response.length !== texts.length) {
            throw new Error('Embedding response length mismatch');
          }

          return response.map((embedding) => {
            if (!embedding) throw new Error('Embedding response length mismatch');

            return embedding;
          });
        };

        const results: Partial<Record<ReEmbedTableKey, ReEmbedStats>> = {};

        const run = async (key: ReEmbedTableKey, handler: () => Promise<ReEmbedStats>) => {
          if (!shouldProcess(key)) return;
          results[key] = await handler();
        };

        // Individual re-embed handlers are appended below.
        await run('userMemories', async () => {
          const where = combineConditions([
            eq(userMemories.userId, ctx.userId),
            options.startDate ? gte(userMemories.createdAt, options.startDate) : undefined,
            options.endDate ? lte(userMemories.createdAt, options.endDate) : undefined,
          ]);

          const rows = await ctx.serverDB.query.userMemories.findMany({
            columns: { details: true, id: true, summary: true },
            limit: options.limit,
            orderBy: [asc(userMemories.createdAt)],
            where,
          });

          let succeeded = 0;
          let failed = 0;
          let skipped = 0;

          await pMap(
            rows,
            async (row) => {
              const summaryText = normalizeEmbeddable(row.summary);
              const detailsText = normalizeEmbeddable(row.details);

              try {
                if (!summaryText && !detailsText) {
                  await ctx.memoryModel.updateUserMemoryVectors(row.id, {
                    detailsVector1024: null,
                    summaryVector1024: null,
                  });
                  skipped += 1;
                  return;
                }

                const inputs: string[] = [];
                if (summaryText) inputs.push(summaryText);
                if (detailsText) inputs.push(detailsText);

                const embeddings = await embedTexts(inputs);
                let embedIndex = 0;

                const summaryVector = summaryText ? (embeddings[embedIndex++] ?? null) : null;
                const detailsVector = detailsText ? (embeddings[embedIndex++] ?? null) : null;

                await ctx.memoryModel.updateUserMemoryVectors(row.id, {
                  detailsVector1024: detailsVector,
                  summaryVector1024: summaryVector,
                });

                succeeded += 1;
              } catch (err) {
                failed += 1;
                console.error(
                  `[memoryRouter.reEmbed] Failed to re-embed user memory ${row.id}`,
                  err,
                );
              }
            },
            { concurrency },
          );

          return {
            failed,
            skipped,
            succeeded,
            total: rows.length,
          } satisfies ReEmbedStats;
        });

        await run('contexts', async () => {
          const where = combineConditions([
            eq(userMemoriesContexts.userId, ctx.userId),
            options.startDate ? gte(userMemoriesContexts.createdAt, options.startDate) : undefined,
            options.endDate ? lte(userMemoriesContexts.createdAt, options.endDate) : undefined,
          ]);

          const rows = await ctx.serverDB.query.userMemoriesContexts.findMany({
            columns: { description: true, id: true },
            limit: options.limit,
            orderBy: [asc(userMemoriesContexts.createdAt)],
            where,
          });

          let succeeded = 0;
          let failed = 0;
          let skipped = 0;

          await pMap(
            rows,
            async (row) => {
              const description = normalizeEmbeddable(row.description);

              try {
                if (!description) {
                  await ctx.memoryModel.updateContextVectors(row.id, {
                    descriptionVector: null,
                  });
                  skipped += 1;
                  return;
                }

                const [embedding] = await embedTexts([description]);

                await ctx.memoryModel.updateContextVectors(row.id, {
                  descriptionVector: embedding ?? null,
                });
                succeeded += 1;
              } catch (err) {
                failed += 1;
                console.error(`[memoryRouter.reEmbed] Failed to re-embed context ${row.id}`, err);
              }
            },
            { concurrency },
          );

          return {
            failed,
            skipped,
            succeeded,
            total: rows.length,
          } satisfies ReEmbedStats;
        });

        await run('preferences', async () => {
          const where = combineConditions([
            eq(userMemoriesPreferences.userId, ctx.userId),
            options.startDate
              ? gte(userMemoriesPreferences.createdAt, options.startDate)
              : undefined,
            options.endDate ? lte(userMemoriesPreferences.createdAt, options.endDate) : undefined,
          ]);

          const rows = await ctx.serverDB.query.userMemoriesPreferences.findMany({
            columns: { conclusionDirectives: true, id: true },
            limit: options.limit,
            orderBy: [asc(userMemoriesPreferences.createdAt)],
            where,
          });

          let succeeded = 0;
          let failed = 0;
          let skipped = 0;

          await pMap(
            rows,
            async (row) => {
              const directives = normalizeEmbeddable(row.conclusionDirectives);

              try {
                if (!directives) {
                  await ctx.memoryModel.updatePreferenceVectors(row.id, {
                    conclusionDirectivesVector: null,
                  });
                  skipped += 1;
                  return;
                }

                const [embedding] = await embedTexts([directives]);
                await ctx.memoryModel.updatePreferenceVectors(row.id, {
                  con
```
