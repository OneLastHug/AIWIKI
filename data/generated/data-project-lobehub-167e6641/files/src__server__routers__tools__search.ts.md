# 文件：src/server/routers/tools/search.ts

## 文件职责
这个文件位于 `src/server/routers/tools`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { searchService } from '@/server/services/search';
export const searchRouter = router({
```

## 主要对外内容
```text
const searchProcedure = authedProcedure;
export const searchRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { authedProcedure, router } from '@/libs/trpc/lambda';
import { searchService } from '@/server/services/search';

const searchProcedure = authedProcedure;

export const searchRouter = router({
  crawlPages: searchProcedure
    .input(
      z.object({
        impls: z
          .enum(['browserless', 'exa', 'firecrawl', 'jina', 'naive', 'search1api', 'tavily'])
          .array()
          .optional(),
        urls: z.string().array(),
      }),
    )
    .mutation(async ({ input }) => {
      return searchService.crawlPages(input);
    }),

  query: searchProcedure
    .input(
      z.object({
        optionalParams: z
          .object({
            searchCategories: z.array(z.string()).optional(),
            searchEngines: z.array(z.string()).optional(),
            searchTimeRange: z.string().optional(),
          })
          .optional(),
        query: z.string(),
      }),
    )
    .query(async ({ input }) => {
      return await searchService.query(input.query, input.optionalParams);
    }),

  webSearch: searchProcedure
    .input(
      z.object({
        query: z.string(),
        searchCategories: z.array(z.string()).optional(),
        searchEngines: z.array(z.string()).optional(),
        searchTimeRange: z.string().optional(),
      }),
    )
    .query(async ({ input }) => {
      return await searchService.webSearch(input);
    }),
});

```
