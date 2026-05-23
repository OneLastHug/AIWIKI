# 目录：src/store/file

## 它负责什么

`src/store/file` 是前端文件域的 Zustand store，负责把“文件上传、聊天附件、知识库/资源管理、文档资源、文件分块、高亮、TTS 文件”等前端状态和动作集中在一个 `useFileStore` 里。它不是实际的对象存储实现，也不是数据库模型层；它更像文件能力在浏览器侧的协调层：UI 从这里读上传队列、资源列表、当前文件、分块搜索状态等，也通过这里触发上传、删除、移动、解析、刷新、TTS 文件读取等动作。

从当前片段看，典型数据流是：`src/features/*` 组件调用 `useFileStore` 的 action，store 内部更新本地 state 或 reducer，再调用 `src/services/file`、`src/services/upload` 等 client service，后者继续连接后端 router 或上传服务。也就是说，这个目录处在“React UI”和“client service”之间，主要承担状态编排、乐观更新、上传进度维护和资源视图缓存。

## 直接子目录地图

`src/store/file/reducers` 放通用 reducer，目前核心是 `uploadFileListReducer`，用于维护上传列表的增删、状态更新、清空等队列型状态。它被聊天上传和资源管理上传复用，避免每个 slice 自己手写列表变更逻辑。

`src/store/file/slices` 是主体目录，按文件业务场景拆成多个 slice：

`src/store/file/slices/chat` 管聊天输入区的文件和上下文选择，例如聊天附件列表、聊天上下文 selection、上传前校验和相关 selector。`src/features/ChatInput`、`src/features/Conversation/ChatInput` 等会大量消费这里。

`src/store/file/slices/fileManager` 面向资源管理器和上传 dock，覆盖文件列表、文件移动、删除、批量上传、文件夹结构上传、上传取消、上传进度汇总等更偏“文件管理台”的能力。`src/features/ResourceManager` 是主要使用者。

`src/store/file/slices/resource` 管资源列表形态和本地资源缓存，包括 `resourceList`、`resourceMap`、查询参数、分页加载、乐观资源替换等。它还包含 `hooks.ts`，说明这里不只是纯 action，也提供与资源列表数据拉取相关的 hook 封装。

`src/store/file/slices/document` 管文档型资源。根据当前片段推断，它服务于 ResourceManager、PageExplorer 或页面编辑相关场景，负责文档创建、读取、更新等状态动作；依据是 `src/features/ResourceManager`、`src/features/PageExplorer` 中存在 `createDocument`、`updateDocumentOptimistically` 等调用。

`src/store/file/slices/chunk` 管文件 chunk/分块相关状态，例如 chunk drawer、相似度搜索、高亮 chunk 等。`src/features/ResourceManager/components/ChunkDrawer` 和 `src/features/FileViewer/Renderer/PDF/HighlightLayer.tsx` 会读取这些状态。

`src/store/file/slices/tts` 管 TTS 生成或播放所需的文件记录，例如上传 TTS 文件、读取 TTS 文件、删除 TTS 文件。`src/features/Conversation/Messages/components/Extras/TTS` 是主要入口之一。

`src/store/file/slices/upload` 是通用上传动作层，处理 `File` 或 base64 数据上传，计算 hash、获取图片尺寸、上传到对象存储，并通过 `fileService.createFile` 创建文件记录。它是其他场景复用的底层上传 action，不直接等同于某个 UI 上传队列。

## 关键入口

最重要的入口是 `src/store/file/index.ts`，它对外导出 `useFileStore` 和 selector。业务组件通常从 `@/store/file` 引入，而不是直接访问内部 slice。

`src/store/file/store.ts` 是 store 聚合入口。这里定义 `FileStore`，把 `FileAction`、`DocumentAction`、`TTSFileAction`、`FileManageAction`、`FileChunkAction`、`FileUploadAction`、`ResourceAction` 和 `FilesStoreState` 合并成一个 store 类型。创建 store 时，它用 `createWithEqualityFn`、`createDevtools('file')` 和 `shallow` 建立 `useFileStore`，并通过 `expose('file', useFileStore)` 暴露调试入口。

`src/store/file/initialState.ts` 是状态聚合入口，合并 `initialImageFileState`、`initialDocumentState`、`initialFileManagerState`、`initialFileChunkState`、`initialResourceState`。注意这里没有包含每个 slice 的 action，只负责 state 初值组合。

`src/store/file/selectors.ts` 是 selector 汇总入口。虽然当前命令没有展开内容，但从 `index.ts` 的 `export * from './selectors'` 以及调用方的 `fileChatSelectors`、`filesSelectors`、`fileManagerSelectors`、`documentSelectors` 可推断，它统一导出各 slice 的 selector 集合，供 UI 以稳定方式读取派生状态。

## 主流程位置

