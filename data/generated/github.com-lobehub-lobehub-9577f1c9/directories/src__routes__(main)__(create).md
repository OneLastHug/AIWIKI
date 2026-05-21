# 目录：src/routes/(main)/(create)

## 它负责什么

`src/routes/(main)/(create)` 是桌面端“生成创作”页面的路由实现区，当前承载两个主入口：

- `/image`：AI 图片生成页面
- `/video`：AI 视频生成页面

从路由注册看，它挂在桌面主路由树下：`src/spa/router/desktopRouter.config.tsx` 中分别注册 `path: 'video'` 和 `path: 'image'`，并通过 `dynamicElement` / `dynamicLayout` 加载 `src/routes/(main)/(create)/video`、`src/routes/(main)/(create)/image` 及其 `_layout`。同步版 `src/spa/router/desktopRouter.config.desktop.tsx` 也直接 import 了 `ImagePage`、`DesktopImageLayout`、`VideoPage`、`DesktopVideoLayout`，说明这两套路由需要在动态路由配置和桌面同步路由配置中保持一致。

这个目录的核心职责不是“创建 agent / page / group”那类通用新建动作，而是“多媒体生成工作台”：展示生成主题列表、输入 prompt、选择模型与参数、上传参考图/关键帧、发起图片或视频生成、展示生成批次结果。

按当前代码片段看，它还没有完全遵循最新的 `src/routes` 薄路由约定：目录内部有 `features/` 和 `components/`，实际业务 UI 大量放在 `src/routes/(main)/(create)/.../features` 下，而不是统一迁到 `src/features/<Domain>`。因此阅读时要把它当作一个“路由目录内自带业务实现的 create 业务岛”。

## 关键组成

直接结构可以分成三层：

第一层是公共 create 生成框架：

- `features/CreateGenerationPage.tsx`
- `features/GenerationLayout/`
- `features/GenerationWorkspace/`
- `features/GenerationInput/`
- `features/GenerationFeed/`
- `components/GenerationModelItem.tsx`
- `components/PromptTitle.tsx`

第二层是图片生成专属实现：

- `image/index.tsx`
- `image/_layout/index.tsx`
- `image/_layout/RegisterHotkeys.tsx`
- `image/features/PromptInput/`
- `image/features/ConfigPanel/`
- `image/features/ImageWorkspace/`
- `image/features/GenerationFeed/`

第三层是视频生成专属实现：

- `video/index.tsx`
- `video/_layout/index.tsx`
- `video/features/PromptInput/`
- `video/features/ConfigPanel/`
- `video/features/VideoWorkspace/`
- `video/features/GenerationFeed/`

`CreateGenerationPage.tsx` 是页面骨架。它接收三个参数：

- `path`：当前路由路径，例如 `/image` 或 `/video`
- `PromptInput`：注入图片或视频自己的输入框
- `Workspace`：注入图片或视频自己的工作区

它用 `useMatch({ path, end: true })` 判断当前页面是否匹配，不匹配时直接返回 `null`。然后用 `useQueryState('topic')` 判断是否处于某个生成主题里：

- 没有 `topic`：视为首页态，居中显示 `PromptInput`，并显示标题
- 有 `topic`：显示 `Workspace`，底部另放一个固定输入区

这就是为什么 `/image` 和 `/video` 的入口文件都很薄：

```tsx
<CreateGenerationPage PromptInput={PromptInput} Workspace={ImageWorkspace} path="/image" />
<CreateGenerationPage PromptInput={PromptInput} Workspace={VideoWorkspace} path="/video" />
```

`GenerationLayout/index.tsx` 是布局壳。它渲染：

- 左侧 `Sidebar`
- 中间 `<Outlet />`
- 可选的 `extra`

图片布局会传入 `extra={<RegisterHotkeys />}`，视频布局没有额外 hotkey 注册。布局还把 store、selector、命名空间等信息传给公共侧边栏：

- 图片：`useImageStore`、`generationTopicSelectors.generationTopics`、`namespace="image"`、`navKey="image"`、`viewModeStatusKey="imageTopicViewMode"`
- 视频：`useVideoStore`、`generationTopicSelectors.generationTopics`、`namespace="video"`、`navKey="video"`、`viewModeStatusKey="videoTopicViewMode"`

`GenerationWorkspace/index.tsx` 是公共工作区状态分发器。它关心 URL 上的 `topic` 和 store 里的 `isCreatingWithNewTopic`：

