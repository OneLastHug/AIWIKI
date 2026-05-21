# 文件：src/server/services/comfyui/config/modelRegistry.ts

## 文件职责
这个文件位于 `src/server/services/comfyui/config`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { FLUX_MODEL_REGISTRY } from './fluxModelRegistry';
import { SD_MODEL_REGISTRY } from './sdModelRegistry';
export interface ModelConfig {
export const MODEL_REGISTRY: Record<string, ModelConfig> = {
export const MODEL_ID_VARIANT_MAP: Record<string, string> = {
```

## 主要对外内容
```text
export interface ModelConfig {
export const MODEL_REGISTRY: Record<string, ModelConfig> = {
export const MODEL_ID_VARIANT_MAP: Record<string, string> = {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
/**
 * ComfyUI Model Registry - Linus-style simple design
 * Interface shared, registries split for maintainability
 */
import { FLUX_MODEL_REGISTRY } from './fluxModelRegistry';
import { SD_MODEL_REGISTRY } from './sdModelRegistry';

export interface ModelConfig {
  modelFamily: string;
  priority: number;
  recommendedDtype?: 'default' | 'fp8_e4m3fn' | 'fp8_e4m3fn_fast' | 'fp8_e5m2';
  variant: string;
}

// ===================================================================
// Combined Model Registry - FLUX + SD families
// ===================================================================

export const MODEL_REGISTRY: Record<string, ModelConfig> = {
  ...FLUX_MODEL_REGISTRY,
  ...SD_MODEL_REGISTRY,
};

/**
 * Model ID to Variant mapping
 * Maps actual frontend model IDs to their corresponding variants in registry
 * Based on src/config/aiModels/comfyui.ts definitions
 */
export const MODEL_ID_VARIANT_MAP: Record<string, string> = {
  // FLUX models
  'flux-schnell': 'schnell', // comfyui/flux-schnell
  'flux-dev': 'dev', // comfyui/flux-dev
  'flux-krea-dev': 'krea', // comfyui/flux-krea-dev
  'flux-kontext-dev': 'kontext', // comfyui/flux-kontext-dev

  // SD3 models
  'stable-diffusion-35': 'sd35', // comfyui/stable-diffusion-35
  'stable-diffusion-35-inclclip': 'sd35-inclclip', // comfyui/stable-diffusion-35-inclclip

  // SD1/SDXL models
  'stable-diffusion-15': 'sd15-t2i', // comfyui/stable-diffusion-15
  'stable-diffusion-xl': 'sdxl-t2i', // comfyui/stable-diffusion-xl
  'stable-diffusion-refiner': 'sdxl-i2i', // comfyui/stable-diffusion-refiner
  'stable-diffusion-custom': 'custom-sd', // comfyui/stable-diffusion-custom
  'stable-diffusion-custom-refiner': 'custom-sd', // comfyui/stable-diffusion-custom-refiner
};

```
