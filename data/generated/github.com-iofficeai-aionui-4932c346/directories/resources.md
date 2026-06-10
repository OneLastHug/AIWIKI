# 目录：resources

## 它负责什么

`resources` 是仓库根部的静态资源池，主要服务三类场景：项目展示、桌面应用打包、安装器定制。它不是业务代码目录，也不是运行时状态目录；更像是“对外可见素材 + 构建期图标/脚本”的集中放置区。

从当前目录结构看，`resources` 下面没有进一步拆分子目录，所有文件都直接放在这一层。文件类型以图片、动图、视频、桌面应用图标和 Windows 安装器脚本为主，包括 `app.icns`、`app.ico`、`app.png`、`app_dev.png`、`icon.png`，以及大量用于 README、文档或官网展示的 `.png`、`.gif`、`.mp4` 素材，例如 `aionui-banner-1.png`、`preview.gif`、`multi-agent.gif`、`webui_compressed.mp4` 等。

这个目录的核心角色不是“被源码 import 的 UI 资源目录”，而是项目级资源目录：一部分被文档引用，一部分被 Electron 构建链消费，一部分用于平台安装包定制。

## 直接子目录地图

当前 `resources` 没有直接子目录，只有文件。可以按用途在脑中分成几组：

第一组是应用图标资源：`app.icns`、`app.ico`、`app.png`、`app_dev.png`、`icon.png`。这些通常对应 macOS、Windows、Linux 或开发环境图标，是 Electron 桌面应用打包时最重要的一组资源。

第二组是品牌和 README 展示素材：`aionui-banner-1.png`、`aionui_logo_black_bg.svg`、`aionui_logo_no_border.png`、`aionui_readme_header_0807.png`、`bannerimage.png`、`homepage.png`、`screenshot_1.png`、`screenshot_2.png` 等。这些资源主要解释 AionUi 的产品形态、界面效果和品牌视觉。

第三组是功能演示素材：大量 `.gif` 和 `.png` 文件展示不同能力，例如多 Agent、文件整理、Excel/PPT/论文生成、WebUI、远程访问、多模型、多 LLM 等。典型文件包括 `multi-agent.gif`、`sort_out_folder.gif`、`generate_xlsx.gif`、`readme-demo-assistant-ppt.gif`、`webui-remote.gif`。

第四组是 WebUI/远程相关素材：`webui banner.png`、`webui-remote-example.png`、`webui-remote.png`、`webui remoet.mp4`、`webui_compressed.mp4` 等。文件名中有少量拼写不统一现象，例如 `remoet`，阅读时应按历史素材名理解，不要直接据此推断功能命名。

第五组是 Windows 安装器脚本：`windows-installer-arm64.nsh`、`windows-installer-x64.nsh`。`.nsh` 通常属于 NSIS 安装器脚本片段，和 Windows 打包流程关系更近，不属于前端资源。

## 关键入口

文档侧的入口主要是根目录 `readme.md` 和 `docs/readme/` 下的多语言 README。当前检索结果显示，多语言 README 会引用 `resources/aionui-banner-1.png` 等素材，用于在项目介绍页展示横幅、功能截图和动图。因此，想理解这些图片“给谁看”，应从 README 文档入口开始，而不是从应用源码入口开始。

构建侧的入口在 `package.json` 的构建脚本区域。`dist`、`dist:mac`、`dist:win`、`dist:linux`、`build-mac`、`build-win`、`build-deb` 等命令都会进入 `scripts/build-with-builder.js`。根据当前片段推断，桌面应用图标和安装器资源会在这条 Electron 打包链中被使用，依据是根目录存在 `app.icns`、`app.ico`、Windows `.nsh` 脚本，并且 `package.json` 的打包命令集中指向 electron-builder 包装脚本。

