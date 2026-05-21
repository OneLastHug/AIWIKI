# 文件：src/server/services/discover/index.ts

## 文件职责
这个文件位于 `src/server/services/discover`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import {
import {
import {
import {
import {
import {
import dayjs from 'dayjs';
import debug from 'debug';
import { cloneDeep, countBy, isString, merge, uniq, uniqBy } from 'es-toolkit/compat';
import matter from 'gray-matter';
import { isAiModelVisible } from 'model-bank';
import urlJoin from 'url-join';
import { type TrustedClientUserInfo } from '@/libs/trusted-client';
import { normalizeLocale } from '@/locales/resources';
import { AssistantStore } from '@/server/modules/AssistantStore';
import { PluginStore } from '@/server/modules/PluginStore';
import { MarketService } from '@/server/services/market';
export interface DiscoverServiceOptions {
export class DiscoverService {
```

## 主要对外内容
```text
const log = debug('lobe-server:discover');
export interface DiscoverServiceOptions {
export class DiscoverService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import {
  CURRENT_VERSION,
  DEFAULT_DISCOVER_ASSISTANT_ITEM,
  DEFAULT_DISCOVER_PLUGIN_ITEM,
  DEFAULT_DISCOVER_PROVIDER_ITEM,
  isDesktop,
  KLAVIS_SERVER_TYPES,
} from '@lobechat/const';
import {
  type AgentStatus,
  type AssistantListResponse,
  type AssistantMarketSource,
  type AssistantQueryParams,
  type DiscoverAssistantDetail,
  type DiscoverAssistantItem,
  type DiscoverMcpDetail,
  type DiscoverModelDetail,
  type DiscoverModelItem,
  type DiscoverPluginDetail,
  type DiscoverPluginItem,
  type DiscoverProviderDetail,
  type DiscoverProviderItem,
  type DiscoverSkillItem,
  type DiscoverUserProfile,
  type IdentifiersResponse,
  type McpListResponse,
  type McpQueryParams,
  type ModelListResponse,
  type ModelQueryParams,
  type PluginListResponse,
  type PluginQueryParams,
  type ProviderListResponse,
  type ProviderQueryParams,
} from '@lobechat/types';
import {
  AssistantCategory,
  AssistantSorts,
  CacheRevalidate,
  CacheTag,
  McpCategory,
  McpSorts,
  ModelSorts,
  PluginSorts,
  ProviderSorts,
} from '@lobechat/types';
import {
  getAudioInputUnitRate,
  getTextInputUnitRate,
  getTextOutputUnitRate,
} from '@lobechat/utils';
import {
  type CategoryItem,
  type CategoryListQuery,
  type MarketSDK,
  type UserInfoResponse,
} from '@lobehub/market-sdk';
import {
  type AgentEventRequest,
  type CallReportRequest,
  type InstallReportRequest,
  type PluginEventRequest,
} from '@lobehub/market-types';
import dayjs from 'dayjs';
import debug from 'debug';
import { cloneDeep, countBy, isString, merge, uniq, uniqBy } from 'es-toolkit/compat';
import matter from 'gray-matter';
import { isAiModelVisible } from 'model-bank';
import urlJoin from 'url-join';

import { type TrustedClientUserInfo } from '@/libs/trusted-client';
import { normalizeLocale } from '@/locales/resources';
import { AssistantStore } from '@/server/modules/AssistantStore';
import { PluginStore } from '@/server/modules/PluginStore';
import { MarketService } from '@/server/services/market';

const log = debug('lobe-server:discover');

export interface DiscoverServiceOptions {
  /** Access token from OIDC flow (legacy) */
  accessToken?: string;
  /** User info for generating trusted client token */
  userInfo?: TrustedClientUserInfo;
}

export class DiscoverService {
  assistantStore = new AssistantStore();
  pluginStore = new PluginStore();
  market: MarketSDK;

  constructor(options: DiscoverServiceOptions = {}) {
    const { accessToken, userInfo } = options;

    // Use MarketService to initialize MarketSDK
    const marketService = new MarketService({ accessToken, userInfo });
    this.market = marketService.market;

    log(
      'DiscoverService initialized with market baseURL: %s, hasAuth: %s, userId: %s',
      process.env.MARKET_BASE_URL,
      !!(accessToken || userInfo),
      userInfo?.userId,
    );
  }

  async registerClient({ userAgent }: { userAgent?: string }) {
    const getDeviceId = async (): Promise<string> => {
      // 1. Use VERCEL_PROJECT_ID in Vercel environment
      if (process.env.VERCEL_PROJECT_ID) {
        return process.env.VERCEL_PROJECT_ID;
      }

      // 2. Use machine-id for desktop
      if (isDesktop) {
        try {
          // Dynamic import
          const { machineId } = await import('node-machine-id');
          return await machineId();
        } catch (error) {
          console.error('Failed to get machine-id:', error);
        }
      }

      return 'unknown-device';
    };

    const deviceId = await getDeviceId();

    const { client_id, client_secret } = await this.market.registerClient({
      clientName: `LobeHub ${isDesktop ? 'Desktop' : 'Web'}`,
      clientType: isDesktop ? 'desktop' : 'web',
      deviceId,
      platform: isDesktop ? process.platform : userAgent,
      version: CURRENT_VERSION,
    });

    return { clientId: client_id, clientSecret: client_secret };
  }

  async fetchM2MToken(params: { clientId: string; clientSecret: string }) {
    // Use MarketService with M2M credentials
    const marketService = new MarketService({
      clientCredentials: params,
    });

    const tokenInfo = await marketService.fetchM2MToken();

    return {
      accessToken: tokenInfo.accessToken,
      expiresIn: tokenInfo.expiresIn,
    };
  }

  // ============================== Call Cloud Mcp Endpoint Methods ==============================

  async callCloudMcpEndpoint(params: {
    apiParams: Record<string, any>;
    identifier: string;
    toolName: string;
    userAccessToken?: string;
  }) {
    log('callCloudMcpEndpoint: params=%O', {
      apiParams: params.apiParams,
      hasUserAccessToken: !!params.userAccessToken,
      identifier: params.identifier,
      toolName: params.toolName,
    });

    try {
      // Build headers - only include Authorization if userAccessToken is provided
      // When userAccessToken is not provided, MarketSDK will use trustedClientToken for authentication
      const headers: Record<string, string> = {};
      if (params.userAccessToken) {
        headers.Authorization = `Bearer ${params.userAccessToken}`;
      }

      // Call cloud gateway with optional user access token in Authorization header
      const result = await this.market.plugins.callCloudGateway(
        {
          apiParams: params.apiParams,
          identifier: params.identifier,
          toolName: params.toolName,
        },
        {
          headers,
        },
      );

      log('callCloudMcpEndpoint: success, result=%O', result);
      return result;
    } catch (error) {
      log('callCloudMcpEndpoint: error=%O', error);
      throw error;
    }
  }

  // ============================== Helper Methods ==============================

  /**
   * Calculate ModelAbilities completeness score
   * Higher score indicates more complete abilities
   */
  private calculateAbilitiesScore = (abilities?: any): number => {
    if (!abilities) return 0;

    let score = 0;
    const abilityWeights = {
      files: 1,
      functionCall: 1,
      imageOutput: 1,
      reasoning: 1,
      search: 1,
      vision: 1,
    };

    Object.entries(abilityWeights).forEach(([ability, weight]) => {
      if (abilities[ability]) {
        score += weight;
      }
    });

    log('calculateAbilitiesScore: abilities=%O, score=%d', abilities, score);
    return score;
  };

  /**
   * Select the model with the most complete abilities from model array
   * Combines the most complete abilities and largest contextWindowTokens
   */
  private selectModelWithBestAbilities = (models: DiscoverModelItem[]): DiscoverModelItem => {
    log('selectModelWithBestAbilities: input models count=%d', models.length);
    if (models.length === 1) return models[0];

    // Find the most complete abilities
    let bestAbilities: Record<string, boolean> = {};
    let maxAbilitiesScore = 0;
    models.forEach((model) => {
      const score = this.calculateAbilitiesScore(model.abilities);
      if (score > maxAbilitiesScore) {
        maxAbilitiesScore = score;
        bestAbilities = { ...(model.abilities as Record<string, boolean>) };
      } else if (score === maxAbilitiesScore && model.abilities) {
        // Merge abilities with the same score to ensure the most complete combination
        const abilities = model.abilities as Record<string, boolean>;
        Object.keys(abilities).forEach((key) => {
          if (abilities[key]) {
            bestAbilities[key] = true;
          }
        });
      }
    });

    // Find the largest contextWindowTokens
    const maxContextWindowTokens = Math.max(
      ...models.map((model) => model.contextWindowTokens || 0),
    );

    // Find the latest releasedAt
    const latestReleasedAt = models
      .map((model) => model.releasedAt)
      .filter(Boolean)
      .sort((a, b) => new Date(b!).getTime() - new Date(a!).getTime())[0];

    // Find the shortest identifier
    const shortestIdentifier = models
      .map((model) => model.identifier)
      .reduce((shortest, current) => (current.length < shortest.length ? current : shortest));

    // Select a base model (usually the first one)
    const baseModel = models[0];

    // Assemble final model using the best attributes
    const result: DiscoverModelItem = {
      ...baseModel,
      abilities: bestAbilities as any,
      contextWindowTokens: maxContextWindowTokens || baseModel.contextWindowTokens,
      identifier: shortestIdentifier,
      releasedAt: latestReleasedAt || baseModel.releasedAt,
    };

    log('selectModelWithBestAbilities: selected model=%O', {
      abilities: result.abilities,
      contextWindowTokens: result.contextWindowTokens,
      identifier: result.identifier,
      releasedAt: result.releasedAt,
    });
    return result;
  };

  private normalizeAuthorField = (author: unknown): { name: string; userName?: string } => {
    if (!author) return { name: '' };

    if (typeof author === 'string') return { name: author };

    if (typeof author === 'object') {
      const { avatar, url, name, userName } = author as {
        avatar?: unknown;
        name?: unknown;
        url?: unknown;
        userName?: unknown;
      };

      const authorName =
        (typeof name === 'string' && name.length > 0 && name) ||
        (typeof avatar === 'string' && avatar.length > 0 && avatar) ||
        (typeof url === 'string' && url.length > 0 && url) ||
        '';

      return {
        name: authorName,
        userName: typeof userName === 'string' ? userName : undefined,
      };
    }

    return { name: '' };
  };

  private isLegacySource = (source?: AssistantMarketSource) => source === 'legacy';

  private legacyGetAssistantListRaw = async (locale?: string): Promise<DiscoverAssistantItem[]> => {
    log('legacyGetAssistantListRaw: locale=%s', locale);
    const normalizedLocale = normalizeLocale(locale);
    const list = await this.assistantStore.getAgentIndex(normalizedLocale);
    if (!list || !Array.isArray(list)) {
      log('legacyGetAssistantListRaw: no valid list found, returning empty array');
      return [];
    }
    const result = list.map(({ meta, ...item }) => ({ ...item, ...meta }));
    log('legacyGetAssistantListRaw: returning %d items', result.length);
    return result;
  };

  private legacyGetAssistantCategories = async (
    params: CategoryListQuery = {},
  ): Promise<CategoryItem[]> => {
    log('legacyGetAssistantCategories: params=%O', params);
    const { q, locale } = params;
    let list = await this.legacyGetAssistantListRaw(locale);
    if (q) {
      const originalCount = list.length;
      list = list.filter((item) => {
        return [item.author, item.title, item.description, item?.tags]
          .flat()
          .filter(Boolean)
          .join(',')
          .toLowerCase()
          .includes(decodeURIComponent(q).toLowerCase());
      });
      log(
        'legacyGetAssistantCategories: filtered by query "%s", %d -> %d items',
        q,
        originalCount,
        list.length,
      );
    }
    const categoryCounts = countBy(list, (item) => item.category);
    const result = Object.entries(categoryCounts)
      .filter(([category]) => Boolean(category))
      .map(([category, count]) => ({
        category,
        count,
      }));
    log('legacyGetAssistantCategories: returning %d categories', result.length);
    return result;
  };

  private legacyGetAssistantDetail = async (params: {
    identifier: string;
    locale?: string;
    version?: string;
  }): Promise<DiscoverAssistantDetail | undefined> => {
    log('legacyGetAssistantDetail: params=%O', params);
    const { locale, identifier } = params;
    const normalizedLocale = normalizeLocale(locale);
    const data = await this.assistantStore.getAgent(identifier, normalizedLocale);
    if (!data) {
      log('legacyGetAssistantDetail: assistant not found for identifier=%s', identifier);
      return;
    }
    const { meta, ...item } = data;
    const assistant = merge(cloneDeep(DEFAULT_DISCOVER_ASSISTANT_ITEM), { ...item, ...meta });
    const list = await this.getAssistantList({
      category: assistant.category,
      includeAgentGroup: true,
      locale,
      page: 1,
      pageSize: 7,
      source: 'legacy',
    });
    const result = {
      ...assistant,
      related: list.items.filter((item) => item.identifier !== assistant.identifier).slice(0, 6),
    };
    log(
      'legacyGetAssistantDetail: returning assistant with %d related items',
      result.related.length,
    );
    return result;
  };

  private legacyGetAssistantIdentifiers = async (): Promise<IdentifiersResponse> => {
    log('legacyGetAssistantIdentifiers: fetching identifiers');
    const list = await this.legacyGetAssistantListRaw();
    const result = list.map((item) => {
      return {
        identifier: item.identifier,
        lastModified: item.createdAt,
      };
    });
    log('legacyGetAssistantIdentifiers: returning %d identifiers', result.length);
    return result;
  };

  private legacyGetAssistantList = async (
    params: AssistantQueryParams = {},
  ): Promise<AssistantListResponse> => {
    log('legacyGetAssistantList: params=%O', params);
    const {
      locale,
      category,
      order = 'desc',
      page = 1,
      pageSize = 20,
      q,
      sort = AssistantSorts.Recommended,
      ownerId,
    } = params;
    const currentPage = Number(page) || 1;
    const currentPageSize = Number(pageSize) || 20;

    if (ownerId) {
      log('legacyGetAssistantList: ownerId filter not supported in legacy source');
      return {
        currentPage,
        items: [],
        pageSize: currentPageSize,
        totalCount: 0,
        totalPages: 0,
      };
    }

    let list = await this.legacyGetAssistantListRaw(locale);
    const originalCount = list.length;

    if (category) {
      list = list.filter((item) => item.category === category);
      log(
        'legacyGetAssistantList: filtered by category "%s", %d -> %d items',
        category,
        originalCount,
        list.length,
      );
    }

    if (q) {
      const beforeFilter = list.length;
      list = list.filter((item) => {
        return [item.author, item.title, item.description, item?.tags]
          .flat()
          .filter(Boolean)
          .join(',')
          .toLowerCase()
          .includes(decodeURIComponent(q).toLowerCase());
      });
      log(
        'legacyGetAssistantList: filtered by query "%s", %d -> %d items',
        q,
        beforeFilter,
        list.length,
      );
    }

    if (sort) {
      log('legacyGetAssistantList: sorting by %s %s', sort, order);
      switch (sort) {
        case AssistantSorts.UpdatedAt: {
          // Legacy source doesn't have updatedAt, fallback to createdAt
          list = list.sort((a, b) => {
            if (order === 'asc') {
              return dayjs(a.createdAt).unix() - dayjs(b.createdAt).unix();
            } else {
              return dayjs(b.createdAt).unix() - dayjs(a.createdAt).unix();
            }
          });
          break;
        }
        default: {
          // Legacy source doesn't support these sorts (MostUsage, HaveSkills, Recommended), keep original order
          break;
        }
      }
    }

    const start = (currentPage - 1) * currentPageSize;
    const end = currentPage * currentPageSize;
    const result = {
      currentPage,
      items: list.slice(start, end),
      pageSize: currentPageSize,
      totalCount: list.length,
      totalPages: Math.ceil(list.length / currentPageSize),
    };
    log(
      'legacyGetAssistantList: returning page %d/%d with %d items',
      currentPage,
      result.totalPages,
      result.items.length,
    );
    return result;
  };

  // ============================== Assistant Market ==============================

  getAssistantCategories = async (
    params: CategoryListQuery & { source?: AssistantMarketSource } = {},
  ): Promise<CategoryItem[]> => {
    log('getAssistantCategories: params=%O', params);
    const { source, ...rest } = params;
    if (this.isLegacySource(source)) {
      return this.legacyGetAssistantCategories(rest);
    }

    const { q, locale } = rest;
    const normalizedLocale = normalizeLocale(locale);

    try {
      // @ts-ignore
      const categories = await this.market.agents.getCategories({
        locale: normalizedLocale,
        q,
      });
      log('getAssistantCategories: returning %d categories from market SDK', categories.length);
      return categories;
    } catch (error) {
      log('getAssistantCategories: error fetching from market SDK: %O', error);
      return [];
    }
  };

  getAssistantDetail = async (params: {
    identifier: string;
    locale?: string;
    source?: AssistantMarketSource;
    version?: string;
  }): Promise<DiscoverAssistantDetail | undefined> => {
    log('getAssistantDetail: params=%O', params);
    const { source, ...rest } = params;
    if (this.isLegacySource(source)) {
      return this.legacyGetAssistantDetail(rest);
    }

    const { locale, identifier, version } = rest;
    const normalizedLocale = normalizeLocale(locale);

    try {
      // @ts-ignore
      const data = await this.market.agents.getAgentDetail(identifier, {
        locale: normalizedLocale,
        version,
      });

      if (!data) {
        log('getAssistantDetail: assistant not found for identifier=%s', identifier);
        return;
      }

      const normalizedAuthor = this.normalizeAuthorField(data.author);
      const assistant = {
        author:
          normalizedAuthor.name || (data.ownerId !== null ? `User${data.ownerId}` : 'Unknown'),
        avatar: data.avatar || normalizedAuthor.name || '',
        category: (data as any).category || 'general',
        config: data.config || {},
        createdAt: (data as any).createdAt,
        currentVersion: data.version,
        description: (data as any).description || data.summary,
        // @ts-ignore
        editorData: data.editorData || {},

        examples: Array.isArray((data as any).examples)
          ? (data as any).examples.map((example: any) => ({
              content: typeof example === 'string' ? example : example.content || '',
              role: example.role || 'user',
            }))
          : [],
        forkCount: (data as any).forkCount,
        forkedFromAgentId: (data as any).forkedFromAgentId,
        homepage:
          (data as any).homepage ||
          `https://lobehub.com/discover/assistant/${(data as any).identifier}`,
        identifier: (data as any).identifier,
        isValidated: (data as any).isValidated,
        knowledgeCount:
          (data.config as any)?.knowledgeBases?.length || (data as any).knowledgeCount || 0,
        pluginCount: (data.config as any)?.plugins?.length || (data as any).pluginCount || 0,
        readme: data.documentationUrl || '',
        schemaVersion: 1,
        status: (data.status as AgentStatus) || undefined,
        summary: data.summary || '',
        systemRole: (data.config as any)?.systemRole || '',
        tags: data.tags || [],
        title: (data as any).name || (data as any).identifier,
        tokenUsage: data.tokenUsage || 0,
        userName: normalizedAuthor.userName,
        versions:
          // @ts-ignore
          data.versions?.map((item) => ({
            createdAt: (item as any).createdAt || item.updatedAt,
            isLatest: item.isLatest,
            isValidated: item.isValidated,
            status: item.status as any,
            version: item.version,
          })) || [],
      };

      // Get related assistants
      const list = await this.getAssistantList({
        category: assistant.category,
        includeAgentGroup: true,
        locale,
        page: 1,
        pageSize: 7,
        source,
      });

      const result = {
        ...assistant,
        related: list.items.filter((item) => item.identifier !== assistant.identifier).slice(0, 6),
      };

      log('getAssistantDetail: returning assistant with %d related items', result.related.length);
      return result;
    } catch (error) {
      log('getAssistantDetail: error fetching from market SDK: %O', error);
      return;
    }
  };

  getAssistantIdentifiers = async (
    params: { source?: AssistantMarketSource } = {},
  ): Promise<IdentifiersResponse> => {
    log('getAssistantIdentifiers: fetching identifiers with params=%O', params);
    if (this.isLegacySource(params.source)) {
      return this.legacyGetAssistantIdentifiers();
    }

    try {
      // @ts-ignore
      const identifiers = await this.market.agents.getPublishedIdentifiers();
      // @ts-ignore
      const result = identifiers.map((item) => ({
        identifier: item.id,
        lastModified: item.lastModified,
      }));
      log('getAssistantIdentifiers: returning %d identifiers from market SDK', result.length);
      return result;
    } catch (error) {
      log('getAssistantIdentifiers: error fetching from market SDK: %O', error);
      return [];
    }
  };

  getAssistantList = async (params: AssistantQueryParams = {}): Promise<AssistantListResponse> => {
    log('getAssistantList: params=%O', params);
    const { source, ...rest } = params;
    if (this.isLegacySource(source)) {
      return this.legacyGetAssistantList(rest);
    }

    const {
      locale,
      category,
      order = 'desc',
      page = 1,
      pageSize = 20,
      q,
      sort = AssistantSorts.Recommended,
      ownerId,
      includeAgentGroup,
    } = rest;
    const shouldOmitCategory = [AssistantCategory.All, AssistantCategory.Discover].includes(
      category as AssistantCategory,
    );

    try {
      const normalizedLocale = normalizeLocale(locale);

      let apiSort: 'createdAt' | 'updatedAt' | 'name' | 'mostUsage' | 'recommended' = 'recommended';
      let haveSkills: boolean | undefined = rest.haveSkills;

      switch (sort) {
        case AssistantSorts.UpdatedAt: {
          apiSort = 'updatedAt';
          break;
        }
        case AssistantSorts.MostUsage: {
          apiSort
```
