# 文件：src/server/services/comfyui/errors/index.ts

## 文件职责
这个文件位于 `src/server/services/comfyui/errors`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
export { ComfyUIInternalError } from './base';
export { ConfigError } from './configError';
export { ModelResolverError } from './modelResolverError';
export { ServicesError } from './servicesError';
export { UtilsError } from './utilsError';
export { WorkflowError } from './workflowError';
export { isComfyUIInternalError } from './typeGuards';
```

## 主要对外内容
```text
未在节选中发现明显导出的类型、函数或组件。
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
/**
 * ComfyUI Internal Error System
 *
 * All ComfyUI internal layers (config, workflow, utils, services) should use these
 * internal error classes instead of framework errors to maintain proper
 * architectural boundaries.
 *
 * File organization:
 * - base.ts: Base error class
 * - configError.ts: Configuration layer errors
 * - workflowError.ts: Workflow layer errors
 * - utilsError.ts: Utility layer errors
 * - servicesError.ts: Service layer errors
 * - modelResolverError.ts: Model resolver specific errors
 * - typeGuards.ts: Type guard utilities
 */

// Base class
export { ComfyUIInternalError } from './base';

// Error classes
export { ConfigError } from './configError';
export { ModelResolverError } from './modelResolverError';
export { ServicesError } from './servicesError';
export { UtilsError } from './utilsError';
export { WorkflowError } from './workflowError';

// Type guards
export { isComfyUIInternalError } from './typeGuards';

```