- 没有 `topic` 或正在创建新主题：显示 `EmptyState`
- 有 `topic`：进入 `Content`

`GenerationWorkspace/Content.tsx` 负责真正加载当前主题的生成批次。它从传入的 store 和 selectors 中取：

- `activeGenerationTopicId`
- `useFetchGenerationBatches`
- `isCurrentGenerationTopicLoaded`
- `currentGenerationBatches`

加载中显示 `SkeletonList`，没有生成结果显示 `EmptyState`，有结果则显示注入进来的 `GenerationFeed`。如果 `embedInput` 为 true，还会在内容后嵌入 `PromptInput`。但在 `CreateGenerationPage` 的 topic 页面中传的是 `embedInput={false}`，输入框由页面底部统一渲染。

`GenerationFeed/index.tsx` 是公共批次列表渲染器。它接收 `batches` 和 `renderBatchItem`，用 `@formkit/auto-animate` 做批次增量动画，并在新批次增加时滚动到底部。图片和视频各自的 `GenerationFeed` 只负责从对应 store 取当前批次，再把每个 batch 渲染为自己的 batch item：

- 图片：`GenerationBatchItem`
- 视频：`VideoGenerationBatchItem`

`GenerationInput/index.ts` 是公共输入组件的导出入口，统一导出：

- `ConfigAction`
- `GenerationInvalidAPIKey`
- `GenerationMediaModeSegment`
- `GenerationPromptInput`
- `ImagePreviewHeader`
- `InlineImageReference`
- `InlineVideoFrames`
- `ModelAction`

图片和视频的 `PromptInput` 都复用这些公共组件，但绑定不同 store、selector、参数配置和模型列表。

## 上下游关系

上游主要是 SPA desktop router。`src/spa/router/desktopRouter.config.tsx` 把 `/image` 和 `/video` 注册成桌面主应用下的两个路由节点：

- `/video` 使用 `src/routes/(main)/(create)/video/_layout` 包裹 `src/routes/(main)/(create)/video`
- `/image` 使用 `src/routes/(main)/(create)/image/_layout` 包裹 `src/routes/(main)/(create)/image`

同步桌面配置 `desktopRouter.config.desktop.tsx` 也 import 对应页面和 layout。根据仓库的 `spa-routes` 约定，这两个配置必须保持路径、层级、index route 一致，否则可能出现某一构建路径空白页。

中游是当前目录自己的公共生成框架。`image/index.tsx`、`video/index.tsx` 并不直接实现复杂 UI，而是把差异组件注入 `CreateGenerationPage`。这形成一种“公共框架 + 媒体类型适配”的结构：

- 公共页面：`CreateGenerationPage`
- 公共布局：`GenerationLayout`
- 公共工作区：`GenerationWorkspace`
- 公共输入基础件：`GenerationInput`
- 公共 feed 容器：`GenerationFeed`
- 图片适配：`ImageWorkspace`、图片 `PromptInput`、图片 `GenerationFeed`
- 视频适配：`VideoWorkspace`、视频 `PromptInput`、视频 `GenerationFeed`

下游主要是几个 store 和能力组件：

图片链路依赖：

- `useImageStore`
- `src/store/image/selectors`
- `src/store/image/slices/generationConfig/hooks`
- `useFetchAiImageConfig`
- `aiProviderSelectors.enabledImageModelList`
- `ModelSwitchPanel`
- `PromptTransformAction`

视频链路依赖：

- `useVideoStore`
- `src/store/video/selectors`
- `src/store/video/slices/generationConfig/hooks`
- `useFetchAiVideoConfig`
- `aiProviderSelectors.enabledVideoModelList`
- `VideoFreeQuotaInfo`
- `ModelSwitchPanel`
- `PromptTransformAction`

认证依赖来自：

- `useUserStore(authSelectors.isLogin)`
- `loginRequired.redirect({ timeout: 2000 })`

也就是说，用户点击生成时，如果未登录会走登录提示/跳转；已登录才调用 `createImage()` 或 `createVideo()`。

## 运行/调用流程

以 `/image` 为例，整体流程是：

