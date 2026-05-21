# 文件：src/server/services/notebook/index.ts

## 文件职责
这个文件位于 `src/server/services/notebook`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type LobeChatDatabase } from '@lobechat/database';
import type { AgentDocumentSourceType } from '@/database/models/agentDocuments/types';
import { DocumentModel } from '@/database/models/document';
import { TopicDocumentModel } from '@/database/models/topicDocument';
import { DocumentService } from '@/server/services/document';
export interface NotebookRuntimeServiceOptions {
export class NotebookRuntimeService {
```

## 主要对外内容
```text
interface DocumentServiceResult {
export interface NotebookRuntimeServiceOptions {
const toServiceResult = (doc: {
export class NotebookRuntimeService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type LobeChatDatabase } from '@lobechat/database';

import type { AgentDocumentSourceType } from '@/database/models/agentDocuments/types';
import { DocumentModel } from '@/database/models/document';
import { TopicDocumentModel } from '@/database/models/topicDocument';
import { DocumentService } from '@/server/services/document';

interface DocumentServiceResult {
  content: string | null;
  createdAt: Date;
  description: string | null;
  fileType: string;
  id: string;
  source: string;
  sourceType: 'api' | 'file' | 'web';
  title: string | null;
  totalCharCount: number;
  updatedAt: Date;
}

export interface NotebookRuntimeServiceOptions {
  serverDB: LobeChatDatabase;
  userId: string;
}

const toServiceResult = (doc: {
  content: string | null;
  createdAt: Date;
  description: string | null;
  fileType: string;
  id: string;
  source: string;
  sourceType: AgentDocumentSourceType;
  title: string | null;
  totalCharCount: number;
  updatedAt: Date;
}): DocumentServiceResult => ({
  content: doc.content,
  createdAt: doc.createdAt,
  description: doc.description,
  fileType: doc.fileType,
  id: doc.id,
  source: doc.source,
  sourceType: doc.sourceType === 'file' || doc.sourceType === 'web' ? doc.sourceType : 'api',
  title: doc.title,
  totalCharCount: doc.totalCharCount,
  updatedAt: doc.updatedAt,
});

export class NotebookRuntimeService {
  private documentService: DocumentService;
  private documentModel: DocumentModel;
  private topicDocumentModel: TopicDocumentModel;

  constructor(options: NotebookRuntimeServiceOptions) {
    this.documentService = new DocumentService(options.serverDB, options.userId);
    this.documentModel = new DocumentModel(options.serverDB, options.userId);
    this.topicDocumentModel = new TopicDocumentModel(options.serverDB, options.userId);
  }

  associateDocumentWithTopic = async (documentId: string, topicId: string): Promise<void> => {
    await this.topicDocumentModel.associate({ documentId, topicId });
  };

  createDocument = async (params: {
    content: string;
    fileType: string;
    source: string;
    sourceType: 'api' | 'file' | 'web';
    title: string;
    totalCharCount: number;
    totalLineCount: number;
  }): Promise<DocumentServiceResult> => {
    const doc = await this.documentModel.create(params);
    return toServiceResult(doc);
  };

  deleteDocument = async (id: string): Promise<void> => {
    await this.topicDocumentModel.deleteByDocumentId(id);
    await this.documentService.deleteDocument(id);
  };

  getDocument = async (id: string): Promise<DocumentServiceResult | undefined> => {
    const doc = await this.documentModel.findById(id);
    if (!doc) return undefined;
    return toServiceResult(doc);
  };

  getDocumentsByTopicId = async (
    topicId: string,
    filter?: { type?: string },
  ): Promise<DocumentServiceResult[]> => {
    const docs = await this.topicDocumentModel.findByTopicId(topicId, filter);
    return docs.map(toServiceResult);
  };

  updateDocument = async (
    id: string,
    params: { content?: string; title?: string },
  ): Promise<DocumentServiceResult> => {
    await this.documentModel.update(id, {
      ...(params.content !== undefined && {
        content: params.content,
        totalCharCount: params.content.length,
        totalLineCount: params.content.split('\n').length,
      }),
      ...(params.title !== undefined && { title: params.title }),
    });

    const doc = await this.documentModel.findById(id);
    if (!doc) throw new Error(`Document not found after update: ${id}`);
    return toServiceResult(doc);
  };
}

```
