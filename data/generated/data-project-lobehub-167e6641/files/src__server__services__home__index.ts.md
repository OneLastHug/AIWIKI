# 文件：src/server/services/home/index.ts

## 文件职责
这个文件位于 `src/server/services/home`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import debug from 'debug';
import { getRedisConfig } from '@/envs/redis';
import {
export interface HomeBriefPair {
export interface HomeBriefData {
export class HomeService {
```

## 主要对外内容
```text
const log = debug('lobe-server:home-service');
export interface HomeBriefPair {
export interface HomeBriefData {
export class HomeService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import debug from 'debug';

import { getRedisConfig } from '@/envs/redis';
import {
  getJSONFromRedis,
  initializeRedisWithPrefix,
  isRedisEnabled,
  RedisKeyNamespace,
  RedisKeys,
} from '@/libs/redis';

const log = debug('lobe-server:home-service');

export interface HomeBriefPair {
  hint: string;
  welcome: string;
}

export interface HomeBriefData {
  pairs: HomeBriefPair[];
}

/**
 * Home Service
 *
 * Encapsulates the read paths for surfaces on the home page that aren't
 * straight DB queries — currently the AI-generated daily brief cached in
 * Redis under `aiGeneration:home_brief:{userId}`.
 */
export class HomeService {
  private readonly userId: string;

  constructor(userId: string) {
    this.userId = userId;
  }

  /**
   * Read the cached daily brief for this user. Returns `{ pairs: [] }` when
   * Redis is disabled, the key is missing, or the payload is malformed —
   * callers can render unconditionally without a null check.
   */
  async getDailyBrief(): Promise<HomeBriefData> {
    const data = await this.readDailyBriefFromRedis();
    return data ?? { pairs: [] };
  }

  private async readDailyBriefFromRedis(): Promise<HomeBriefData | null> {
    try {
      const redisConfig = getRedisConfig();
      if (!isRedisEnabled(redisConfig)) return null;

      const redis = await initializeRedisWithPrefix(redisConfig, RedisKeyNamespace.AI_GENERATION);
      const data = await getJSONFromRedis<HomeBriefData>(
        redis,
        RedisKeys.aiGeneration.homeBrief(this.userId),
      );
      if (!data || !Array.isArray(data.pairs)) return null;
      return data;
    } catch (error) {
      log('Failed to read daily brief from Redis for user %s: %O', this.userId, error);
      return null;
    }
  }
}

```
