# 目录：apps/desktop/src/main/services

## 它负责什么

`apps/desktop/src/main/services` 是 LobeHub Desktop 的 Electron 主进程服务层。它不直接渲染 UI，也不负责 React 状态管理，而是把桌面端才能访问的能力封装成可复用的主进程服务，例如本地文件存储、文件搜索、内容搜索、网关连接等。

从已读代码看，这一层的共同特点是：

- 运行在 Electron main process，能访问 Node.js API，例如 `node:fs`、`node:path`。
- 通过统一基类 `ServiceModule` 持有 `App` 实例，从而访问桌面应用上下文，例如 `app.appStoragePath`。
- 通常被 `apps/desktop/src/main/controllers` 中的 IPC controller 调用，再经由 preload / IPC 暴露给 renderer。
- 和 Web 端服务不同，这里处理的是桌面本地能力：本地文件路径、本地索引、系统搜索、桌面连接状态等。

目录当前包含：

```text
apps/desktop/src/main/services
├── __tests__/
│   ├── fileSearchSrv.test.ts
│   └── fileSrv.test.ts
├── contentSearchSrv.ts
├── fileSearchSrv.ts
├── fileSrv.ts
├── gatewayConnectionSrv.ts
└── index.ts
```

其中 `index.ts` 是基础入口，其他 `*Srv.ts` 是具体服务实现。

## 关键组成

`index.ts` 定义了所有服务的共同基类：

```ts
export class ServiceModule {
  constructor(public app: App) {
    this.app = app;
  }
}

export type IServiceModule = typeof ServiceModule;
```

这个类很薄，只做一件事：把 `App` 实例注入到服务里。服务类继承它后，可以统一访问主进程应用上下文。比如 `FileService` 通过 `this.app.appStoragePath` 拼出桌面端本地文件存储路径。

`fileSrv.ts` 是本目录里最核心、最具代表性的服务。它默认导出 `FileService`，并额外导出：

- `FileNotFoundError`：本地文件不存在时抛出的专用错误。
- `FileMetadata`：上传后返回给上层的文件元信息类型。

`FileService` 主要负责桌面端本地文件生命周期：

- `uploadFile(...)`：把 renderer 或服务端传来的文件内容写入本地存储。
- `getFile(path)`：读取 `desktop://` 协议路径对应的本地文件内容。
- `deleteFile(path)`：删除 `desktop://` 协议路径对应的本地文件。
- 内部 `isLegacyPath(path)`：判断路径是否是历史上传目录格式，用于兼容旧数据。

它依赖这些关键模块：

- `node:fs`、`node:fs/promises`：读写和删除本地文件。
- `node:path`：拼接本地路径。
- `@/const/dir` 中的 `FILE_STORAGE_DIR`、`LOCAL_STORAGE_URL_PREFIX`。
- `@/utils/file-system` 的 `makeSureDirExist`。
- `@/utils/logger` 的 `createLogger`。
- `@lobechat/electron-server-ipc` 中的桌面 IPC 类型。

`uploadFile` 的核心逻辑是：拿到 `content`、`filename`、`hash`、`path`、`type` 后，把文件写到：

```text
this.app.appStoragePath / FILE_STORAGE_DIR / filePath
```

同时旁边写一个同名 `.meta` 文件，保存：

```ts
{
  createdAt,
  filename,
  hash,
  size,
  type,
}
```

最终返回给上层的路径不是本地绝对路径，而是类似：

```text
desktop://some/path/file.png
```

这是一个桌面端内部协议路径，用来让 renderer 或上层业务以稳定格式引用本地文件。

`getFile` 的重点是兼容两种路径格式：

- 新格式：直接在 `FILE_STORAGE_DIR` 根目录下按业务传入路径存储。
- 旧格式：形如 `{timestamp}/{hash}.{ext}`，会优先从 `FILE_STORAGE_DIR/uploads` 读取。

如果旧格式读取失败，还会 fallback 到新存储根目录再试一次。读取成功后，它会优先从 `.meta` 文件里拿 MIME type；如果 `.meta` 不存在，则根据扩展名兜底推断，例如 `png`、`jpeg`、`gif`、`webp`、`svg`、`pdf`。

`fileSearchSrv.ts` 是本地文件搜索服务。它默认导出 `FileSearchService`，继承 `ServiceModule`，但自身不直接实现搜索算法，而是委托给：

```ts
createFileSearchModule()
```

相关类型来自：

```ts
@/modules/fileSearch
@lobechat/electron-client-ipc
```

