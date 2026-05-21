# 文件：src/server/routers/lambda/index.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { accountDeletionRouter } from '@/business/server/lambda-routers/accountDeletion';
import { referralRouter } from '@/business/server/lambda-routers/referral';
import { spendRouter } from '@/business/server/lambda-routers/spend';
import { subscriptionRouter } from '@/business/server/lambda-routers/subscription';
import { taskTemplateRouter } from '@/business/server/lambda-routers/taskTemplate';
import { topUpRouter } from '@/business/server/lambda-routers/topUp';
import { publicProcedure, router } from '@/libs/trpc/lambda';
import { agentRouter } from './agent';
import { agentBotProviderRouter } from './agentBotProvider';
import { agentDocumentRouter } from './agentDocument';
import { agentEvalRouter } from './agentEval';
import { agentEvalExternalRouter } from './agentEvalExternal';
import { agentGroupRouter } from './agentGroup';
import { agentNotifyRouter } from './agentNotify';
import { agentSignalRouter } from './agentSignal';
import { agentSkillsRouter } from './agentSkills';
import { aiAgentRouter } from './aiAgent';
import { aiChatRouter } from './aiChat';
import { aiModelRouter } from './aiModel';
import { aiProviderRouter } from './aiProvider';
import { apiKeyRouter } from './apiKey';
import { botMessageRouter } from './botMessage';
import { briefRouter } from './brief';
import { changelogRouter } from './changelog';
import { chunkRouter } from './chunk';
import { comfyuiRouter } from './comfyui';
import { configRouter } from './config';
import { deviceRouter } from './device';
import { documentRouter } from './document';
import { exporterRouter } from './exporter';
import { fileRouter } from './file';
import { followUpActionRouter } from './followUpAction';
import { generationRouter } from './generation';
import { generationBatchRouter } from './generationBatch';
import { generationTopicRouter } from './generationTopic';
import { homeRouter } from './home';
import { imageRouter } from './image';
import { importerRouter } from './importer';
import { klavisRouter } from './klavis';
import { knowledgeRouter } from './knowledge';
```

## 主要对外内容
```text
export const lambdaRouter = router({
export type LambdaRouter = typeof lambdaRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
/**
 * This file contains the root router of Lobe Chat tRPC-backend
 */
import { accountDeletionRouter } from '@/business/server/lambda-routers/accountDeletion';
import { referralRouter } from '@/business/server/lambda-routers/referral';
import { spendRouter } from '@/business/server/lambda-routers/spend';
import { subscriptionRouter } from '@/business/server/lambda-routers/subscription';
import { taskTemplateRouter } from '@/business/server/lambda-routers/taskTemplate';
import { topUpRouter } from '@/business/server/lambda-routers/topUp';
import { publicProcedure, router } from '@/libs/trpc/lambda';

import { agentRouter } from './agent';
import { agentBotProviderRouter } from './agentBotProvider';
import { agentDocumentRouter } from './agentDocument';
import { agentEvalRouter } from './agentEval';
import { agentEvalExternalRouter } from './agentEvalExternal';
import { agentGroupRouter } from './agentGroup';
import { agentNotifyRouter } from './agentNotify';
import { agentSignalRouter } from './agentSignal';
import { agentSkillsRouter } from './agentSkills';
import { aiAgentRouter } from './aiAgent';
import { aiChatRouter } from './aiChat';
import { aiModelRouter } from './aiModel';
import { aiProviderRouter } from './aiProvider';
import { apiKeyRouter } from './apiKey';
import { botMessageRouter } from './botMessage';
import { briefRouter } from './brief';
import { changelogRouter } from './changelog';
import { chunkRouter } from './chunk';
import { comfyuiRouter } from './comfyui';
import { configRouter } from './config';
import { deviceRouter } from './device';
import { documentRouter } from './document';
import { exporterRouter } from './exporter';
import { fileRouter } from './file';
import { followUpActionRouter } from './followUpAction';
import { generationRouter } from './generation';
import { generationBatchRouter } from './generationBatch';
import { generationTopicRouter } from './generationTopic';
import { homeRouter } from './home';
import { imageRouter } from './image';
import { importerRouter } from './importer';
import { klavisRouter } from './klavis';
import { knowledgeRouter } from './knowledge';
import { knowledgeBaseRouter } from './knowledgeBase';
import { marketRouter } from './market';
import { messageRouter } from './message';
import { messengerRouter } from './messenger';
import { notebookRouter } from './notebook';
import { notificationRouter } from './notification';
import { oauthDeviceFlowRouter } from './oauthDeviceFlow';
import { pluginRouter } from './plugin';
import { ragEvalRouter } from './ragEval';
import { recentRouter } from './recent';
import { searchRouter } from './search';
import { sessionRouter } from './session';
import { sessionGroupRouter } from './sessionGroup';
import { shareRouter } from './share';
import { taskRouter } from './task';
import { threadRouter } from './thread';
import { topicRouter } from './topic';
import { uploadRouter } from './upload';
import { usageRouter } from './usage';
import { userRouter } from './user';
import { userMemoriesRouter } from './userMemories';
import { userMemoryRouter } from './userMemory';
import { videoRouter } from './video';

export const lambdaRouter = router({
  agent: agentRouter,
  agentBotProvider: agentBotProviderRouter,
  agentNotify: agentNotifyRouter,
  botMessage: botMessageRouter,
  agentDocument: agentDocumentRouter,
  agentEval: agentEvalRouter,
  agentEvalExternal: agentEvalExternalRouter,
  agentSkills: agentSkillsRouter,
  agentSignal: agentSignalRouter,
  task: taskRouter,
  changelog: changelogRouter,
  brief: briefRouter,
  aiAgent: aiAgentRouter,
  aiChat: aiChatRouter,
  aiModel: aiModelRouter,
  aiProvider: aiProviderRouter,
  apiKey: apiKeyRouter,
  chunk: chunkRouter,
  comfyui: comfyuiRouter,
  config: configRouter,
  device: deviceRouter,
  document: documentRouter,
  exporter: exporterRouter,
  file: fileRouter,
  followUpAction: followUpActionRouter,
  generation: generationRouter,
  generationBatch: generationBatchRouter,
  generationTopic: generationTopicRouter,
  group: agentGroupRouter,
  healthcheck: publicProcedure.query(() => "i'm live!"),
  home: homeRouter,
  image: imageRouter,
  importer: importerRouter,
  klavis: klavisRouter,
  knowledge: knowledgeRouter,
  knowledgeBase: knowledgeBaseRouter,
  market: marketRouter,
  message: messageRouter,
  messenger: messengerRouter,
  notebook: notebookRouter,
  notification: notificationRouter,
  oauthDeviceFlow: oauthDeviceFlowRouter,
  plugin: pluginRouter,
  ragEval: ragEvalRouter,
  recent: recentRouter,
  search: searchRouter,
  session: sessionRouter,
  sessionGroup: sessionGroupRouter,
  share: shareRouter,
  thread: threadRouter,
  topic: topicRouter,
  upload: uploadRouter,
  usage: usageRouter,
  user: userRouter,
  userMemories: userMemoriesRouter,
  userMemory: userMemoryRouter,
  video: videoRouter,
  accountDeletion: accountDeletionRouter,
  referral: referralRouter,
  spend: spendRouter,
  subscription: subscriptionRouter,
  taskTemplate: taskTemplateRouter,
  topUp: topUpRouter,
});

export type LambdaRouter = typeof lambdaRouter;

```
