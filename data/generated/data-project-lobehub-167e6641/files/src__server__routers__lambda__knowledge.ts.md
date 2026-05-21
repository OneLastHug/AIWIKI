# 文件：src/server/routers/lambda/knowledge.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { AsyncTaskModel } from '@/database/models/asyncTask';
import { ChunkModel } from '@/database/models/chunk';
import { DocumentModel } from '@/database/models/document';
import { FileModel } from '@/database/models/file';
import { KnowledgeRepo } from '@/database/repositories/knowledge';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { FileService } from '@/server/services/file';
import { AsyncTaskStatus, AsyncTaskType } from '@/types/asyncTask';
import { type FileListItem } from '@/types/files';
import { QueryFileListSchema } from '@/types/files';
export const knowledgeRouter = router({
export type KnowledgeRouter = typeof knowledgeRouter;
```

## 主要对外内容
```text
const knowledgeProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
export const knowledgeRouter = router({
export type KnowledgeRouter = typeof knowledgeRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { AsyncTaskModel } from '@/database/models/asyncTask';
import { ChunkModel } from '@/database/models/chunk';
import { DocumentModel } from '@/database/models/document';
import { FileModel } from '@/database/models/file';
import { KnowledgeRepo } from '@/database/repositories/knowledge';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { FileService } from '@/server/services/file';
import { AsyncTaskStatus, AsyncTaskType } from '@/types/asyncTask';
import { type FileListItem } from '@/types/files';
import { QueryFileListSchema } from '@/types/files';

const knowledgeProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;

  return opts.next({
    ctx: {
      asyncTaskModel: new AsyncTaskModel(ctx.serverDB, ctx.userId),
      chunkModel: new ChunkModel(ctx.serverDB, ctx.userId),
      documentModel: new DocumentModel(ctx.serverDB, ctx.userId),
      fileModel: new FileModel(ctx.serverDB, ctx.userId),
      fileService: new FileService(ctx.serverDB, ctx.userId),
      knowledgeRepo: new KnowledgeRepo(ctx.serverDB, ctx.userId),
    },
  });
});

export const knowledgeRouter = router({
  getKnowledgeItems: knowledgeProcedure.input(QueryFileListSchema).query(async ({ ctx, input }) => {
    const knowledgeItems = await ctx.knowledgeRepo.query(input);

    // Process files (add chunk info and async task status)
    const fileItems = knowledgeItems.filter((item) => item.sourceType === 'file');
    const fileIds = fileItems.map((item) => item.id);
    const chunks = await ctx.chunkModel.countByFileIds(fileIds);

    const chunkTaskIds = fileItems.map((item) => item.chunkTaskId).filter(Boolean) as string[];
    const chunkTasks = await ctx.asyncTaskModel.findByIds(chunkTaskIds, AsyncTaskType.Chunking);

    const embeddingTaskIds = fileItems
      .map((item) => item.embeddingTaskId)
      .filter(Boolean) as string[];
    const embeddingTasks = await ctx.asyncTaskModel.findByIds(
      embeddingTaskIds,
      AsyncTaskType.Embedding,
    );

    // Combine all items with their metadata
    const resultItems = [] as any[];
    for (const item of knowledgeItems) {
      if (item.sourceType === 'file') {
        const chunkTask = item.chunkTaskId
          ? chunkTasks.find((task) => task.id === item.chunkTaskId)
          : null;
        const embeddingTask = item.embeddingTaskId
          ? embeddingTasks.find((task) => task.id === item.embeddingTaskId)
          : null;

        resultItems.push({
          ...item,
          chunkCount: chunks.find((chunk) => chunk.id === item.id)?.count ?? null,
          chunkingError: chunkTask?.error ?? null,
          chunkingStatus: chunkTask?.status as AsyncTaskStatus,
          editorData: null,
          embeddingError: embeddingTask?.error ?? null,
          embeddingStatus: embeddingTask?.status as AsyncTaskStatus,
          finishEmbedding: embeddingTask?.status === AsyncTaskStatus.Success,
          url: item.url ? await ctx.fileService.getFullFileUrl(item.url) : undefined,
        } as FileListItem);
      } else {
        // Document item - no chunk processing needed, includes editorData
        const documentItem = {
          ...item,
          chunkCount: null,
          chunkingError: null,
          chunkingStatus: null,
          embeddingError: null,
          embeddingStatus: null,
          finishEmbedding: false,
        } as FileListItem;
        console.info('[API getKnowledgeItems] Processing document:', {
          editorDataPreview: item.editorData ? JSON.stringify(item.editorData).slice(0, 100) : null,
          hasEditorData: !!item.editorData,
          id: item.id,
          name: item.name,
        });
        resultItems.push(documentItem);
      }
    }

    return resultItems;
  }),
});

export type KnowledgeRouter = typeof knowledgeRouter;

```
