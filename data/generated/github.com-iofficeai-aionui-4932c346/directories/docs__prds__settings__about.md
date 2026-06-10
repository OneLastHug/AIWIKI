# 目录：docs/prds/settings/about

## 它负责什么

`docs/prds/settings/about` 是“设置页 → 关于 & 检查更新”这一产品需求模块的文档目录，不是业务实现代码目录。它负责把关于页相关能力用 PRD 形式集中描述清楚：应用信息展示、版本号展示、检查更新、预发布版本开关、自动更新下载与安装、手动下载安装包、更新弹窗状态机、外部链接导航、问题报告、应用菜单或启动时触发更新检查等。

从目录内容看，这里聚焦的是桌面端设置页里的 `About` 页面，以及与它耦合很深的 `UpdateModal` 和 `FeedbackReportModal`。它不直接定义 React 组件、IPC provider 或更新服务逻辑，而是为这些实现提供需求索引、验收标准、异常场景、已知局限和建议验证策略。实现侧主要分布在 `packages/desktop/src/renderer/components/settings/SettingsModal/contents/AboutModalContent.tsx`、`packages/desktop/src/renderer/components/settings/UpdateModal.tsx`、`packages/desktop/src/process/bridge/updateBridge.ts`、`packages/desktop/src/process/services/autoUpdaterService.ts` 等位置。

## 直接子目录地图

该目录当前没有更深一级子目录，只有两个 Markdown 文件：

`docs/prds/settings/about/README.md` 是索引页，负责说明本目录覆盖“设置 → 关于”页面的全部功能，并以表格汇总功能点、状态统计、已知局限和建议验证策略。它适合作为进入本目录的第一站，帮助读者快速知道总共有 12 个 `F-ABOUT` 功能点，以及哪些功能属于静态验证、动态验证或仅静态分析。

`docs/prds/settings/about/about-update.md` 是主体 PRD，覆盖 `F-ABOUT-01` 到 `F-ABOUT-12`。它按用户故事、正常流程、异常情况、验收标准组织内容，后面还附有 IPC 通信链路和已知局限汇总。这个文件是理解“关于页 + 检查更新 + 问题报告”完整业务闭环的核心材料。

从相邻目录看，`docs/prds/settings` 下还有 `display`、`llm_providers`、`skills`、`system` 等设置页 PRD 子模块。`about` 是 settings PRD 体系中的一个独立分支，关注产品信息、更新、反馈，不负责模型供应商、显示、技能、系统设置等配置型页面。

## 关键入口

文档入口是 `docs/prds/settings/about/README.md`。它的价值在于给出模块边界：本目录只有一个主体模块文件 `about-update.md`，总计 12 个独立功能点，全部标记为“已实现”。如果只是做需求地图或验收范围梳理，先看这个索引即可。

主体入口是 `docs/prds/settings/about/about-update.md`。文件标题为“设置页 → 关于 & 检查更新 (F-ABOUT)”，开头明确说明覆盖应用信息展示、版本更新、外部链接导航、问题报告。后续章节编号从 `F-ABOUT-01` 到 `F-ABOUT-12`，每个功能点都可以单独作为测试或实现核对单。

实现入口根据当前片段推断主要有三类。渲染层关于页入口是 `packages/desktop/src/renderer/components/settings/SettingsModal/contents/AboutModalContent.tsx`，负责显示应用名、描述、版本 badge、GitHub 图标、检查更新按钮、预发布开关和外部链接列表，同时打开 `FeedbackReportModal`。更新弹窗入口是 `packages/desktop/src/renderer/components/settings/UpdateModal.tsx`，负责监听 `aionui-open-update-modal` 自定义事件和 `ipcBridge.update.open`，驱动检查、下载、安装、错误、成功等状态。主进程更新能力入口是 `packages/desktop/src/process/bridge/updateBridge.ts`，负责提供 `ipcBridge.update.check`、`ipcBridge.update.download`、`ipcBridge.autoUpdate.check`、`ipcBridge.autoUpdate.download`、`ipcBridge.autoUpdate.quitAndInstall` 等 IPC provider。

## 主流程位置

关于页主流程从 `AboutModalContent` 开始。用户进入设置页的关于内容后，页面读取编译期注入的 `__APP_VERSION__` 展示版本号，使用 i18n key 展示应用描述和链接文案。桌面端环境下才显示检查更新区域；非 Electron 环境下，检查更新按钮和预发布开关不渲染。预发布开关保存到 `localStorage('update.includePrerelease')`。