上传主流程集中在 `src/store/file/slices/upload/action.ts`。普通文件上传大致是：读取 `File.arrayBuffer()`，用 `sha256` 计算 hash，调用 `fileService.checkFileHash` 判断是否已有记录；若不存在，再调用 `uploadService.uploadFileToS3` 上传并上报进度；最后调用 `fileService.createFile` 创建文件元数据记录。base64 上传则走 `uploadBase64FileWithProgress`，先取图片尺寸，再调用 `uploadService.uploadBase64ToS3` 和 `fileService.createFile`。

聊天附件流程在 `src/store/file/slices/chat/action.ts`。它维护 `chatUploadFileList`，通过 `uploadFileListReducer` 更新上传队列；移除、获取知识项等动作会走 `fileService.removeFile`、`fileService.getKnowledgeItem`。聊天输入相关 UI 主要在 `src/features/ChatInput` 和 `src/features/Conversation/ChatInput` 读取 `fileChatSelectors` 与对应 action。

资源管理流程主要在 `src/store/file/slices/fileManager/action.ts` 和 `src/store/file/slices/resource/*`。ResourceManager 上传文件时，会先向 dock 队列插入上传项，再调用通用 `uploadWithProgress`，成功后替换或刷新本地资源；移动、删除、清空等动作会调用 `fileService.updateFile`、`fileService.removeFile`、`fileService.removeFiles`、`fileService.removeAllFiles`。资源列表的分页、查询参数和局部缓存则由 resource slice 维护。

文件分块和检索流程在 `src/store/file/slices/chunk`。它连接 ResourceManager 的 ChunkDrawer、PDF 高亮层和相似度搜索 UI，用来表达“当前打开哪个文件的分块”“哪些 chunk 需要高亮”“是否正在相似度搜索”等前端状态。根据当前片段推断，真正的解析、embedding 或检索服务不在本目录，而是在 service/router/server 侧。

TTS 文件流程在 `src/store/file/slices/tts/action.ts`。它通过 `fileService.getFile` 获取文件记录，通过 `fileService.removeFile` 删除记录，并被消息扩展里的 TTS 播放器消费。

## 推荐阅读顺序

1. 先读 `src/store/file/store.ts`，理解 `useFileStore` 如何由多个 slice 聚合，以及 `flattenActions` 在类 action 合并中的作用。
2. 再读 `src/store/file/initialState.ts` 和 `src/store/file/selectors.ts`，建立“有哪些 state、UI 如何读取派生数据”的整体印象。
3. 接着读 `src/store/file/slices/upload/action.ts`，因为它是通用上传底座，很多上层流程最终会复用这里。
4. 然后按使用场景选择 slice：聊天附件看 `src/store/file/slices/chat`；资源管理器看 `src/store/file/slices/fileManager` 和 `src/store/file/slices/resource`；文档资源看 `src/store/file/slices/document`；分块检索看 `src/store/file/slices/chunk`；语音播放文件看 `src/store/file/slices/tts`。
5. 最后对照调用方阅读，例如 `src/features/ChatInput`、`src/features/Conversation/ChatInput`、`src/features/ResourceManager`、`src/features/FileViewer`、`src/features/Conversation/Messages/components/Extras/TTS`，这样更容易把 store action 和真实 UI 流程连起来。

## 常见误区

不要把 `src/store/file` 当成后端文件服务。实际上传、文件记录、对象存储、数据库删除等能力在 `src/services/file`、`src/services/upload`、`src/server/routers/lambda/file.ts` 以及更底层服务中；这里主要是前端状态和流程编排。

不要把 `slices/upload` 和“上传队列 UI”混为一谈。`slices/upload/action.ts` 是通用上传执行器；聊天上传队列在 `slices/chat`，资源管理器 dock 队列在 `slices/fileManager`，两者都可能复用 `uploadFileListReducer`。

不要绕过 selector 到处手写派生逻辑。调用方已经存在 `fileChatSelectors`、`filesSelectors`、`fileManagerSelectors`、`documentSelectors` 等模式，优先沿用这些 selector，能减少 UI 对 state 结构的耦合。

不要在 UI 组件里直接复制上传状态机。上传进度、取消、错误提示、hash 去重、文件记录创建这些流程已经在 store action 与 service 中串好；UI 更适合调用 action 并展示 selector 返回的状态。

不要忽略 slice 边界。`chat` 关注聊天输入上下文，`fileManager` 关注资源管理器操作，`resource` 关注资源列表缓存和查询，`chunk` 关注分块视图，`tts` 关注语音文件。新增能力时先判断属于哪个业务场景，而不是直接塞进 `store.ts` 或通用 upload action。

不要忘记这个 store 使用 class-based action 和 `flattenActions` 聚合。扩展 action 时要保持现有 Zustand 约定：公共 action 给 UI 调用，内部更新尽量通过清晰的 dispatch/reducer 或局部 `set` 完成，复杂列表和乐观更新优先复用 reducer 模式。
