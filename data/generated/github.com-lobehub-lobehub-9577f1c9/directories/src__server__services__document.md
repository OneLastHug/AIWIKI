# 目录：src/server/services/document

## 它负责什么

`src/server/services/document` 是服务端文档领域的核心服务目录，主要负责把“文档”这一业务对象在数据库、文件系统、编辑器数据和历史版本之间串起来。它不是前端编辑器本身，也不是数据库 schema 定义处，而是站在 server service 层，封装文档创建、更新、删除、文件解析导入、历史快照、历史对比等业务流程。

从当前片段看，这个目录围绕两个主要服务类展开：`DocumentService` 和 `DocumentHistoryService`。前者处理文档生命周期，例如创建文档、批量创建、删除文档、更新 `editorData`、从文件解析生成文档；后者处理历史版本，例如列出历史、读取单个历史项、比较两个历史项、根据保存来源做历史保留清理。目录下的 `diff/json.ts` 则提供结构化 JSON diff / patch 能力，用于把编辑器数据的历史变化保存为更轻量的差异信息。

它和数据库模型关系很紧密，代码中使用了 `DocumentModel`、`FileModel`、`documentHistories`、`documents`、`files` 等模型或表查询；同时它也依赖文件服务和文件加载能力，例如 `FileService.downloadFileToLocal`、`@lobechat/file-loaders` 的 `loadFile`。因此这里可以理解为“文档服务编排层”：它不定义底层存储结构，但决定一次文档操作应该触发哪些模型读写、历史保存和文件处理。

## 直接子目录地图

`src/server/services/document` 本身是一个小而集中的目录，直接子目录不多：

`src/server/services/document/diff` 负责文档内容差异算法。目前能看到 `json.ts` 和对应测试 `json.test.ts`。它基于 `jsondiffpatch` 创建 JSON patch，并提供应用 patch、判断 patch 是否过大等工具。这里服务的是历史版本功能，尤其适合编辑器数据这类结构化 JSON。

`src/server/services/document/__tests__` 放置文档服务层测试。当前包括 `index.test.ts` 和 `history.integration.test.ts`。前者偏向 `DocumentService` 的行为测试，后者偏向 `DocumentHistoryService` 与数据库交互的集成测试。另有 `diff/json.test.ts` 位于 `diff` 子目录下，覆盖 JSON diff 工具自身。

根目录下的 `index.ts` 是 `DocumentService` 主入口；`history.ts` 是 `DocumentHistoryService` 主入口；`types.ts` 集中定义历史列表、历史项、更新参数、保存来源、数据库类型等服务层类型。

## 关键入口

最重要的入口是 `src/server/services/document/index.ts`。这里导出 `DocumentService`，也是外部模块通常引入文档服务的位置，例如 `src/server/services/notebook/index.ts` 和 `src/server/services/webBrowsing/index.ts` 都会使用 `DocumentService` 来复用文档更新、删除或内容变更后的历史保存逻辑。

`DocumentService` 构造时接收数据库对象和 `userId`，内部组合 `DocumentModel`、`FileModel`、`FileService`、`DocumentHistoryService` 等依赖。根据当前片段，它覆盖的职责包括：创建普通文档、批量创建文档、删除文档及其关联文件、更新文档内容、从已有文件下载到本地后通过 `loadFile` 解析成文档。更新流程中还会规范化编辑器数据，例如调用 `normalizeEditorDataDiffNodes`，并在必要时追加历史记录。

第二个关键入口是 `src/server/services/document/history.ts`。这里导出 `DocumentHistoryService`，专注于文档历史版本。它会读取当前文档作为 `head`，也会查询 `documentHistories` 表中的历史行。相关类型在 `types.ts` 中，例如 `DocumentHistorySaveSource`、`ListDocumentHistoryParams`、`GetDocumentHistoryItemParams`、`CompareDocumentHistoryItemsParams`。这说明历史服务对外提供的是“列表、详情、比较、保存”这一组稳定能力。

第三个入口是 `src/server/services/document/diff/json.ts`。它不是业务服务类，而是被历史保存和比较流程依赖的底层工具。它导出 `createJsonPatch`、`applyJsonPatch`、`isOversizedJsonPatch` 和 `JsonPatchDelta`，用于把两份编辑器 JSON 数据转成 patch、再从 patch 恢复目标数据，或在 patch 太大时选择其他保存策略。

## 主流程位置

文档创建主流程在 `src/server/services/document/index.ts` 的 `DocumentService` 中。普通创建会整理内容长度、行数、元数据、文件信息等，然后写入 `documents`，必要时也会创建 `files` 记录。批量创建则基于单个创建流程做 `Promise.all` 聚合。这里是理解“文档对象如何落库”的第一位置。

