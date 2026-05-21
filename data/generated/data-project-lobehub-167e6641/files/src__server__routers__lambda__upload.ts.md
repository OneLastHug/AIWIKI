# 文件：src/server/routers/lambda/upload.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { FileS3 } from '@/server/modules/S3';
export const uploadRouter = router({
export type FileRouter = typeof uploadRouter;
```

## 主要对外内容
```text
export const uploadRouter = router({
export type FileRouter = typeof uploadRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { authedProcedure, router } from '@/libs/trpc/lambda';
import { FileS3 } from '@/server/modules/S3';

export const uploadRouter = router({
  createS3PreSignedUrl: authedProcedure
    .input(z.object({ pathname: z.string() }))
    .mutation(async ({ input }) => {
      const s3 = new FileS3();

      return await s3.createPreSignedUrl(input.pathname);
    }),
});

export type FileRouter = typeof uploadRouter;

```
