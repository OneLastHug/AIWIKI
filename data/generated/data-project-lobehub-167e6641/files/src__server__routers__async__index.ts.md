# 文件：src/server/routers/async/index.ts

## 文件职责
这个文件位于 `src/server/routers/async`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { asyncRouter as router, publicProcedure } from '@/libs/trpc/async';
import { documentRouter } from './document';
import { fileRouter } from './file';
import { imageRouter } from './image';
import { ragEvalRouter } from './ragEval';
import { videoRouter } from './video';
export const asyncRouter = router({
export type AsyncRouter = typeof asyncRouter;
export type { UnifiedAsyncCaller } from './caller';
export { createAsyncCaller, createAsyncServerClient } from './caller';
```

## 主要对外内容
```text
export const asyncRouter = router({
export type AsyncRouter = typeof asyncRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { asyncRouter as router, publicProcedure } from '@/libs/trpc/async';

import { documentRouter } from './document';
import { fileRouter } from './file';
import { imageRouter } from './image';
import { ragEvalRouter } from './ragEval';
import { videoRouter } from './video';

export const asyncRouter = router({
  document: documentRouter,
  file: fileRouter,
  healthcheck: publicProcedure.query(() => "i'm live!"),
  image: imageRouter,
  ragEval: ragEvalRouter,
  video: videoRouter,
});

export type AsyncRouter = typeof asyncRouter;

export type { UnifiedAsyncCaller } from './caller';
export { createAsyncCaller, createAsyncServerClient } from './caller';

```