它暴露的方法包括：

- `search(query, options)`：把字符串查询转成 `keywords` 后交给底层实现。
- `checkSearchServiceStatus()`：检查搜索服务可用性。
- `updateSearchIndex(path?)`：更新指定路径或全局索引。
- `glob(params)`：执行 glob 文件匹配。

也就是说，`FileSearchService` 更像是主进程服务层的适配器，真正的平台差异和搜索实现藏在 `@/modules/fileSearch` 里。

`contentSearchSrv.ts` 根据文件名推断是“内容搜索”服务，可能与文件搜索不同：`fileSearchSrv.ts` 更关注文件名、路径、glob 和索引状态，而 `contentSearchSrv.ts` 应该面向文件内容或应用数据内容检索。由于当前读取片段没有展开该文件正文，具体方法名需要以源码为准。

`gatewayConnectionSrv.ts` 根据文件名推断是桌面端网关连接服务，用于维护或查询 Desktop 与某种 gateway/device gateway 的连接状态。结合仓库结构里存在 `apps/device-gateway`，它很可能承担桌面主进程侧的连接协调职责。这里属于根据当前片段推断，依据是文件命名和仓库中 `device-gateway` 应用的存在。

`__tests__/fileSrv.test.ts` 和 `__tests__/fileSearchSrv.test.ts` 表明此目录至少对文件服务和文件搜索服务有单元测试覆盖。阅读业务逻辑时，测试文件是理解边界条件的好入口，尤其适合确认 legacy path、`.meta`、搜索服务状态等行为。

## 上下游关系

上游通常是 Electron IPC controller。根据桌面开发约定，renderer 不应直接调用主进程服务，而是走这样的链路：

```text
React renderer / src/services/electron
  -> preload 暴露的 IPC client
  -> apps/desktop/src/main/controllers
  -> apps/desktop/src/main/services
  -> Node.js / 本地系统 / 本地模块
```

也就是说，`services` 本身不是 IPC 边界，它是 controller 后面的业务执行层。controller 负责把方法暴露给 IPC，service 负责真正做事。

下游主要分三类：

第一类是 Node.js 系统能力。`FileService` 明确使用了 `fs`、`path`、`Buffer` 等 Node 能力，这些只能在主进程或受控 preload 中使用，不能直接放到普通 Web renderer 代码里。

第二类是桌面应用上下文。所有服务继承 `ServiceModule` 后都拿到 `app: App`，因此可以访问桌面应用级状态，例如 `appStoragePath`。这也是为什么文件服务不自己决定根目录，而是从 `App` 注入的上下文里取。

第三类是功能模块。`FileSearchService` 不直接搜索，而是调用 `@/modules/fileSearch` 创建出的实现。这样可以把“服务层 API”和“平台搜索实现”分开：service 负责稳定暴露方法，module 负责适配 macOS、Windows、Linux 或具体搜索引擎。

从类型关系看，服务层还和 IPC 类型包有关：

- `@lobechat/electron-client-ipc`：偏 renderer 调 main 的参数和结果类型。
- `@lobechat/electron-server-ipc`：偏 main/server 侧返回结构。

这些类型让主进程和 renderer 之间的调用保持一致。

## 运行/调用流程

以文件上传为例，典型流程是：

1. renderer 侧选择或生成文件内容。
2. renderer 通过 electron IPC service 发起上传请求。
3. 主进程 controller 接收到 IPC 调用。
4. controller 调用 `FileService.uploadFile(...)`。
5. `FileService` 使用 `app.appStoragePath`、`FILE_STORAGE_DIR` 和业务传入的 `path` 拼出保存位置。
6. 服务确保目录存在，然后把 `ArrayBuffer` 或 base64 字符串转成 `Buffer`。
7. 写入真实文件。
8. 写入同路径旁边的 `.meta` 文件。
9. 返回 `desktop://...` 路径和元信息。

以文件读取为例：

1. 上层传入 `desktop://...` 路径。
2. `getFile` 先校验路径必须以 `desktop://` 开头。
3. 把 `desktop:/xxx` 或 `desktop://xxx` 统一规范化成 `desktop://xxx`。
4. 去掉协议头，得到相对路径。
5. 判断是否为 legacy path。
6. legacy path 优先读 `FILE_STORAGE_DIR/uploads`，失败后 fallback 到 `FILE_STORAGE_DIR` 根目录。
7. 新格式直接读 `FILE_STORAGE_DIR` 根目录下的对应路径。
8. 尝试读取 `.meta` 获取 MIME type。
9. 如果 `.meta` 不存在，根据扩展名兜底判断 MIME type。
10. 返回 `{ content, mimeType }`。

