# 文件：src/server/services/comfyui/errors/modelResolverError.ts

## 文件职责
这个文件位于 `src/server/services/comfyui/errors`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
export class ModelResolverError extends Error {
```

## 主要对外内容
```text
export class ModelResolverError extends Error {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
/**
 * Model Resolver Error
 *
 * Error class for model resolution failures
 * Simplified after moving main logic to service layer
 */

/**
 * Internal error class for model resolver
 *
 * This error is thrown by model resolver when it cannot find models
 * or encounters issues with the ComfyUI server.
 * It will be caught and converted to framework errors at the main entry level.
 */
export class ModelResolverError extends Error {
  public readonly reason: string;
  public readonly details?: Record<string, any>;

  constructor(reason: string, message: string, details?: Record<string, any>) {
    super(message);
    this.name = 'ModelResolverError';
    this.reason = reason;
    this.details = details;

    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ModelResolverError);
    }
  }

  static readonly Reasons = {
    COMPONENT_NOT_FOUND: 'COMPONENT_NOT_FOUND',
    CONNECTION_ERROR: 'CONNECTION_ERROR',
    INVALID_API_KEY: 'INVALID_API_KEY',
    INVALID_MODEL_FORMAT: 'INVALID_MODEL_FORMAT',
    MODEL_NOT_FOUND: 'MODEL_NOT_FOUND',
    NO_MODELS_AVAILABLE: 'NO_MODELS_AVAILABLE',
    PERMISSION_DENIED: 'PERMISSION_DENIED',
    SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  } as const;
}

```
