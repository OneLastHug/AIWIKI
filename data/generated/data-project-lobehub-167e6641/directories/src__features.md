# `src/features` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/src/features`
- 它位于 `src/routes` 的下游，是前端业务实现的主战场之一

## 它负责什么

`src/features` 负责“真正的业务功能实现”。

如果说：

- `src/routes` 回答的是“现在在哪个页面”
- `src/store` 回答的是“数据放哪里”

那么 `src/features` 回答的就是：

- 这个页面真正显示什么
- 交互怎么做
- 哪些业务模块需要拆成独立域

从当前目录能看出，它按业务域组织，而不是按 URL 组织。

## 初学者应该先看哪些文件

推荐顺序：

1. `src/features/Conversation/index.ts`
   这是聊天主链的公共出口。
2. `src/features/ChatInput/index.ts`
   看输入框能力如何被单独封装。
3. `src/features/Pages/index.ts`
4. `src/features/PageExplorer/index.tsx`
   这两者很适合看懂“feature 如何被 route 调用”。
5. `src/features/AgentTasks/index.tsx`
   看任务功能是如何拆分成列表、详情、共享子组件的。
6. `src/features/AgentSetting/index.tsx`
   看配置型功能如何按子域拆分。
7. `src/features/Electron/navigation/routeMetadata.ts`
   看桌面适配逻辑也会作为 feature 的一部分存在。

## 它和其他目录如何交互

最常见的关系是：

```text
src/routes/*
-> import '@/features/...'
-> feature 内部再读 src/store / 调 src/services / 组合 src/components
```

也就是说，`features` 往往处在前端中层：

- 上游是 route
- 下游是 store、service、component、hook

## 目录里的主要业务簇

下面这些簇值得优先建立印象：

### 聊天主链

- `Conversation`
- `ChatInput`
- `ChatMiniMap`
- `PromptTransform`
- `SuggestQuestions`

这一组负责“和 Agent/Group 对话”这件核心事情。

### Agent 与配置

- `AgentBuilder`
- `AgentSetting`
- `AgentHome`
- `AgentInfo`
- `AgentTasks`
- `AgentTaskManager`

这一组负责 Agent 的创建、设置、首页、任务和协作。

### 页面与编辑

- `Pages`
- `PageExplorer`
- `PageEditor`
- `EditorCanvas`
- `EditorModal`

这一组负责页面/文档编辑相关能力。

### 桌面与系统桥接

- `Electron`
- `DesktopNavigationBridge`
- `DesktopFileMenuBridge`
- `OpenInAppButton`

这一组让共享前端页面知道“当前是不是桌面端、该怎么接本地能力”。

### 设置、用户与周边体验

- `Setting`
- `ProfileEditor`
- `User`
- `ShareModal`
- `Billboard`
- `CommandMenu`

## 常见概念解释

### 为什么很多 feature 有 `index.ts` 或 `index.tsx`

这是一个很常见的公开出口模式。

好处是：

- route 不必 import 一大串深路径
- 这个 feature 自己决定哪些实现是“对外公开的”
- 以后内部文件重构时，对外接口可以尽量稳定

### feature 和 component 的区别是什么

在这个项目里，通常可以这样理解：

- `component`
  更通用、更偏基础 UI
- `feature`
  更贴业务、更知道上下文、更可能直接读 store 或调 service

当然现实项目里边界不会永远百分百整齐，但这个区别足够帮你读懂大部分代码。

### feature 一定不碰 store 吗

不是。

恰恰相反，很多 feature 会直接：

- 用 Zustand selector 读状态
- 调 store action 改状态
- 调 service 发请求

因为 feature 本来就是业务层，不只是纯展示层。

### feature 一定比 route 更稳定吗

不一定，但通常更适合承载长期业务实现。

`route` 更容易受 URL 结构影响；
`feature` 更像按业务域积累起来的“可复用页面块”。

## 当前代码快照里一个很值得记住的现象

`src/routes` 和 `src/features` 的边界正在逐步拉开，但还没有彻底拉齐。

这不是推测，而是能直接从目录看到：

- `/page` 路由已经更明显地依赖 `src/features/Pages` 与 `src/features/PageExplorer`
- 一些旧路径仍然把不少实现留在 route 目录里

这意味着你在阅读时要保持弹性：

- 不要死背“所有业务都一定只在 features”
- 但也要知道团队希望未来更多业务往 features 汇拢

## 需要暂时跳过的内容

初学阶段可以先跳过这些 feature：

- `AgentMockDevtools`
- `DevPanel`
- `DevFeatureFlagPanel`
- 很多名称非常短小的 modal / popover / badge 类 feature

原因不是它们不重要，而是它们太容易把你带进局部细节，却帮不了你建立全局图。

## 一句话阅读建议

如果你想知道“这个页面真正干了什么”，大概率最终都要回到 `src/features`。
