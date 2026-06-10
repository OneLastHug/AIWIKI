# 目录：packages/desktop/src/renderer/pages/conversation
## 它负责什么
这个目录是桌面端 renderer 里“会话页”的总装配区，负责把一次 conversation 的入口、布局、消息流、工作区、历史列表、预览面板，以及不同平台的会话实现统一起来。根据当前片段推断，它不是单纯的聊天消息页，而是一个围绕 conversation 生命周期运转的页面域：路由进来后先定位会话，再根据会话类型分发到 `acp`、`aionrs`、`legacy` 等平台实现，同时把 `Workspace`、`GroupedHistory`、`Preview` 这些侧向能力挂到同一套布局里。

## 直接子目录地图
这个目录下的一级角色很清楚：

`components`：页面级组合件和布局件，核心是 `ChatConversation.tsx`、`ChatLayout/`、`ChatSlider.tsx`、`WorkspaceCollapse.tsx`、`ConversationTitleMinimap/` 等。这里更像页面骨架和壳层。

`Messages`：消息渲染与消息列表状态层，包含 `MessageList.tsx`、各种 message 片段组件、`hooks.ts`、`artifacts.tsx`。它负责把后端流式消息、工具调用、思考态、权限态等统一显示出来。

`Workspace`：会话工作区面板，管理文件树、变更列表、拖拽导入、粘贴确认、上下文菜单、搜索和文件操作。它是“围绕会话上下文的文件工作区”。

`Preview`：独立可复用的文档预览模块，对外通过 `Preview/index.ts` 统一导出 viewer、editor、panel、context、hooks、theme、utils。

`GroupedHistory`：按分组展示的会话历史侧栏，支持选择、拖拽排序、批量操作、导出、分组展开收起和搜索。

`platforms`：平台分发层，里面有 `acp/`、`aionrs/`、`gemini/`、`legacy/`，外加 `useConversationCommandQueue.ts` 和 `useConversationCommandQueue` 相关逻辑，说明这里承接不同会话后端协议。

`runtime`：会话运行态视图层，负责把 backend runtime、发送/停止本地状态、turn 完成事件同步成前端可读状态。

`hooks`、`utils`：页面域共享 hooks 与辅助函数，覆盖布局约束、标题重命名、平台检测、缓存、会话创建参数、runtime 工具等。

## 关键入口
最外层入口是 `index.tsx`。它从路由参数拿到会话 `id`，通过 `useSWR` 和 `getConversationOrNull` 读取会话缓存，监听 `ipcBridge.conversation.listChanged` 做刷新，并在会话不存在时提示后跳回首页。这个文件是“路由级入口”。

真正的页面编排入口是 `components/ChatConversation.tsx`。它负责判断会话类型，组装 `ChatLayout`，再把平台专属的聊天组件塞进去。这里还能看到“关联会话”“新建相似会话”等会话导航动作，也说明它是会话页的中枢。

布局核心在 `components/ChatLayout/index.tsx`。它处理标题区、工作区宽度、预览区宽度、折叠状态、移动端动作槽位等，是整个 conversation 页面最重要的壳。

消息主渲染入口在 `Messages/MessageList.tsx`，平台聊天实现再把它嵌进自己的 provider 链路里，比如 `platforms/acp/AcpChat.tsx` 和 `platforms/aionrs/AionrsChat.tsx`。

## 主流程位置
主流程可以按“路由进入 -> 会话装配 -> 平台渲染 -> 消息与侧栏联动”来理解：

1. `index.tsx` 读取会话，处理不存在、切换会话、标题同步和预览关闭。
2. `components/ChatConversation.tsx` 根据会话类型选择 `AcpChat`、`AionrsChat` 或 `LegacyReadOnlyConversation`，并把 `ChatLayout` 作为统一外壳。
3. `components/ChatLayout/index.tsx` 负责把正文区、右侧工作区、预览面板、标题编辑、折叠逻辑和拖拽分割器组合起来。
4. 平台聊天组件内部再通过 `ConversationProvider`、`ConversationArtifactProvider`、`MessageListProvider` 等上下文，把消息流和业务状态串起来。
5. `runtime/useConversationRuntimeView.ts` 与 `runtime/conversationRuntimeViewStore.ts` 维护发送、停止、完成、删除等状态，保证 UI 和 backend runtime 同步。
6. `Workspace/index.tsx`、`GroupedHistory/index.tsx`、`Preview/index.ts` 分别作为侧边工作区、历史列表和预览面板被嵌入布局。

## 推荐阅读顺序
建议先看 `index.tsx`，建立路由入口印象；再看 `components/ChatConversation.tsx`，理解平台分发和页面装配；然后看 `components/ChatLayout/index.tsx`，把布局骨架和预览/工作区关系串起来；接着读 `platforms/acp/AcpChat.tsx`、`platforms/aionrs/AionrsChat.tsx`，看消息区如何被包进不同平台；最后补 `Messages/hooks.ts`、`Workspace/index.tsx`、`GroupedHistory/index.tsx`、`runtime/useConversationRuntimeView.ts`。

## 常见误区
一个常见误区是把这个目录只看成“聊天消息页”。实际上它还承载历史、工作区、预览、平台适配和 runtime 协调。

第二个误区是把 `Preview` 当成 conversation 专属组件。根据 `Preview/index.ts` 的导出结构，它更像独立可复用的文档预览子系统，只是在 conversation 页里被接入。

第三个误区是忽略 `runtime`。这里的状态不是普通本地 UI 状态，而是把 backend runtime、turn 完成事件、本地发送中状态统一成一个前端可订阅视图，直接影响能不能发消息、能不能停止、页面是否处于处理态。

第四个误区是把 `platforms` 里的目录理解成可随意替换的视图实现。实际上它们依赖同一套 `ConversationProvider`、消息列表、artifact、runtime 约定，平台之间是同构但不等价的分支。
