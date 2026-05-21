# 文件：src/server/routers/lambda/device.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { z } from 'zod';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { deviceProxy } from '@/server/services/toolExecution/deviceProxy';
export const deviceRouter = router({
```

## 主要对外内容
```text
const deviceProcedure = authedProcedure.use(async (opts) => {
export const deviceRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { z } from 'zod';

import { authedProcedure, router } from '@/libs/trpc/lambda';
import { deviceProxy } from '@/server/services/toolExecution/deviceProxy';

const deviceProcedure = authedProcedure.use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: { userId: ctx.userId },
  });
});

export const deviceRouter = router({
  getDeviceSystemInfo: deviceProcedure
    .input(z.object({ deviceId: z.string() }))
    .query(async ({ ctx, input }) => {
      return deviceProxy.queryDeviceSystemInfo(ctx.userId, input.deviceId);
    }),

  listDevices: deviceProcedure.query(async ({ ctx }) => {
    return deviceProxy.queryDeviceList(ctx.userId);
  }),

  status: deviceProcedure.query(async ({ ctx }) => {
    return deviceProxy.queryDeviceStatus(ctx.userId);
  }),
});

```