文档更新主流程也在 `src/server/services/document/index.ts`。从当前代码片段看，更新会先读取当前文档，规范化 `editorData`，记录 `savedAt`，并在事务中再次确认当前数据。随后根据新旧编辑器数据是否变化决定是否追加历史，再更新文档字段、文件字段或内容相关字段。根据当前片段推断，历史写入和文档更新被放在同一事务里，是为了避免“文档已更新但历史未保存”或“历史保存了但文档更新失败”的不一致。

文档删除主流程位于 `src/server/services/document/index.ts` 的后段。它会先读取目标文档，处理子文档，再查找关联文件并删除。这里需要注意它不是简单删除一行 `documents`，而是要维护文档树和文件资源的关系。

文件导入主流程集中在 `src/server/services/document/index.ts` 更靠后的部分。当前片段显示它会调用 `fileService.downloadFileToLocal(fileId)` 得到临时本地文件，再用 `loadFile(filePath)` 解析内容，最后创建文档；失败时会经过 `normalizeParseFileError` 统一文件解析错误。根据当前片段推断，这条链路是上传文件变成可编辑文档的服务端核心流程，依据是代码中出现了 `downloadFileToLocal`、`loadFile`、`UnsupportedFileTypeError`、解析成功后 `documentModel.create` 这些连续操作。

历史列表与详情主流程在 `src/server/services/document/history.ts`。`listDocumentHistory` 会把当前文档头版本和历史表版本合并成列表，并支持 `limit`、`beforeSavedAt`、`beforeId`、`includeCurrent` 这类分页和包含当前版本的控制。`getDocumentHistoryItem` 负责读取指定历史项，`compareDocumentHistoryItems` 负责比较两个历史版本。保存历史后还会按 `DocumentHistorySaveSource` 做数量限制清理，例如 `autosave`、`manual`、`restore`、`system`、`llm_call` 来源会有不同保留策略。

## 推荐阅读顺序

建议先读 `src/server/services/document/types.ts`。这里能先建立服务层对“文档历史”的抽象，包括保存来源、列表项、历史详情、更新参数和返回值。先看类型，比直接进入服务实现更容易理解后续方法的输入输出边界。

第二步读 `src/server/services/document/index.ts`。重点看 `DocumentService` 的构造依赖和几个主流程分组：创建、更新、删除、文件解析导入。不要一开始陷入每个字段的细节，先把它看成一个编排器：它调用模型、文件服务、历史服务，完成一次完整业务操作。

第三步读 `src/server/services/document/history.ts`。重点理解当前版本 `head` 和历史表记录之间的关系，以及列表分页、历史详情、历史比较、历史清理这些行为。这里是理解“为什么文档更新要保存历史”的关键。

第四步读 `src/server/services/document/diff/json.ts`。看它如何对编辑器 JSON 做稳定比较、生成 patch、应用 patch，并判断 patch 体积。读完之后再回到 `history.ts`，历史保存策略会更容易理解。

最后看测试：`src/server/services/document/__tests__/index.test.ts`、`src/server/services/document/__tests__/history.integration.test.ts`、`src/server/services/document/diff/json.test.ts`。测试可以帮助确认边界行为，例如历史分页、不同保存来源的保留数量、文件解析异常、diff patch 的结构处理。

## 常见误区

第一个误区是把这里当成数据库层。实际数据库表和模型不在这个目录，`DocumentService` 只是调用 `DocumentModel`、`FileModel` 等模型完成业务编排。要查字段定义或索引，应继续去数据库 schema 或 model 目录，而不是只在这里找。

第二个误区是认为文档更新只是更新 `documents.editorData`。从当前片段看，更新还牵涉历史快照、diff 规范化、事务、文件字段同步等逻辑。绕过 `DocumentService.updateDocument` 直接改模型，可能会漏掉 `document_histories` 写入，导致历史列表、恢复或对比功能不完整。

第三个误区是把 `diff/json.ts` 理解成通用文本 diff。它处理的是结构化 JSON，尤其适合编辑器数据，不是面向纯文本段落的行级 diff。它还包含稳定化比较逻辑，目的是减少对象 key 顺序带来的无意义差异。

第四个误区是忽略 `head` 当前版本。历史列表不是只读 `documentHistories` 表；当前文档本身也会作为当前版本参与展示或比较。阅读 `history.ts` 时要特别留意 `includeCurrent`、`head`、`beforeSavedAt` 这些概念。

第五个误区是把文件导入失败当作普通异常。`index.ts` 中有 `normalizeParseFileError`，并且识别 `UnsupportedFileTypeError` 等解析错误，说明文件解析链路有专门的错误归一化逻辑。调用方看到的错误很可能已经不是底层 loader 的原始错误。
