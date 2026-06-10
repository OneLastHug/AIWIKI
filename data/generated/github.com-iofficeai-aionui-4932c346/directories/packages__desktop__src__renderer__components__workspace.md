# 目录：packages/desktop/src/renderer/components/workspace

## 它负责什么

这个目录是桌面端 renderer 里“工作区目录选择与最近记录”的小型组件区。根据当前片段推断，它的职责很集中：让用户在多个页面里用同一套交互选择一个 workspace 文件夹，并把最近使用过的目录保存在浏览器本地存储里，供下次快速复用。

这里不是一个通用的大型组件库，而是一个面向“工作区路径输入”的功能模块。它同时承担了三件事：目录选择器的 UI、最近目录列表的读取与写入、以及对外统一导出，方便上层页面直接复用。

## 直接子目录地图

这个目录下当前没有更深一层的子目录，直接子项只有 3 个文件：

- `index.ts`：对外汇总导出
- `WorkspaceFolderSelect.tsx`：核心交互组件
- `recentWorkspaces.ts`：最近工作区的本地存储工具

如果把它当成一个功能目录来看，`WorkspaceFolderSelect.tsx` 是展示层和交互层，`recentWorkspaces.ts` 是状态持久化层，`index.ts` 是门面层。目录结构很浅，说明它的设计目标不是拆分复杂模块，而是把一个高频控件收拢到一个位置，避免页面侧重复实现。

## 关键入口

最直接的入口是 `index.ts`。它只做两类导出：

- `WorkspaceFolderSelect`
- `getRecentWorkspaces`、`addRecentWorkspace`、`DEFAULT_RECENT_WS_KEY`

这意味着外部模块通常不会直接深挖内部文件，而是通过 `@renderer/components/workspace` 或同类别名来取用。就当前代码看，这个目录的对外 API 非常明确：一个 UI 组件，加上一组最近目录的辅助函数。

真正的功能入口是 `WorkspaceFolderSelect.tsx`。它决定了：
- 非桌面环境下走 `Input` 兜底
- Electron 桌面环境下走自定义下拉菜单
- 何时打开系统目录选择器
- 何时读取和更新最近工作区列表

`recentWorkspaces.ts` 则是数据入口和出口：读 `localStorage`、写 `localStorage`、截断长度、去重。

## 主流程位置

主流程基本都收敛在 `WorkspaceFolderSelect.tsx`。

1. 组件先判断运行环境。`isElectronDesktop()` 为假时，直接返回 Arco 的 `Input`，说明这个控件在非桌面环境下不追求完整的目录选择体验，只保留最基本的文本输入能力。

2. 在桌面环境中，组件会从 `recentWorkspaces.ts` 读取最近记录。这个读取发生在渲染期，列表来源是 `recentStorageKey`，默认键是 `aionui:recent-workspaces`。

3. 用户点击触发器后，如果没有最近记录，组件直接调用 `ipcBridge.dialog.showOpen.invoke({ properties: ['openDirectory', 'createDirectory'] })` 打开系统目录选择器；如果有最近记录，则打开自定义菜单，菜单里先展示最近目录，再提供“选择其他文件夹”的动作。

4. 用户选中最近目录时，`onChange(path)` 先把值交给上层，再调用 `addRecentWorkspace(path, recentStorageKey)`，最后关闭菜单。这个顺序说明它把“表单值更新”放在第一优先级，最近记录只是附加状态。

5. 用户从系统对话框选中目录后，同样会触发 `onChange` 和 `addRecentWorkspace`。这条路径与“最近目录点击”保持一致，避免两套逻辑分叉。

6. 清空动作由 `onClear` 控制。如果外部提供了 `onClear`，组件优先交给外部处理；否则自己调用 `onChange('')`。这说明该组件同时兼容“受控清空”和“内部兜底清空”两种模式。

7. 菜单位置不是写死的，而是根据触发器的 `getBoundingClientRect()` 和视口空间动态计算。`estimateMenuHeight()`、`MENU_GAP`、`VIEWPORT_MARGIN`、`MAX_MENU_HEIGHT` 共同控制弹层是向下展开还是向上展开，以及最大高度是多少。这个细节是该目录里最核心的交互实现之一。

从页面接入看，当前至少有三处直接使用它：
- `packages/desktop/src/renderer/pages/guid/components/GuidWorkspaceFootnote.tsx`
- `packages/desktop/src/renderer/pages/cron/ScheduledTasksPage/CreateTaskDialog.tsx`
- `packages/desktop/src/renderer/pages/team/components/TeamCreateModal.tsx`

这说明它不是局部私有控件，而是桌面端多个业务页共享的工作区选择入口。

## 推荐阅读顺序

1. 先看 `index.ts`，确认这个目录对外暴露了什么。
2. 再看 `recentWorkspaces.ts`，理解最近目录是怎么存和去重的。
3. 然后看 `WorkspaceFolderSelect.tsx`，重点看环境分支、菜单定位、选择/清空/浏览三条主路径。
4. 最后回到调用方：`GuidWorkspaceFootnote.tsx`、`CreateTaskDialog.tsx`、`TeamCreateModal.tsx`，看不同页面如何传入文案、测试 id、回调和存储键。

## 常见误区

- 容易把它当成纯 UI 组件。实际上它还负责本地持久化和系统对话框调用，职责比一般表单控件更重。
- 容易忽略桌面与非桌面分支。`isElectronDesktop()` 之后的行为差异很大，非桌面环境并不会走同样的目录选择流程。
- 容易误解最近记录的存储范围。这里不是全局数据库，而是 `localStorage`；清缓存、换浏览器上下文或隐私模式都可能影响可见性。
- 容易忽略最大条数限制。`recentWorkspaces.ts` 里最多只保留 5 条，且新选项会被放到最前面。
- 容易忽略空值语义。`onClear` 存在时由外部决定清空动作，不存在时才由组件自己把值置空。
- 容易误判菜单位置逻辑是固定向下展开。实际上它会根据可用空间决定向上或向下，属于响应式弹层，不是简单的绝对定位菜单。

如果把这个目录理解成一句话，就是：它是桌面端各处“选择 workspace 文件夹”的统一入口，同时顺手管理最近使用目录的轻量状态。
