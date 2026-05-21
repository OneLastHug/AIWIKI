# 文件：src/server/services/queue/impls/index.ts

## 文件职责
这个文件位于 `src/server/services/queue/impls`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { appEnv } from '@/envs/app';
import { LocalQueueServiceImpl } from './local';
import { QStashQueueServiceImpl } from './qstash';
import { type QueueServiceImpl } from './type';
export const isQueueAgentRuntimeEnabled = (): boolean => {
export const createQueueServiceModule = (): QueueServiceImpl => {
export { LocalQueueServiceImpl } from './local';
export type { QueueServiceImpl } from './type';
```

## 主要对外内容
```text
export const isQueueAgentRuntimeEnabled = (): boolean => {
export const createQueueServiceModule = (): QueueServiceImpl => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { appEnv } from '@/envs/app';

import { LocalQueueServiceImpl } from './local';
import { QStashQueueServiceImpl } from './qstash';
import { type QueueServiceImpl } from './type';

/**
 * Check if queue-based agent runtime is enabled
 * Set via AGENT_RUNTIME_MODE=queue environment variable
 */
export const isQueueAgentRuntimeEnabled = (): boolean => {
  return appEnv.enableQueueAgentRuntime === true;
};

/**
 * Create queue service module
 *
 * When enableQueueAgentRuntime=true (AGENT_RUNTIME_MODE=queue):
 *   - QStashQueueServiceImpl (production, requires QSTASH_TOKEN)
 *
 * When enableQueueAgentRuntime=false (default):
 *   - LocalQueueServiceImpl (local development, uses setTimeout for async execution)
 */
export const createQueueServiceModule = (): QueueServiceImpl => {
  if (isQueueAgentRuntimeEnabled()) {
    const qstashToken = process.env.QSTASH_TOKEN;

    if (!qstashToken) {
      throw new Error('QSTASH_TOKEN is required when AGENT_RUNTIME_MODE=queue');
    }
    return new QStashQueueServiceImpl({ qstashToken });
  }

  // Local mode (default): use LocalQueueServiceImpl with callback mechanism
  return new LocalQueueServiceImpl();
};

export { LocalQueueServiceImpl } from './local';
export type { QueueServiceImpl } from './type';

```