1. 用户访问 `/image`
2. router 匹配到 `path: 'image'`
3. 加载 `image/_layout/index.tsx`
4. `ImageLayout` 渲染 `GenerationLayout`
5. `GenerationLayout` 渲染侧边栏 `Sidebar` 和中间 `<Outlet />`
6. `<Outlet />` 渲染 `image/index.tsx`
7. `image/index.tsx` 注入 `PromptInput` 和 `ImageWorkspace` 到 `CreateGenerationPage`
8. `CreateGenerationPage` 判断当前路径是 `/image`
9. 读取 URL query 中的 `topic`
10. 没有 `topic` 时显示居中的图片 prompt 输入区
11. 有 `topic` 时显示 `ImageWorkspace` 和底部输入区
12. `ImageWorkspace` 通过 `GenerationWorkspace` 读取当前主题状态
13. `Content` 调用 store 里的 `useFetchGenerationBatches(activeTopicId)` 获取批次
14. 加载完成且有数据后，图片 `GenerationFeed` 渲染批次列表
15. 用户输入 prompt 后点击生成
16. 图片 `PromptInput` 检查登录态
17. 已登录则调用 `useImageStore((s) => s.createImage)`

`/video` 基本相同，只是 layout 注入 `useVideoStore`，页面注入 `VideoWorkspace` 和视频 `PromptInput`，生成时调用 `createVideo()`。

图片 `PromptInput` 的核心逻辑包括：

- 拉取图片生成配置：`useFetchAiImageConfig()`
- 读取和设置 prompt：`useGenerationConfigParam('prompt')`
- 读取模型和 provider：`imageGenerationConfigSelectors.model/provider`
- 判断模型支持哪些参数：`isSupportedParamSelector('imageUrl')`、`quality`、`resolution`、`size`、`seed`、`steps`、`cfg`、`promptExtend`、`watermark`、`webSearch` 等
- 从 URL query 读取 `prompt` 和 `model`
- 如果 URL 有 `model`，初始化完成后在 `enabledImageModelList` 中找到对应 provider，并调用 `setModelAndProviderOnSelect`
- 如果 URL 有 `prompt` 且已登录，会填入 prompt，然后延迟 100ms 自动 `createImage()`
- 支持参考图：`imageUrl` 和 `imageUrls`
- 根据上传图片尺寸自动设置生成尺寸：`useAutoDimensions()`
- 通过 `ModelSwitchPanel` 切换模型
- 通过 `ConfigAction` 展示图片参数面板
- 通过 `PromptTransformAction mode="image"` 做 prompt 转换

视频 `PromptInput` 的核心逻辑类似，但参数更偏视频：

- 拉取视频生成配置：`useFetchAiVideoConfig()`
- 支持 `imageUrl`、`imageUrls`、`endImageUrl`
- 支持 `aspectRatio`、`resolution`、`size`、`duration`、`seed`
- 支持 `generateAudio`、`cameraFixed`、`watermark`、`promptExtend`、`webSearch`
- 用 `InlineVideoFrames` 管理首帧、参考帧、尾帧
- 通过 `VideoFreeQuotaInfo` 展示视频免费额度信息
- 通过 `PromptTransformAction mode="video"` 做 prompt 转换
- 点击生成时调用 `createVideo()`

一个容易忽略的流程是 URL 参数自动生成。图片和视频都支持类似：

- `/image?prompt=...&model=...`
- `/video?prompt=...&model=...`

页面会先消费 `model` 参数切换模型，再消费 `prompt` 参数填充 prompt，并在登录状态下自动发起生成。处理完成后会把对应 query 参数清空，避免重复执行。

## 小白阅读顺序

建议按“路由入口 -> 公共框架 -> 媒体差异 -> store 下游”的顺序读。

第一步，看路由注册：

- `src/spa/router/desktopRouter.config.tsx`
- `src/spa/router/desktopRouter.config.desktop.tsx`

重点只看 `/image` 和 `/video` 那两段，理解这两个页面如何挂到桌面路由树。

第二步，看两个入口文件：

- `src/routes/(main)/(create)/image/index.tsx`
- `src/routes/(main)/(create)/video/index.tsx`

这两个文件很短，能快速看出 `CreateGenerationPage` 是公共页面容器，图片/视频只是注入不同的 `PromptInput` 和 `Workspace`。

第三步，看两个 layout：

- `src/routes/(main)/(create)/image/_layout/index.tsx`
- `src/routes/(main)/(create)/video/_layout/index.tsx`

这里能看出图片和视频分别绑定哪个 store、selector、namespace、navKey，以及图片额外注册了 hotkeys。

