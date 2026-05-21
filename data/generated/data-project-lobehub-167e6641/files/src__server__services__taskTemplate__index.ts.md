# 文件：src/server/services/taskTemplate/index.ts

## 文件职责
这个文件位于 `src/server/services/taskTemplate`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { TaskTemplate, TaskTemplateSkillSource } from '@lobechat/const';
import {
import { klavisEnv } from '@/config/klavis';
import { appEnv } from '@/envs/app';
export const ENABLED_SKILL_SOURCES: ReadonlySet<TaskTemplateSkillSource> = (() => {
export const isTemplateSkillSourceEligible = (
export class TaskTemplateService {
```

## 主要对外内容
```text
export const ENABLED_SKILL_SOURCES: ReadonlySet<TaskTemplateSkillSource> = (() => {
const hashString = (str: string): number => {
const mulberry32 = (seed: number) => {
const seededShuffle = <T>(items: T[], seed: number): T[] => {
const normalize = (s: string) => s.trim().toLowerCase();
const hasIntersection = (template: TaskTemplate, userInterests: string[]): boolean => {
const getUtcDateStr = (now: Date): string => now.toISOString().slice(0, 10);
export const isTemplateSkillSourceEligible = (
export class TaskTemplateService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { TaskTemplate, TaskTemplateSkillSource } from '@lobechat/const';
import {
  TASK_TEMPLATE_FALLBACK_CATEGORIES,
  TASK_TEMPLATE_RECOMMEND_COUNT,
  taskTemplates,
} from '@lobechat/const';

import { klavisEnv } from '@/config/klavis';
import { appEnv } from '@/envs/app';

export const ENABLED_SKILL_SOURCES: ReadonlySet<TaskTemplateSkillSource> = (() => {
  const sources = new Set<TaskTemplateSkillSource>();
  if (klavisEnv.KLAVIS_API_KEY) sources.add('klavis');
  if (appEnv.MARKET_TRUSTED_CLIENT_ID && appEnv.MARKET_TRUSTED_CLIENT_SECRET) {
    sources.add('lobehub');
  }
  return sources;
})();

const hashString = (str: string): number => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
  }
  return hash >>> 0;
};

/** mulberry32 — pure function of seed, used so recommendations are stable per user/day. */
const mulberry32 = (seed: number) => {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d_2b_79_f5) | 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4_294_967_296;
  };
};

const seededShuffle = <T>(items: T[], seed: number): T[] => {
  const arr = [...items];
  const rand = mulberry32(seed);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
};

const normalize = (s: string) => s.trim().toLowerCase();

const hasIntersection = (template: TaskTemplate, userInterests: string[]): boolean => {
  if (userInterests.length === 0) return false;
  const normalized = new Set(userInterests.map(normalize));
  return template.interests.some((i) => normalized.has(normalize(i)));
};

const getUtcDateStr = (now: Date): string => now.toISOString().slice(0, 10);

/**
 * A template is eligible only if every `requiresSkills[].source` is enabled
 * server-side. When a template declares no skill requirement, it is always
 * eligible. When the caller passes no `enabledSkillSources` set, any template
 * with skill requirements is filtered out (conservative default).
 */
export const isTemplateSkillSourceEligible = (
  template: TaskTemplate,
  enabledSkillSources?: ReadonlySet<TaskTemplateSkillSource>,
): boolean => {
  if (!template.requiresSkills || template.requiresSkills.length === 0) return true;
  if (!enabledSkillSources) return false;
  return template.requiresSkills.every((s) => enabledSkillSources.has(s.source));
};

export class TaskTemplateService {
  constructor(private userId: string) {}

  async listDailyRecommend(
    interestKeys: string[],
    options: {
      count?: number;
      enabledSkillSources?: ReadonlySet<TaskTemplateSkillSource>;
      excludeIds?: string[];
      now?: Date;
      refreshSeed?: string;
    } = {},
  ): Promise<TaskTemplate[]> {
    const {
      count = TASK_TEMPLATE_RECOMMEND_COUNT,
      enabledSkillSources,
      excludeIds,
      now = new Date(),
      refreshSeed,
    } = options;
    const limit = Math.max(1, count);
    const excluded = new Set(excludeIds ?? []);
    const seedBase = `${this.userId}:${getUtcDateStr(now)}`;
    const seed = hashString(refreshSeed ? `${seedBase}:${refreshSeed}` : seedBase);

    const candidates = taskTemplates.filter(
      (t) => !excluded.has(t.id) && isTemplateSkillSourceEligible(t, enabledSkillSources),
    );
    const matched = candidates.filter((t) => hasIntersection(t, interestKeys));
    const result: TaskTemplate[] = [];

    if (matched.length >= limit) {
      result.push(...seededShuffle(matched, seed).slice(0, limit));
    } else {
      // Not enough interest matches: fold the fallback pool in so refreshSeed
      // can reorder the whole batch — otherwise a single-match interest pins
      // that template to position 0 forever.
      const matchedIds = new Set(matched.map((t) => t.id));
      const fallback = candidates.filter(
        (t) => TASK_TEMPLATE_FALLBACK_CATEGORIES.includes(t.category) && !matchedIds.has(t.id),
      );
      const pool = [...matched, ...fallback];
      result.push(...seededShuffle(pool, seed).slice(0, limit));
    }

    if (result.length < limit) {
      const seen = new Set(result.map((t) => t.id));
      const remaining = candidates.filter((t) => !seen.has(t.id));
      result.push(...seededShuffle(remaining, seed).slice(0, limit - result.length));
    }

    return result;
  }
}

```
