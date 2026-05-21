# 文件：src/server/services/riskControl/routerAlertNotification.ts

## 文件职责
这个文件位于 `src/server/services/riskControl`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
export interface ChannelStats {
export interface AlertThresholds {
export const shouldAlert = (_stats: ChannelStats, _thresholds: AlertThresholds): boolean => {
export const sendRouterChannelAlertNotification = async (_params: {
export const sendRouterModelAlertNotification = async (_params: {
```

## 主要对外内容
```text
export interface ChannelStats {
export interface AlertThresholds {
export const shouldAlert = (_stats: ChannelStats, _thresholds: AlertThresholds): boolean => {
export const sendRouterChannelAlertNotification = async (_params: {
export const sendRouterModelAlertNotification = async (_params: {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
export interface ChannelStats {
  errorCount: number;
  successCount: number;
  totalCount: number;
}

export interface AlertThresholds {
  errorRateThreshold: number;
  minSampleSize: number;
}

export const shouldAlert = (_stats: ChannelStats, _thresholds: AlertThresholds): boolean => {
  return false;
};

export const sendRouterChannelAlertNotification = async (_params: {
  channelId: string;
  model: string;
  routerId: string;
  stats: ChannelStats;
}): Promise<void> => {
  // Stub implementation
};

export const sendRouterModelAlertNotification = async (_params: {
  model: string;
  stats: ChannelStats;
}): Promise<void> => {
  // Stub implementation
};

```
