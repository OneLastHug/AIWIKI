# 文件：src/server/services/chunk/index.ts

## 文件职责
这个文件位于 `src/server/services/chunk`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type LobeChatDatabase } from '@lobechat/database';
import { AsyncTaskModel } from '@/database/models/asyncTask';
import { FileModel } from '@/database/models/file';
import { type ChunkContentParams } from '@/server/modules/ContentChunk';
import { ContentChunk } from '@/server/modules/ContentChunk';
import {
export class ChunkService {
```

## 主要对外内容
```text
export class ChunkService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type LobeChatDatabase } from '@lobechat/database';

import { AsyncTaskModel } from '@/database/models/asyncTask';
import { FileModel } from '@/database/models/file';
import { type ChunkContentParams } from '@/server/modules/ContentChunk';
import { ContentChunk } from '@/server/modules/ContentChunk';
import {
  AsyncTaskError,
  AsyncTaskErrorType,
  AsyncTaskStatus,
  AsyncTaskType,
} from '@/types/asyncTask';

export class ChunkService {
  private userId: string;
  private chunkClient: ContentChunk;
  private fileModel: FileModel;
  private asyncTaskModel: AsyncTaskModel;

  constructor(serverDB: LobeChatDatabase, userId: string) {
    this.userId = userId;

    this.chunkClient = new ContentChunk();

    this.fileModel = new FileModel(serverDB, userId);
    this.asyncTaskModel = new AsyncTaskModel(serverDB, userId);
  }

  async chunkContent(params: ChunkContentParams) {
    return this.chunkClient.chunkContent(params);
  }

  async asyncEmbeddingFileChunks(fileId: string) {
    const result = await this.fileModel.findById(fileId);

    if (!result) return;

    // 1. create a asyncTaskId
    const asyncTaskId = await this.asyncTaskModel.create({
      status: AsyncTaskStatus.Pending,
      type: AsyncTaskType.Embedding,
    });

    await this.fileModel.update(fileId, { embeddingTaskId: asyncTaskId });

    // Async router will read keyVaults from DB, no need to pass jwtPayload
    // Dynamic import to avoid circular dependency
    const { createAsyncCaller } = await import('@/server/routers/async');
    const asyncCaller = await createAsyncCaller({ userId: this.userId });

    // trigger embedding task asynchronously
    try {
      await asyncCaller.file.embeddingChunks({ fileId, taskId: asyncTaskId });
    } catch (e) {
      console.error('[embeddingFileChunks] error:', e);

      await this.asyncTaskModel.update(asyncTaskId, {
        error: new AsyncTaskError(
          AsyncTaskErrorType.TaskTriggerError,
          'trigger chunk embedding async task error. Please make sure the APP_URL is available from your server. You can check the proxy config or WAF blocking',
        ),
        status: AsyncTaskStatus.Error,
      });
    }

    return asyncTaskId;
  }

  /**
   * parse file to chunks with async task
   */
  async asyncParseFileToChunks(fileId: string, skipExist?: boolean) {
    const result = await this.fileModel.findById(fileId);

    if (!result) return;

    // skip if already exist chunk tasks
    if (skipExist && result.chunkTaskId) return;

    // 1. create a asyncTaskId
    const asyncTaskId = await this.asyncTaskModel.create({
      status: AsyncTaskStatus.Processing,
      type: AsyncTaskType.Chunking,
    });

    await this.fileModel.update(fileId, { chunkTaskId: asyncTaskId });

    // Async router will read keyVaults from DB, no need to pass jwtPayload
    // Dynamic import to avoid circular dependency
    const { createAsyncCaller } = await import('@/server/routers/async');
    const asyncCaller = await createAsyncCaller({ userId: this.userId });

    // trigger parse file task asynchronously
    asyncCaller.file.parseFileToChunks({ fileId, taskId: asyncTaskId }).catch(async (e) => {
      console.error('[ParseFileToChunks] error:', e);

      await this.asyncTaskModel.update(asyncTaskId, {
        error: new AsyncTaskError(
          AsyncTaskErrorType.TaskTriggerError,
          'trigger chunk embedding async task error. Please make sure the APP_URL is available from your server. You can check the proxy config or WAF blocking',
        ),
        status: AsyncTaskStatus.Error,
      });
    });

    return asyncTaskId;
  }
}

```
