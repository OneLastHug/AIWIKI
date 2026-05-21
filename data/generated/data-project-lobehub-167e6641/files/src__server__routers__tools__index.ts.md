# 文件：src/server/routers/tools/index.ts

## 文件职责
这个文件位于 `src/server/routers/tools`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { klavisRouter } from './klavis';
import { marketRouter } from './market';
import { mcpRouter } from './mcp';
import { searchRouter } from './search';
export const toolsRouter = router({
export type ToolsRouter = typeof toolsRouter;
```

## 主要对外内容
```text
export const toolsRouter = router({
export type ToolsRouter = typeof toolsRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { publicProcedure, router } from '@/libs/trpc/lambda';

import { klavisRouter } from './klavis';
import { marketRouter } from './market';
import { mcpRouter } from './mcp';
import { searchRouter } from './search';

export const toolsRouter = router({
  healthcheck: publicProcedure.query(() => "i'm live!"),
  klavis: klavisRouter,
  market: marketRouter,
  mcp: mcpRouter,
  search: searchRouter,
});

export type ToolsRouter = typeof toolsRouter;

```
