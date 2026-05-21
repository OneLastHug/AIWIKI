# 文件：src/server/services/agentSignal/store/types.ts

## 文件职责
这个文件位于 `src/server/services/agentSignal/store`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { AgentSignalReceiptStore } from '../services/receiptService';
export interface AgentSignalPolicyStatePayload {
export interface AgentSignalSourceEventWindowPayload {
export interface AgentSignalPolicyStateStore {
export interface AgentSignalSourceEventStore {
export type { AgentSignalReceiptStore };
```

## 主要对外内容
```text
export interface AgentSignalPolicyStatePayload {
export interface AgentSignalSourceEventWindowPayload {
export interface AgentSignalPolicyStateStore {
export interface AgentSignalSourceEventStore {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { AgentSignalReceiptStore } from '../services/receiptService';

/** Persisted policy-state payload for one AgentSignal scope. */
export interface AgentSignalPolicyStatePayload {
  [key: string]: string;
}

/** Persisted source-event window payload for one AgentSignal scope. */
export interface AgentSignalSourceEventWindowPayload {
  [key: string]: string;
}

/** Storage contract for policy-scoped AgentSignal state. */
export interface AgentSignalPolicyStateStore {
  readPolicyState: (
    policyId: string,
    scopeKey: string,
  ) => Promise<AgentSignalPolicyStatePayload | undefined>;
  writePolicyState: (
    policyId: string,
    scopeKey: string,
    data: AgentSignalPolicyStatePayload,
    ttlSeconds: number,
  ) => Promise<void>;
}

/** Storage contract for AgentSignal source-event generation state. */
export interface AgentSignalSourceEventStore {
  acquireScopeLock: (scopeKey: string, ttlSeconds: number) => Promise<boolean>;
  readWindow: (scopeKey: string) => Promise<AgentSignalSourceEventWindowPayload | undefined>;
  releaseScopeLock: (scopeKey: string) => Promise<void>;
  tryDedupe: (eventId: string, ttlSeconds: number) => Promise<boolean>;
  writeWindow: (
    scopeKey: string,
    data: AgentSignalSourceEventWindowPayload,
    ttlSeconds: number,
  ) => Promise<void>;
}

export type { AgentSignalReceiptStore };

```
