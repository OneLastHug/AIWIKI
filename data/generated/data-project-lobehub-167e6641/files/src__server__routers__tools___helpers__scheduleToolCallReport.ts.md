# 文件：src/server/routers/tools/_helpers/scheduleToolCallReport.ts

## 文件职责
这个文件位于 `src/server/routers/tools/_helpers`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { CURRENT_VERSION } from '@lobechat/const';
import { type CallReportRequest } from '@lobehub/market-types';
import { after } from 'next/server';
import { DiscoverService } from '@/server/services/discover';
export interface ToolCallReportMeta {
export interface ScheduleToolCallReportParams {
export function scheduleToolCallReport(params: ScheduleToolCallReportParams): void {
```

## 主要对外内容
```text
const calculateObjectSizeBytes = (obj: unknown): number => {
export interface ToolCallReportMeta {
export interface ScheduleToolCallReportParams {
export function scheduleToolCallReport(params: ScheduleToolCallReportParams): void {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { CURRENT_VERSION } from '@lobechat/const';
import { type CallReportRequest } from '@lobehub/market-types';
import { after } from 'next/server';

import { DiscoverService } from '@/server/services/discover';

/**
 * Calculate byte size of object
 */
const calculateObjectSizeBytes = (obj: unknown): number => {
  try {
    const jsonString = JSON.stringify(obj);
    return new TextEncoder().encode(jsonString).length;
  } catch {
    return 0;
  }
};

export interface ToolCallReportMeta {
  customPluginInfo?: {
    avatar?: string;
    description?: string;
    name?: string;
  };
  isCustomPlugin?: boolean;
  sessionId?: string;
  version?: string;
}

export interface ScheduleToolCallReportParams {
  /** Error code if call failed */
  errorCode?: string;
  /** Error message if call failed */
  errorMessage?: string;
  /** Plugin/tool identifier */
  identifier: string;
  /** Market access token for reporting */
  marketAccessToken?: string;
  /** MCP connection type */
  mcpType: string;
  /** Metadata for reporting */
  meta?: ToolCallReportMeta;
  /** Request payload for size calculation */
  requestPayload: unknown;
  /** Result for size calculation */
  result?: unknown;
  /** Start time of the call */
  startTime: number;
  /** Whether the call was successful */
  success: boolean;
  /** Whether telemetry is enabled */
  telemetryEnabled: boolean;
  /** Tool/method name */
  toolName: string;
}

/**
 * Schedule a tool call report to be sent after the response.
 * Uses Next.js after() to avoid blocking the response.
 */
export function scheduleToolCallReport(params: ScheduleToolCallReportParams): void {
  const {
    telemetryEnabled,
    marketAccessToken,
    startTime,
    success,
    errorCode,
    errorMessage,
    result,
    meta,
    identifier,
    toolName,
    mcpType,
    requestPayload,
  } = params;

  // Only report when telemetry is enabled and marketAccessToken exists
  if (!telemetryEnabled || !marketAccessToken) return;

  // Use Next.js after() to report after response is sent
  after(async () => {
    try {
      const callDurationMs = Date.now() - startTime;
      const requestSizeBytes = calculateObjectSizeBytes(requestPayload);
      const responseSizeBytes = success && result ? calculateObjectSizeBytes(result) : 0;

      const reportData: CallReportRequest = {
        callDurationMs,
        customPluginInfo: meta?.customPluginInfo,
        errorCode,
        errorMessage,
        identifier,
        isCustomPlugin: meta?.isCustomPlugin,
        metadata: {
          appVersion: CURRENT_VERSION,
          mcpType,
        },
        methodName: toolName,
        methodType: 'tool',
        requestSizeBytes,
        responseSizeBytes,
        sessionId: meta?.sessionId,
        success,
        version: meta?.version || 'unknown',
      };

      const discoverService = new DiscoverService({ accessToken: marketAccessToken });
      await discoverService.reportCall(reportData);
    } catch (reportError) {
      console.error('Failed to report tool call: %O', reportError);
    }
  });
}

```
