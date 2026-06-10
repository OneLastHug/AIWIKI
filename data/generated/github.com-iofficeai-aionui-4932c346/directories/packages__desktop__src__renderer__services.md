# 子系统：packages/desktop/src/renderer/services

## 解决什么问题

这个目录是 renderer 侧的“平台服务层”，把和 UI 组件强耦合但又不适合散落在组件里的能力收拢起来：文件上传与拖拽处理、剪贴板粘贴上传、语音转文字、PWA 注册，以及渲染层本地化入口。它的共同特点是都要直接接触浏览器 API、Electron/WebUI 差异，或者需要在多个页面复用。

换句话说，这里不负责展示 UI，而是负责把“用户操作”转换成稳定的数据流和后端请求。根据当前片段推断，它是 `renderer` 内部最接近基础设施的一层，下面的 hooks 和页面都依赖它来减少重复实现。

## 相关目录和文件

- `packages/desktop/src/renderer/services/FileService.ts`：文件上传、拖拽文件解析、文件名清理、扩展名判断等核心工具。
- `packages/desktop/src/renderer/services/PasteService.ts`：全局粘贴事件管理，尤其是图片/文件从剪贴板上传。
- `packages/desktop/src/renderer/services/SpeechToTextService.ts`：音频转写入口，区分 Electron 和 Web 两条路径。
- `packages/desktop/src/renderer/services/registerPwa.ts`：渲染层启动时注册 service worker。
- `packages/desktop/src/renderer/services/i18n/index.ts`：渲染层 i18n 初始化与语言切换入口。
- `packages/desktop/src/renderer/services/i18n/i18n-keys.d.ts`：i18n key 的类型约束。
- `packages/desktop/src/renderer/services/i18n/README.md`：i18n 目录约定说明。

与它紧密配套的消费方主要在 `packages/desktop/src/renderer/hooks/file/`、`packages/desktop/src/renderer/pages/`、`packages/desktop/src/renderer/components/`，以及 `packages/desktop/src/renderer/main.tsx`。

## 核心对象

- `FileService`：单例服务对象，承载 `processDroppedFiles`、`isTextFile`、`getCleanFileNames`、`getFileExtension` 等逻辑。它把文件元数据、上传和路径清理统一起来。
- `uploadFileViaHttp(file, conversation_id, ...)`：真正发起 multipart 上传的底层函数，依赖 `getBaseUrl()`，并支持 `AbortSignal`。
- `PasteService`：单例服务对象，维护组件级粘贴处理器注册表、最后聚焦组件，以及全局 `paste` 事件分发。
- `transcribeAudioBlob(blob, languageHint?)`：音频转写统一入口，内部自动选择 Electron IPC 或 Web 端 HTTP。
- `registerPwa()`：负责把 PWA/Service Worker 接入渲染层生命周期。
- `changeLanguage` / i18n 初始化入口：让页面和主进程共享同一套语言资源。

## 运行流程

1. 应用启动时，`packages/desktop/src/renderer/main.tsx` 会先导入 `./services/i18n`，再调用 `registerPwa()`，保证语言环境和 PWA 能力在页面渲染前就绪。
2. 文件拖拽或附件选择进入页面后，页面/Hook 会调用 `FileService.processDroppedFiles(...)`，把 `FileList` 或伪造文件列表整理成统一的 `FileMetadata`，再交给发送框或工作区逻辑。
3. 粘贴文件时，`usePasteService` 注册组件处理器，`PasteService` 监听全局 `paste` 事件，优先放行 input/textarea/contentEditable，避免截断普通文本输入；若命中当前焦点组件，则把事件交给对应 handler。
4. 粘贴图片时，`PasteService` 会生成稳定文件名，调用 `uploadFileViaHttp()` 上传到后端，得到磁盘绝对路径后再回填为文件元数据。
5. 语音输入时，`useSpeechInput` 调 `transcribeAudioBlob()`，Electron 下走 `ipcBridge.speechToText.transcribe.invoke`，Web 下走 `/api/stt`。
6. 语言切换由 `changeLanguage` 驱动，页面上的语言开关直接依赖这里，而不是自己操作 locale 数据。

## 上下游依赖

上游依赖主要是平台和基础设施：

- `@/common/adapter/httpBridge`：提供 `getBaseUrl()`，让 HTTP 上传能同时适配 Electron 本地后端和 Web 同源代理。
- `@/common`、`@/common/types/provider/speech`：提供 IPC 桥和转写结果类型。
- `@/renderer/utils/platform`：判断是否在 Electron 桌面环境。
- 浏览器原生能力：`XMLHttpRequest`、`FormData`、`AbortController`、`ServiceWorker`、`document.addEventListener('paste', ...)`。

下游消费方集中在聊天发送框、工作区、附件按钮、语言切换等页面：

- `packages/desktop/src/renderer/hooks/file/usePasteService.ts`
- `packages/desktop/src/renderer/hooks/file/useDragUpload.ts`
- `packages/desktop/src/renderer/hooks/system/useSpeechInput.ts`
- `packages/desktop/src/renderer/pages/conversation/Workspace/hooks/useWorkspacePaste.ts`
- `packages/desktop/src/renderer/components/chat/SendBox/index.tsx`
- `packages/desktop/src/renderer/components/settings/LanguageSwitcher.tsx`

## 修改时最容易踩的坑

- `FileService` 和 `PasteService` 都是跨页面复用的公共层，改接口前要先看所有调用方；尤其 `usePasteService`、`SendBox`、`Workspace` 会同时依赖它们。
- 粘贴逻辑不能破坏原生输入框行为，`PasteService.shouldAllowNativePaste()` 这条分支很关键。
- 上传和转写都依赖错误码字符串约定，比如 `UPLOAD_ABORTED_ERROR`、`FILE_TOO_LARGE`、`STT_FILE_TOO_LARGE`，前端很多地方是按 message 做分支判断的。
- `isSupportedFile()` 当前实现始终返回 `true`，这是明显的预留设计。根据当前片段推断，后续如果真的启用扩展名过滤，会影响拖拽、粘贴和附件入口的默认行为。
- `SpeechToTextService` 有 30MB 限制，且 Electron/Web 两条路径返回格式不同，改动时要同时验证两端。
- `i18n` 目录里类型文件和资源文件是联动的，改 key 或语言包时要注意类型生成与引用同步。

## 推荐阅读顺序

1. `packages/desktop/src/renderer/services/FileService.ts`
2. `packages/desktop/src/renderer/hooks/file/useDragUpload.ts`
3. `packages/desktop/src/renderer/services/PasteService.ts`
4. `packages/desktop/src/renderer/hooks/file/usePasteService.ts`
5. `packages/desktop/src/renderer/services/SpeechToTextService.ts`
6. `packages/desktop/src/renderer/services/i18n/index.ts`
7. `packages/desktop/src/renderer/main.tsx`