手动检查更新流程由关于页按钮触发。`AboutModalContent` 点击“检查更新”后派发 `CustomEvent('aionui-open-update-modal')`，`UpdateModal` 监听该事件，打开弹窗、重置状态并执行 `checkForUpdates`。检查逻辑先尝试 `ipcBridge.autoUpdate.check.invoke({ includePrerelease })`，用于 electron-updater 路径；随后始终执行 `ipcBridge.update.check.invoke({ includePrerelease })`，用于 GitHub Release 手动检查路径。PRD 将这称为“双路径检查”，其中 manual 路径承担版本信息、release notes 和安装包资产匹配。

下载和安装流程在 `UpdateModal` 内继续分支。若 manual 检查拿到兼容安装包，优先调用 `ipcBridge.update.download.invoke` 下载到系统下载目录，并通过 `ipcBridge.update.downloadProgress.on` 更新进度；完成后进入 `success` 状态，提供“打开文件”和“在文件夹中显示”。若只有 auto-update 可用，则调用 `ipcBridge.autoUpdate.download.invoke`，完成后进入 `downloaded` 状态，用户点击“立即安装”会走 `ipcBridge.autoUpdate.quitAndInstall.invoke`。

问题报告流程在关于页链接区触发。点击“问题报告”不是打开外部链接，而是打开应用内 `FeedbackReportModal`。PRD 描述它要求用户选择模块、填写描述、最多上传 3 张截图，并尝试附加最近 3 天日志后提交到 Sentry。根据当前片段推断，具体弹窗实现位于 `packages/desktop/src/renderer/components/settings/SettingsModal/contents/FeedbackReportModal` 相关文件。

## 推荐阅读顺序

1. 先读 `docs/prds/settings/about/README.md`，建立模块边界、功能点数量、状态统计和已知局限的总览。
2. 再读 `docs/prds/settings/about/about-update.md` 的 `F-ABOUT-01` 到 `F-ABOUT-03`，理解关于页本体：应用信息、检查更新入口、预发布开关。
3. 接着读 `F-ABOUT-04` 到 `F-ABOUT-09`，这是更新系统的主干，包括双路径检查、更新可用、自动下载、手动下载、错误恢复和状态机。
4. 然后读 `F-ABOUT-10` 和 `F-ABOUT-11`，理解关于页下半区的外部资源入口和问题报告。
5. 最后读 `F-ABOUT-12` 与附录 A，串起关于页按钮、应用菜单、启动自动检查、renderer IPC、main IPC、外部服务之间的完整链路。
6. 若要对照代码，再按 `AboutModalContent.tsx`、`UpdateModal.tsx`、`updateBridge.ts`、`autoUpdaterService.ts` 的顺序阅读，实现结构会比较顺。

## 常见误区

不要把 `docs/prds/settings/about` 当成设置页代码目录。这里是 PRD 文档，真正的 UI、IPC、下载、安装、Sentry 提交流程在 `packages/desktop/src` 下。

不要只看 `README.md` 就认为功能很简单。索引页只汇总 12 个功能点，真正的状态机、下载安全限制、双路径检查、异常场景、已知局限都在 `about-update.md`。

不要把“检查更新”理解成单一路径。PRD 明确写的是 auto-update 路径先尝试、manual GitHub Release 路径始终执行；两者职责不同，前者偏自动安装，后者偏版本信息、release notes 和资产选择。

不要忽略 Electron 与 WebUI 的差异。关于页本身可以在不同视图中出现，但检查更新区域仅桌面端显示；外部链接在 Electron 中通过 IPC 调用系统浏览器，在 WebUI 中走浏览器新标签页逻辑。

不要把预发布开关等同于 electron-updater 的 `allowPrerelease`。PRD 和实现片段都显示，预发布过滤主要由 manual check 路径处理，且弹窗打开后通过 `useMemo` 读取本地缓存，因此弹窗已打开时修改开关不会立即影响当前检查。

不要把“问题报告”当普通外链。它在视觉上像链接项，但行为是打开应用内反馈弹窗，并涉及截图、日志收集和 Sentry 提交；这是关于页业务的一部分。
