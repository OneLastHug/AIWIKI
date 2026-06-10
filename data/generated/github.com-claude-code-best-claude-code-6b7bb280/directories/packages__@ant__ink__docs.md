# 目录：packages/@ant/ink/docs

## 它负责什么

`packages/@ant/ink/docs` 是 `@anthropic/ink` 这套终端 React 渲染框架的文档目录，作用是把这个包的核心能力按章节拆开说明，覆盖从入门、布局、文本样式，到主题系统、设计系统组件、滚动、输入、按键绑定、事件与焦点、核心架构、终端集成的一整条使用链路。

根据当前片段推断，这里不是源码实现目录，而是“知识地图”目录。它更像包内的说明书和教学索引，服务对象是要直接使用或维护 `packages/@ant/ink/src` 的开发者。结合 `packages/@ant/ink/package.json` 和 `docs/README.md` 可以看出，这个包的入口是 `src/index.ts`，而 `docs` 负责解释这些导出背后的分层设计和运行方式。

## 直接子目录地图

根据当前片段推断，`packages/@ant/ink/docs` 下**没有直接子目录**，只有一组平铺的 Markdown 文件。目录结构是按章节编号组织的，便于顺序阅读和按主题跳转。

可把它理解成三类内容：

1. 总览文件：`README.md`
2. 入门与基础章节：`01-getting-started.md` 到 `04-theme-system.md`
3. 进阶与内部机制章节：`05-design-system.md` 到 `12-terminal-integration.md`

这种结构说明文档并不是按源码文件逐一对应，而是按概念层级组织。

## 关键入口

最重要的入口是 `README.md`。它先给出 `@anthropic/ink` 的三层架构图，把整体拆成 `core`、`components`、`theme` 三层，然后再把 12 个章节按学习顺序列出来。对理解整个目录来说，`README.md` 就是导航页。

第二个关键入口是 `01-getting-started.md`。它通常承担“如何开始用这个包”的职责，说明安装、基本渲染、基础概念，是后续章节的前置知识。

从源码角度看，文档真正对应的实现入口是 `packages/@ant/ink/src/index.ts`。这个文件集中导出：
- `core/root.js` 里的 `renderSync`、`createRoot`
- `core/ink.js` 里的 `Ink`
- `keybindings/*` 的解析、匹配、上下文与 setup
- `components/*` 的基础组件，如 `Box`、`Text`、`Button`、`ScrollBox`、`AlternateScreen`
- `hooks/*` 的常用 hooks
- `theme/*` 相关类型与主题能力

所以，`docs` 目录的阅读顺序，最好跟着 `src/index.ts` 的导出分组来对照。

## 主流程位置

如果只看“主流程”而不展开每个叶子文件，`docs` 主要围绕这条链路展开：

1. `README.md` 先说明架构分层
2. `01-getting-started.md` 说明如何从 `render` / `createRoot` 开始
3. `02-layout.md`、`03-text-and-styling.md`、`04-theme-system.md` 解释界面如何布局、着色和套主题
4. `05-design-system.md` 和 `06-scrolling.md` 进入更高层的 UI 组件与滚动行为
5. `07-user-input.md`、`08-keybindings.md`、`10-events-and-focus.md` 说明交互输入、快捷键、焦点和事件流
6. `11-core-architecture.md`、`12-terminal-integration.md` 回到底层，解释 reconciler、screen buffer、terminal I/O、alt screen、mouse tracking 等运行机制

换句话说，这个目录的主线不是“页面展示”，而是“终端渲染管线从入口到输出”的解释链。源码上对应的是 `src/core/`、`src/components/`、`src/theme/`、`src/hooks/`、`src/keybindings/` 这些层。

## 推荐阅读顺序

建议按这个顺序读：

1. `README.md`
2. `01-getting-started.md`
3. `02-layout.md`
4. `03-text-and-styling.md`
5. `04-theme-system.md`
6. `05-design-system.md`
7. `07-user-input.md`
8. `08-keybindings.md`
9. `10-events-and-focus.md`
10. `11-core-architecture.md`
11. `12-terminal-integration.md`

`06-scrolling.md` 和 `09-hooks-reference.md` 可以插在中间或按需查阅。前者更偏组件行为，后者更像 API 索引。

## 常见误区

1. 把 `docs` 当成独立产品文档站。这里其实是包内源码文档，目标是解释 `packages/@ant/ink/src` 的实现与用法，而不是对外营销页。

2. 只看 `README.md` 就以为已经理解全部结构。`README.md` 只是总览，真正的使用细节分散在 `01` 到 `12` 的章节里。

3. 以为 `components`、`hooks`、`theme` 是完全分开的三套系统。实际上它们是同一套渲染框架的不同层，很多能力在 `src/index.ts` 中是交叉导出的。

4. 只盯着文档里的 UI 组件名，忽略底层实现。对于 `@anthropic/ink`，真正决定行为的是 `core` 层的 reconciler、layout、terminal I/O、screen buffer 和事件系统，文档后半段专门就是在讲这些。

5. 把章节编号理解成源码目录编号。这里的编号只是阅读顺序，不代表 `src/` 下也按同样编号组织。根据当前片段推断，章节编号只是文档组织方式。