第四步，看公共页面骨架：

- `src/routes/(main)/(create)/features/CreateGenerationPage.tsx`

重点理解 `topic` query 控制“首页输入态”和“主题工作区态”的切换。

第五步，看公共布局和侧边栏：

- `src/routes/(main)/(create)/features/GenerationLayout/index.tsx`
- `src/routes/(main)/(create)/features/GenerationLayout/Sidebar.tsx`
- `src/routes/(main)/(create)/features/GenerationLayout/Header`
- `src/routes/(main)/(create)/features/GenerationLayout/Body`

这里会看到侧边栏是通过 `NavPanelPortal` 和 `SideBarLayout` 接入全局导航面板体系的。

第六步，看工作区数据流：

- `src/routes/(main)/(create)/features/GenerationWorkspace/index.tsx`
- `src/routes/(main)/(create)/features/GenerationWorkspace/Content.tsx`
- `src/routes/(main)/(create)/image/features/ImageWorkspace/index.tsx`
- `src/routes/(main)/(create)/video/features/VideoWorkspace/index.tsx`

重点理解 `selectors` 和 `useStore` 是如何让同一个公共工作区同时服务图片和视频的。

第七步，看输入框：

- `src/routes/(main)/(create)/image/features/PromptInput/index.tsx`
- `src/routes/(main)/(create)/video/features/PromptInput/index.tsx`
- `src/routes/(main)/(create)/features/GenerationInput/index.ts`

这部分代码较长，建议先只抓四件事：配置来源、模型切换、参考图/帧处理、生成按钮调用。

第八步，看结果流：

- `src/routes/(main)/(create)/features/GenerationFeed/index.tsx`
- `src/routes/(main)/(create)/image/features/GenerationFeed/index.tsx`
- `src/routes/(main)/(create)/video/features/GenerationFeed/index.tsx`

公共 `GenerationFeed` 只负责列表、分割线、动画、滚动；具体 batch item 由图片/视频自己渲染。

## 常见误区

第一个误区：看到目录名 `(create)` 就以为它是所有“新建”能力的入口。实际上这里主要是图片/视频生成创作，不是 home 顶部加号菜单里的创建 agent、group、page。那些逻辑在 `src/routes/(main)/home/_layout/hooks/useCreateMenuItems.tsx` 等位置，和这个目录不是一条主线。

第二个误区：以为 `src/routes` 里只有薄路由。根据当前片段，这个目录内部包含大量 `features/` 和 `components/`，实际业务 UI 就写在 route 目录下。这和仓库当前推荐的“route 只放 page/layout，业务放 `src/features`”并不完全一致。阅读时要以现状为准；如果未来维护，才需要考虑渐进迁移。

第三个误区：以为 `image` 和 `video` 是两套完全独立页面。实际上它们共用很多公共骨架：`CreateGenerationPage`、`GenerationLayout`、`GenerationWorkspace`、`GenerationInput`、`GenerationFeed`。差异主要是 store、selector、PromptInput、Workspace、ConfigPanel 和 batch item。

第四个误区：忽略 `topic` query。这个页面不是靠嵌套路由区分“首页”和“详情”，而是通过 URL query 里的 `topic` 判断是否进入某个生成主题。没有 `topic` 时是居中 prompt 首页；有 `topic` 时是生成历史/工作区。

第五个误区：以为生成按钮直接调用后端服务。当前 UI 层只调用 store action：图片是 `createImage()`，视频是 `createVideo()`。真正的接口调用、任务创建、状态更新在 `src/store/image`、`src/store/video` 及其下游服务里，需要继续往 store 层追。

第六个误区：忽略模型能力差异。图片和视频的参数面板不是固定展示所有配置，而是通过 `isSupportedParamSelector(...)` 判断当前模型支持哪些参数，再决定显示 `quality`、`resolution`、`duration`、`seed`、`watermark`、`webSearch` 等控件。

第七个误区：只看 `PromptInput` 的 JSX，忽略 URL 参数副作用。图片和视频都支持从 query 中读取 `prompt` 和 `model`，并可能自动触发生成。调试“为什么一进页面就生成”时，要优先检查 URL 是否带了 `prompt` 参数，以及登录态是否满足。

第八个误区：修改 `/image` 或 `/video` 路由时只改一个 router config。这个仓库要求 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 的桌面路由树保持同步；否则可能在某个运行入口出现页面缺失或空白。