以文件搜索为例：

1. 上层传入 `query` 和搜索选项。
2. `FileSearchService.search(query, options)` 把 `query` 合并成 `{ ...options, keywords: query }`。
3. 调用内部 `impl.search(...)`。
4. `impl` 来自 `createFileSearchModule()`，实际搜索逻辑由 `@/modules/fileSearch` 决定。
5. 返回 `FileResult[]` 给 controller，再通过 IPC 回到 renderer。

搜索索引更新和 glob 匹配也是类似模式：service 层只做薄封装，真正能力下沉到 `impl`。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `apps/desktop/src/main/services/index.ts`  
   这个文件最短，但能理解所有 service 为什么都有 `app`。先明白 `ServiceModule` 是“主进程 App 上下文注入基类”。

2. 再读 `apps/desktop/src/main/services/fileSrv.ts`  
   这是最完整的代表服务，能看到桌面服务层如何使用 Node API、如何处理本地路径、如何包装错误、如何写日志、如何兼容历史数据。

3. 接着读 `apps/desktop/src/main/services/__tests__/fileSrv.test.ts`  
   测试通常比实现更容易看出作者希望保证哪些行为。重点看上传、读取、删除、legacy path、`.meta` 缺失时 MIME type 推断等场景。

4. 再读 `apps/desktop/src/main/services/fileSearchSrv.ts`  
   这个文件很薄，适合理解“服务层不一定承载全部逻辑，也可以只是稳定门面”。重点看它如何把调用转发给 `@/modules/fileSearch`。

5. 然后读 `@/modules/fileSearch` 相关实现  
   如果想深入搜索能力，下一站不是继续在 `services` 目录里找，而是去看 `apps/desktop/src/main/modules/fileSearch` 或路径别名实际指向的模块目录。

6. 最后读 `contentSearchSrv.ts` 和 `gatewayConnectionSrv.ts`  
   这两个可以放在后面，因为从目录结构看，它们分别是内容检索和网关连接的专项服务。先掌握 `ServiceModule`、`FileService`、`FileSearchService` 的模式后，再看它们会更顺。

7. 如果想看完整调用链，再去 `apps/desktop/src/main/controllers`  
   service 不是 IPC 入口。要知道 renderer 怎么调到它，需要看 controller 注册和对应方法。

## 常见误区

第一，容易把 `services` 当成 renderer service。这里不是 `src/services` 那种前端业务服务，而是 Electron main process 服务。它可以访问 Node.js 和系统资源，普通浏览器环境不能运行这里的代码。

第二，`desktop://...` 不是本地文件绝对路径。它是桌面端内部协议式引用。真正文件位置由 `app.appStoragePath`、`FILE_STORAGE_DIR` 和相对路径拼出来。上层应该传递和保存 `desktop://` 路径，而不是泄漏系统绝对路径。

第三，`.meta` 文件不是可有可无的装饰。`FileService.getFile` 会优先从 `.meta` 读取 MIME type。没有 `.meta` 时虽然能靠扩展名兜底，但准确性会下降，未知类型会落到 `application/octet-stream`。

第四，legacy path 逻辑不能随便删。`isLegacyPath` 判断首段是否为纯数字，目的是兼容历史上传格式 `{timestamp}/{hash}.{ext}`。读取和删除时都需要考虑旧路径，否则老用户本地文件可能无法访问。

第五，`FileSearchService` 不是搜索算法本体。它只是调用 `createFileSearchModule()` 得到的实现，并把 `query` 转成 `keywords`。要研究索引、平台差异、glob 细节，应继续看 `@/modules/fileSearch`。

第六，service 层通常不直接暴露给 renderer。标准链路应该经过 controller 和 IPC 类型定义。新增桌面能力时，不能只加一个 service 方法，还要考虑 controller 注册、IPC 类型、renderer 调用封装和测试。

第七，不要忽略 `App` 注入。很多路径和运行环境信息来自 `this.app`。如果在测试或新服务里手动构造 service，需要提供足够的 `App` mock，否则像 `appStoragePath` 这样的属性会直接影响文件读写位置。

第八，看到 `contentSearchSrv.ts` 和 `gatewayConnectionSrv.ts` 时，不要先假设它们是 UI 功能。根据当前片段推断，它们仍然属于主进程服务层，应该从“被 controller 调用，向下访问本地模块或系统能力”的角度理解。
