# 文件：src/server/routers/mobile/index.ts

## 文件职责
这个文件位于 `src/server/routers/mobile`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { mobileSubscriptionRouter } from '@/business/server/mobile-routers/mobileSubscription';
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { agentRouter } from '../lambda/agent';
import { aiAgentRouter } from '../lambda/aiAgent';
import { aiChatRouter } from '../lambda/aiChat';
import { aiModelRouter } from '../lambda/aiModel';
import { aiProviderRouter } from '../lambda/aiProvider';
import { briefRouter } from '../lambda/brief';
import { chunkRouter } from '../lambda/chunk';
import { configRouter } from '../lambda/config';
import { documentRouter } from '../lambda/document';
import { fileRouter } from '../lambda/file';
import { homeRouter } from '../lambda/home';
import { knowledgeBaseRouter } from '../lambda/knowledgeBase';
import { marketRouter } from '../lambda/market';
import { messageRouter } from '../lambda/message';
import { sessionRouter } from '../lambda/session';
import { sessionGroupRouter } from '../lambda/sessionGroup';
import { taskRouter } from '../lambda/task';
import { topicRouter } from '../lambda/topic';
import { uploadRouter } from '../lambda/upload';
import { userRouter } from '../lambda/user';
export const mobileRouter = router({
```

## 主要对外内容
```text
export const mobileRouter = router({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
/**
 * This file contains the root router of Lobe Chat tRPC-backend for Mobile App
 * Only includes routers that are actually used by the mobile client
 */
import { mobileSubscriptionRouter } from '@/business/server/mobile-routers/mobileSubscription';
import { publicProcedure, router } from '@/libs/trpc/lambda';

import { agentRouter } from '../lambda/agent';
import { aiAgentRouter } from '../lambda/aiAgent';
import { aiChatRouter } from '../lambda/aiChat';
import { aiModelRouter } from '../lambda/aiModel';
import { aiProviderRouter } from '../lambda/aiProvider';
import { briefRouter } from '../lambda/brief';
import { chunkRouter } from '../lambda/chunk';
import { configRouter } from '../lambda/config';
import { documentRouter } from '../lambda/document';
import { fileRouter } from '../lambda/file';
import { homeRouter } from '../lambda/home';
import { knowledgeBaseRouter } from '../lambda/knowledgeBase';
import { marketRouter } from '../lambda/market';
import { messageRouter } from '../lambda/message';
import { sessionRouter } from '../lambda/session';
import { sessionGroupRouter } from '../lambda/sessionGroup';
import { taskRouter } from '../lambda/task';
import { topicRouter } from '../lambda/topic';
import { uploadRouter } from '../lambda/upload';
import { userRouter } from '../lambda/user';

export const mobileRouter = router({
  agent: agentRouter,
  aiAgent: aiAgentRouter,
  aiChat: aiChatRouter,
  brief: briefRouter,
  aiModel: aiModelRouter,
  aiProvider: aiProviderRouter,
  chunk: chunkRouter,
  config: configRouter,
  document: documentRouter,
  file: fileRouter,
  healthcheck: publicProcedure.query(() => "i'm live!"),
  home: homeRouter,
  knowledgeBase: knowledgeBaseRouter,
  market: marketRouter,
  message: messageRouter,
  session: sessionRouter,
  sessionGroup: sessionGroupRouter,
  subscription: mobileSubscriptionRouter,
  task: taskRouter,
  topic: topicRouter,
  upload: uploadRouter,
  user: userRouter,
});

```
