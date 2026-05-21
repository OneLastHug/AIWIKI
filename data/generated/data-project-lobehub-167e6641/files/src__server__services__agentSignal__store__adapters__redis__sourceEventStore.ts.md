# 文件：src/server/services/agentSignal/store/adapters/redis/sourceEventStore.ts

## 文件职责
这个文件位于 `src/server/services/agentSignal/store/adapters/redis`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { AGENT_SIGNAL_KEYS } from '../../../constants';
import type { AgentSignalSourceEventStore } from '../../types';
import { getRedisClient, readHash, trySetNx, writeHash } from './shared';
export const tryDedupe = async (eventId: string, ttlSeconds: number) => {
export const readWindow = async (scopeKey: string) => {
export const writeWindow = async (
export const acquireScopeLock = async (scopeKey: string, ttlSeconds: number) => {
export const releaseScopeLock = async (scopeKey: string) => {
export const redisSourceEventStore: AgentSignalSourceEventStore = {
```

## 主要对外内容
```text
export const tryDedupe = async (eventId: string, ttlSeconds: number) => {
export const readWindow = async (scopeKey: string) => {
export const writeWindow = async (
export const acquireScopeLock = async (scopeKey: string, ttlSeconds: number) => {
export const releaseScopeLock = async (scopeKey: string) => {
export const redisSourceEventStore: AgentSignalSourceEventStore = {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { AGENT_SIGNAL_KEYS } from '../../../constants';
import type { AgentSignalSourceEventStore } from '../../types';
import { getRedisClient, readHash, trySetNx, writeHash } from './shared';

/** Accepts one source-event id once within the configured TTL window. */
export const tryDedupe = async (eventId: string, ttlSeconds: number) => {
  return trySetNx(AGENT_SIGNAL_KEYS.dedupe(eventId), ttlSeconds);
};

/** Reads one persisted source-event window snapshot. */
export const readWindow = async (scopeKey: string) => {
  return readHash(AGENT_SIGNAL_KEYS.window(scopeKey));
};

/** Writes one persisted source-event window snapshot. */
export const writeWindow = async (
  scopeKey: string,
  data: Record<string, string>,
  ttlSeconds: number,
) => {
  await writeHash(AGENT_SIGNAL_KEYS.window(scopeKey), data, ttlSeconds);
};

/** Acquires the short-lived source-generation lock for one scope. */
export const acquireScopeLock = async (scopeKey: string, ttlSeconds: number) => {
  return trySetNx(AGENT_SIGNAL_KEYS.lock(scopeKey), ttlSeconds);
};

/** Releases the short-lived source-generation lock for one scope. */
export const releaseScopeLock = async (scopeKey: string) => {
  const redis = getRedisClient();
  if (!redis) return;

  await redis.del(AGENT_SIGNAL_KEYS.lock(scopeKey));
};

/** Redis-backed source-event store used by generation. */
export const redisSourceEventStore: AgentSignalSourceEventStore = {
  acquireScopeLock,
  readWindow,
  releaseScopeLock,
  tryDedupe,
  writeWindow,
};

```
