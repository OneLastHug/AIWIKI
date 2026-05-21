# 文件：src/server/services/toolExecution/serverRuntimes/index.ts

## 文件职责
这个文件位于 `src/server/services/toolExecution/serverRuntimes`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { ToolExecutionContext } from '../types';
import { activatorRuntime } from './activator';
import { agentDocumentsRuntime } from './agentDocuments';
import { agentManagementRuntime } from './agentManagement';
import { briefRuntime } from './brief';
import { calculatorRuntime } from './calculator';
import { cloudSandboxRuntime } from './cloudSandbox';
import { credsRuntime } from './creds';
import { knowledgeBaseRuntime } from './knowledgeBase';
import { lobeAgentRuntime } from './lobeAgent';
import { localSystemRuntime } from './localSystem';
import { memoryRuntime } from './memory';
import { messageRuntime } from './message';
import { notebookRuntime } from './notebook';
import { remoteDeviceRuntime } from './remoteDevice';
import { selfFeedbackIntentRuntime } from './selfFeedbackIntent';
import { skillManagementRuntime } from './skillManagement';
import { skillsRuntime } from './skills';
import { skillStoreRuntime } from './skillStore';
import { taskRuntime } from './task';
import { topicReferenceRuntime } from './topicReference';
import type { ServerRuntimeFactory, ServerRuntimeRegistration } from './types';
import { userInteractionRuntime } from './userInteraction';
import { webBrowsingRuntime } from './webBrowsing';
import { webOnboardingRuntime } from './webOnboarding';
export const getServerRuntime = (
export const hasServerRuntime = (identifier: string): boolean => {
export const getServerRuntimeIdentifiers = (): string[] => {
```

## 主要对外内容
```text
const serverRuntimeFactories = new Map<string, ServerRuntimeFactory>();
const registerRuntimes = (runtimes: ServerRuntimeRegistration[]) => {
export const getServerRuntime = (
export const hasServerRuntime = (identifier: string): boolean => {
export const getServerRuntimeIdentifiers = (): string[] => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
/**
 * Server Runtime Registry
 *
 * Central registry for all builtin tool server runtimes.
 * Uses factory functions to support both:
 * - Pre-instantiated runtimes (e.g., WebBrowsing - no per-request context needed)
 * - Per-request runtimes (e.g., CloudSandbox - needs topicId, userId)
 */
import type { ToolExecutionContext } from '../types';
import { activatorRuntime } from './activator';
import { agentDocumentsRuntime } from './agentDocuments';
import { agentManagementRuntime } from './agentManagement';
import { briefRuntime } from './brief';
import { calculatorRuntime } from './calculator';
import { cloudSandboxRuntime } from './cloudSandbox';
import { credsRuntime } from './creds';
import { knowledgeBaseRuntime } from './knowledgeBase';
import { lobeAgentRuntime } from './lobeAgent';
import { localSystemRuntime } from './localSystem';
import { memoryRuntime } from './memory';
import { messageRuntime } from './message';
import { notebookRuntime } from './notebook';
import { remoteDeviceRuntime } from './remoteDevice';
import { selfFeedbackIntentRuntime } from './selfFeedbackIntent';
import { skillManagementRuntime } from './skillManagement';
import { skillsRuntime } from './skills';
import { skillStoreRuntime } from './skillStore';
import { taskRuntime } from './task';
import { topicReferenceRuntime } from './topicReference';
import type { ServerRuntimeFactory, ServerRuntimeRegistration } from './types';
import { userInteractionRuntime } from './userInteraction';
import { webBrowsingRuntime } from './webBrowsing';
import { webOnboardingRuntime } from './webOnboarding';

/**
 * Registry of server runtime factories by identifier
 */
const serverRuntimeFactories = new Map<string, ServerRuntimeFactory>();

/**
 * Register server runtimes
 */
const registerRuntimes = (runtimes: ServerRuntimeRegistration[]) => {
  for (const runtime of runtimes) {
    serverRuntimeFactories.set(runtime.identifier, runtime.factory);
  }
};

// Register all server runtimes
registerRuntimes([
  webBrowsingRuntime,
  cloudSandboxRuntime,
  calculatorRuntime,
  agentDocumentsRuntime,
  agentManagementRuntime,
  skillManagementRuntime,
  notebookRuntime,
  skillStoreRuntime,
  skillsRuntime,
  memoryRuntime,
  activatorRuntime,
  messageRuntime,
  localSystemRuntime,
  remoteDeviceRuntime,
  briefRuntime,
  taskRuntime,
  topicReferenceRuntime,
  userInteractionRuntime,
  credsRuntime,
  knowledgeBaseRuntime,
  webOnboardingRuntime,
  lobeAgentRuntime,
  selfFeedbackIntentRuntime,
]);

// ==================== Registry API ====================

/**
 * Get a server runtime by identifier
 * @param identifier - The tool identifier
 * @param context - Execution context (required for per-request runtimes)
 * @returns Runtime instance (may be a Promise for async factories)
 */
export const getServerRuntime = (
  identifier: string,
  context: ToolExecutionContext,
): any | Promise<any> => {
  const factory = serverRuntimeFactories.get(identifier);
  return factory?.(context);
};

/**
 * Check if a server runtime exists for the given identifier
 */
export const hasServerRuntime = (identifier: string): boolean => {
  return serverRuntimeFactories.has(identifier);
};

/**
 * Get all registered server runtime identifiers
 */
export const getServerRuntimeIdentifiers = (): string[] => {
  return Array.from(serverRuntimeFactories.keys());
};

```
