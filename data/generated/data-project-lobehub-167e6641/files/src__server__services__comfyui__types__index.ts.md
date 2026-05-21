# 文件：src/server/services/comfyui/types/index.ts

## 文件职责
这个文件位于 `src/server/services/comfyui/types`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type ComfyUIKeyVault } from '@lobechat/types';
export interface ComfyUIServiceConfig {
export interface WorkflowBuildParams {
export interface WorkflowContext {
export interface ProcessedImageResult {
export interface ImagePreprocessOptions {
```

## 主要对外内容
```text
export interface ComfyUIServiceConfig {
export interface WorkflowBuildParams {
export interface WorkflowContext {
export interface ProcessedImageResult {
export interface ImagePreprocessOptions {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type ComfyUIKeyVault } from '@lobechat/types';

export interface ComfyUIServiceConfig {
  baseURL: string;
  cacheTTL?: number;
  connectionTimeout?: number;
  enableCache?: boolean;
  enableDebug?: boolean;
  keyVault: ComfyUIKeyVault;
  maxRetries?: number;
}

export interface WorkflowBuildParams {
  cfgScale?: number;
  height?: number;
  imageUrl?: string;
  model?: string;
  prompt: string;
  seed?: number;
  steps?: number;
  strength?: number; // Standard parameter for image modification strength
  width?: number;
}

export interface WorkflowContext {
  clientService: any;
  modelResolverService: any;
}

export interface ProcessedImageResult {
  buffer: Buffer;
  format: string;
  height: number;
  size: number;
  width: number;
}

export interface ImagePreprocessOptions {
  format?: string;
  targetHeight?: number;
  targetWidth?: number;
}

```
