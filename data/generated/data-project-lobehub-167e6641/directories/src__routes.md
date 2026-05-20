# `src/routes` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/src/routes`
- 它位于 `src/spa/router` 的下游，位于 `src/features` 的上游

## 它负责什么

`src/routes` 主要负责页面段和布局壳。

你可以把它看成“URL 到页面骨架”的中间层：

- 哪个路径有自己的 `_layout`
- 哪个路径是 `index.tsx`
- 哪个路径带动态参数，比如 `[id]`、`[taskId]`
- 页面最终要把哪个 feature 组合出来

从当前目录结构看，主要分组包括：

```text
src/routes
├─ (main)        主桌面/网页 SPA 路由
├─ (mobile)      移动端路由
├─ (popup)       弹窗窗口路由
├─ (desktop)     桌面端专属路由
├─ onboarding    引导流程
└─ share         分享页
```

## 初学者应该先看哪些文件

推荐顺序：

1. `src/routes/(main)/page/_layout/index.tsx`
   这是当前比较“薄”的路由壳示例。
2. `src/routes/(main)/page/index.tsx`
3. `src/routes/(main)/page/[id]/index.tsx`
   这三者一起能帮你理解一个清晰的 route -> feature 分工。
4. `src/routes/(main)/agent/_layout/index.tsx`
   看主聊天页壳层如何组织 sidebar、同步逻辑、hotkey。
5. `src/routes/(main)/agent/index.tsx`
   看一个更“厚”的页面入口现实长什么样。
6. `src/routes/(mobile)/chat/index.tsx`
   看移动端如何复用聊天能力。
7. `src/routes/(popup)/agent/[aid]/index.tsx`
   看 popup 模式怎么只保留轻量会话能力。
8. `src/routes/onboarding/index.tsx`
   看非主业务页怎样直接转到 feature。

## 它和其他目录如何交互

最核心的一条关系是：

```text
src/spa/router/*.config.tsx
-> import('@/routes/...')
-> src/routes/* 页面段
-> import('@/features/...')
-> src/features/* 业务实现
```

除此之外，`src/routes` 还会直接碰到：

- `src/store/*`
  页面级同步状态，例如从 URL 同步当前 pageId、agentId、topicId
- `src/hooks/*`
  页面装配用 hooks
- `src/components/*`
  通用 UI 组件

## 常见概念解释

### 路由分组里的括号是什么意思

像 `(main)`、`(mobile)`、`(popup)` 这样的名字，主要是为了按场景分组阅读。

它们不是“业务模块名”，而是“路由树所属环境/变体”。

### `_layout` 是什么

`_layout` 表示这个路径段的布局层。

常见职责有：

- 渲染侧边栏
- 放 `<Outlet />`
- 做进入该区域时需要的同步逻辑
- 注册热键、标题、桥接逻辑

### `[id]`、`[taskId]` 这类目录是什么

这是动态路径段。

例如：

- `page/[id]`
- `task/[taskId]`
- `agent/[topicId]`

它们表示页面会从 URL 中取参数再决定显示什么。

### “routes 薄、features 厚” 在这里是什么意思

仓库约定希望 `src/routes` 尽量只做：

- 布局壳
- 页面入口
- 参数同步

真正复杂的 UI 和业务逻辑尽量放到 `src/features`。

当前快照里，这个目标已经有明显例子：

- `/page` 路由相对更符合这个方向

但也能直接看到一些尚未完全迁移的现实：

- `src/routes/(main)/agent` 目录里依然有自己的 `features`
- `community`、`home`、`settings` 目录下也还有相当多 route-local 实现

所以更准确的说法是：

- 这是当前项目的目标结构
- 但仓库仍在渐进式迁移中

## 这个目录里最值得先理解的几个大组

### `(main)`

主桌面/网页应用的主体。

从 router 配置和目录都能看出，这里覆盖了：

- `agent`
- `group`
- `community`
- `resource`
- `settings`
- `memory`
- `image`
- `video`
- `eval`
- `tasks`
- `page`

### `(mobile)`

移动端裁剪版路由树。

它不是简单复制 `(main)`，而是保留移动端真正需要的路径。

### `(popup)`

桌面端弹窗会话模式。

特点是：

- 页面少
- 目标单一
- 不带完整主布局

### `onboarding`

新手引导流程。

它在当前仓库里既有 route 级文件，也有直接跳到 feature 的入口。

## 需要暂时跳过的内容

如果你还没有建立整体地图，建议先跳过这些地方：

- `src/routes/(main)/community`
  列表页、详情页、组件都比较多。
- `src/routes/(main)/home`
  包含很多导航、菜单、抽屉和侧边栏细节。
- `src/routes/(main)/settings`
  Tab、映射、provider 细节较多，容易先把人拖进业务细节里。
- route 目录里的测试文件
  先把运行主线看懂，再回来用测试文件校验理解。

## 一句话阅读建议

把 `src/routes` 先看成“页面骨架层”，不要误以为它就是整个前端业务主体。
