# 文件：src/server/services/agentSignal/store/adapters/redis/shared.ts

## 文件职责
这个文件位于 `src/server/services/agentSignal/store/adapters/redis`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type Redis from 'ioredis';
import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';
export type HashPayload = Record<string, string>;
export const getRedisClient = (): Redis | null => {
export const readHashFrom = async (
export const readHash = async (key: string): Promise<HashPayload | undefined> => {
export const getCasRedisClient = (): Redis | null => {
export const closeCasRedisClient = async (redis: Pick<Redis, 'quit'> | null) => {
export const writeHash = async (
export const trySetNx = async (key: string, ttlSeconds: number): Promise<boolean> => {
export const parseJsonField = <T>(value?: string): T | undefined => {
```

## 主要对外内容
```text
interface AgentSignalRedisGlobal {
export type HashPayload = Record<string, string>;
export const getRedisClient = (): Redis | null => {
export const readHashFrom = async (
export const readHash = async (key: string): Promise<HashPayload | undefined> => {
export const getCasRedisClient = (): Redis | null => {
export const closeCasRedisClient = async (redis: Pick<Redis, 'quit'> | null) => {
export const writeHash = async (
export const trySetNx = async (key: string, ttlSeconds: number): Promise<boolean> => {
export const parseJsonField = <T>(value?: string): T | undefined => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type Redis from 'ioredis';

import { getAgentRuntimeRedisClient } from '@/server/modules/AgentRuntime/redis';

interface AgentSignalRedisGlobal {
  __agentSignalRedisClient?: Redis | null;
}

export type HashPayload = Record<string, string>;

export const getRedisClient = (): Redis | null => {
  const testRedis = (globalThis as AgentSignalRedisGlobal).__agentSignalRedisClient;
  if (testRedis !== undefined) return testRedis;

  return getAgentRuntimeRedisClient();
};

export const readHashFrom = async (
  redis: Pick<Redis, 'hgetall'> | null,
  key: string,
): Promise<HashPayload | undefined> => {
  if (!redis) return undefined;

  const value = await redis.hgetall(key);
  if (!value || Object.keys(value).length === 0) return undefined;

  return value;
};

export const readHash = async (key: string): Promise<HashPayload | undefined> => {
  return readHashFrom(getRedisClient(), key);
};

export const getCasRedisClient = (): Redis | null => {
  const redis = getRedisClient();
  if (!redis) return null;

  return redis.duplicate();
};

export const closeCasRedisClient = async (redis: Pick<Redis, 'quit'> | null) => {
  if (!redis) return;

  await redis.quit();
};

export const writeHash = async (
  key: string,
  data: HashPayload,
  ttlSeconds: number,
): Promise<void> => {
  const redis = getRedisClient();
  if (!redis) return;
  if (Object.keys(data).length === 0) return;

  await redis.hset(key, data);
  await redis.expire(key, ttlSeconds);
};

export const trySetNx = async (key: string, ttlSeconds: number): Promise<boolean> => {
  const redis = getRedisClient();
  if (!redis) return false;

  const result = await redis.set(key, '1', 'EX', ttlSeconds, 'NX');
  return result === 'OK';
};

export const parseJsonField = <T>(value?: string): T | undefined => {
  if (!value) return undefined;

  return JSON.parse(value) as T;
};

```