打包后校验入口是 `scripts/afterPack.js`。它解析平台相关的 Electron `resources` 输出目录：非 macOS 时为打包产物下的 `resources`，macOS 时为 `.app/Contents/Resources`。这里的 `resources` 指的是 Electron 打包后的资源目录，不等同于源码根目录的 `resources`，但两者在命名上容易混淆。`afterPack.js` 还会调用 `verifyBundledAioncoreResources` 检查打包后的内置资源是否齐全，并处理跨架构原生模块重建。

## 主流程位置

项目展示主流程大致是：`readme.md` 或 `docs/readme/*` 引用 `resources` 下的图片、动图、视频；用户浏览文档时直接看到这些素材；这些素材不经过运行时代码逻辑，也不参与 IPC、数据库或 Agent 调度。

桌面应用打包主流程大致是：开发者执行 `package.json` 中的 `dist:*` 或 `build-*` 命令；命令进入 `scripts/build-with-builder.js`；Electron 构建配置在打包过程中读取图标和平台资源；构建完成后触发 `scripts/afterPack.js`；`afterPack.js` 定位打包产物里的 Electron `resources` 目录，验证必需资源并按平台/架构处理原生模块。源码根目录 `resources` 里的图标和安装器脚本更接近这条链路的输入材料。

Windows 安装器主流程的位置应关注 `resources/windows-installer-arm64.nsh` 和 `resources/windows-installer-x64.nsh`。根据当前片段推断，它们会被 Windows 打包配置按架构选择，用来补充 NSIS 安装行为；依据是文件名明确区分 `arm64`、`x64`，且项目构建脚本提供 `build-win:arm64` 和 `build-win:x64` 两条架构入口。

## 推荐阅读顺序

建议先看 `resources` 文件列表，建立“这是平铺资源目录”的基本认识，不要一开始逐个打开图片。

第二步看根目录 `readme.md` 和 `docs/readme/`，观察哪些素材被用于项目介绍、功能演示和多语言文档。这样能最快理解大多数 `.png`、`.gif`、`.mp4` 的存在理由。

第三步看 `package.json` 的 `scripts` 字段，重点关注 `dist`、`dist:mac`、`dist:win`、`dist:linux`、`build-*` 命令，理解资源如何进入桌面应用构建链。

第四步看 `scripts/build-with-builder.js` 和 `scripts/afterPack.js`。前者是打包命令的实际入口，后者负责打包后的资源目录定位、资源校验和原生模块处理。读到这里即可把源码根目录 `resources` 与 Electron 产物中的 `resources` 区分开。

最后再按需查看 `resources/windows-installer-*.nsh`。只有在研究 Windows 安装包行为、卸载逻辑、快捷方式或架构差异时，才需要深入这两个脚本。

## 常见误区

不要把根目录 `resources` 当成前端组件资源目录。渲染进程的 UI 代码主要在 `packages/desktop/src/renderer/`，这里的素材更多面向文档、品牌展示和打包流程。

不要把源码目录 `resources` 和 Electron 打包产物里的 `resources` 混为一谈。`scripts/afterPack.js` 中的 `resourcesDir` 指向的是构建输出目录，例如非 macOS 产物中的 `resources` 或 macOS `.app/Contents/Resources`，不是当前源码根部的 `resources`。

不要认为这里的每个展示素材都有对应业务逻辑。很多 `.gif`、`.png` 是 README 或宣传说明用的静态资产，不一定能在源码中找到同名功能入口。

不要随意重命名资源文件。README、多语言文档、构建配置或安装器配置可能直接按文件名引用它们。尤其是 `app.icns`、`app.ico`、`app.png`、`windows-installer-arm64.nsh`、`windows-installer-x64.nsh` 这类文件，改名会影响构建或安装包生成。

不要仅凭文件名判断最终产品能力。`resources` 保存的是展示结果或构建素材，不是能力实现本身。要追踪真实实现，应回到 `packages/desktop/src/process/`、`packages/desktop/src/renderer/`、`packages/web-host/`、`scripts/` 等代码目录。
