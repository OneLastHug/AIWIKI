# 子系统：packages/coding-agent/src/utils

## 解决什么问题
`packages/coding-agent/src/utils` 是 coding-agent 的通用工具层，集中放置跨模块复用、但又不适合下沉到 `core` 的“胶水型能力”。这里主要处理三类问题：第一类是跨平台兼容，比如 shell 发现、浏览器打开、剪贴板写入、版本检查、Windows 自更新；第二类是输入输出和文本处理，比如路径归一化、ANSI 清理、JSON、HTML、Markdown changelog 链接修正；第三类是重任务的独立封装，比如图片解码/缩放/转码和工具二进制下载管理。  
根据当前片段推断，这个目录的设计目标是把平台细节、外部命令、网络请求、worker 线程、原生能力封装在一起，避免这些细节散落到 `cli/`、`core/`、`modes/` 中。

## 相关目录和文件
直接相关的上游调用点主要在 `packages/coding-agent/src/main.ts`、`packages/coding-agent/src/cli/file-processor.ts`、`packages/coding-agent/src/package-manager-cli.ts`、`packages/coding-agent/src/modes/interactive/interactive-mode.ts`。测试主要在 `packages/coding-agent/test/*.test.ts`，例如 `paths.test.ts`、`clipboard.test.ts`、`image-processing.test.ts`、`syntax-highlight.test.ts`、`trust-selector.test.ts`。  
目录内文件大致可分组：路径与进程基础设施如 `paths.ts`、`child-process.ts`、`shell.ts`、`open-browser.ts`；文本与展示如 `ansi.ts`、`json.ts`、`html.ts`、`syntax-highlight.ts`、`frontmatter.ts`、`changelog.ts`；系统集成如 `clipboard.ts`、`clipboard-native.ts`、`clipboard-image.ts`、`fs-watch.ts`、`git.ts`、`version-check.ts`、`windows-self-update.ts`；图片链路如 `image-resize.ts`、`image-resize-core.ts`、`image-resize-worker.ts`、`image-convert.ts`、`exif-orientation.ts`、`photon.ts`；工具管理如 `tools-manager.ts`。`highlight-js-lib-index.d.ts` 是配套类型声明。

## 核心对象
这里没有大型领域对象，核心是若干小而稳定的接口和函数。最关键的是 `paths.ts` 里的 `PathInputOptions`、`canonicalizePath`、`normalizePath`、`resolvePath`、`getCwdRelativePath`；`changelog.ts` 里的 `ChangelogEntry`、`parseChangelog`、`normalizeChangelogLinks`；`version-check.ts` 里的 `LatestPiRelease`、`comparePackageVersions`、`checkForNewPiVersion`；`image-resize.ts` 里的 `resizeImage`、`formatDimensionNote`；`shell.ts` 里的 `ShellConfig`、`getShellConfig`、`getShellEnv`；`tools-manager.ts` 里的 `getToolPath`。  
这些函数的共同点是：输入面向上层业务，输出尽量是可直接消费的基础结果，不把平台分支暴露给调用方。

## 运行流程
启动时，`main.ts` 和 `cli/` 会先借助 `paths.ts`、`shell.ts`、`open-browser.ts`、`windows-self-update.ts` 完成环境准备与命令执行基础设施。处理文件时，`cli/file-processor.ts` 会通过 `image-resize.ts`、`mime.ts`、`paths.ts` 把用户输入规范化后交给后续流程。交互模式里，`modes/interactive/interactive-mode.ts` 会使用 `clipboard.ts`、`clipboard-image.ts`、`ansi.ts`、`changelog.ts` 来完成复制、图片读取、终端输出清理和 changelog 链接修正。  
图片链路中，`image-resize.ts` 会优先在 worker 线程里做缩放，失败后再退回进程内实现；`version-check.ts` 会按环境变量决定是否联网检查最新版本；`tools-manager.ts` 则在本地工具缺失时按平台下载或选择系统二进制。根据当前片段推断，这些工具函数大多是“先尝试最优路径，失败再降级”的模式。

## 上下游依赖
上游依赖主要来自 `core/`、`cli/`、`modes/interactive/` 和测试代码；下游依赖则是 Node/Bun 运行时能力、平台命令、GitHub API、剪贴板原生插件、worker 线程，以及图片处理库 `photon.ts` 和相关转码实现。  
其中 `tools-manager.ts` 直接依赖 `getBinDir` 和 `APP_NAME`，说明它受 `config.ts` 与安装布局约束；`shell.ts` 同样依赖 `getBinDir` 来把内置工具目录放进 `PATH`；`clipboard.ts` 依赖 `clipboard-native.ts`、`clipboard-image.ts` 和系统命令 `pbcopy`、`clip`、`wl-copy`、`xclip`、`xsel`；`version-check.ts` 依赖 `pi-user-agent.ts` 生成请求头。测试层面，`packages/coding-agent/test` 对这些工具做了大量行为验证，说明它们是稳定契约的一部分。

## 修改时最容易踩的坑
第一，路径与链接处理很容易误伤平台差异，`paths.ts` 同时处理 `~`、`file://`、Unicode 空格、`@file` 前缀和 symlink 归一化，改动时要保留这些入口。第二，剪贴板逻辑是多级降级链，Linux 上既区分 Wayland/X11，也区分远程会话和本地会话，简单改成单一路径会回退失败。第三，`image-resize.ts` 兼容 Node worker、Bun compiled executable 和进程内 fallback，不能只测一种运行时。第四，`changelog.ts` 会把相对链接改写到仓库 tag，对目录/文件的判断依赖路径形态，误判会生成错误 GitHub 链接。第五，`tools-manager.ts` 和 `version-check.ts` 都涉及网络和平台命令，离线模式、超时和错误吞掉策略需要保持一致。第六，这里很多函数都被测试直接覆盖，改签名或改返回语义时很容易牵连 `packages/coding-agent/test`。

## 推荐阅读顺序
先读 `paths.ts`、`shell.ts`、`child-process.ts`，建立基础执行环境的心智模型；再读 `clipboard.ts`、`clipboard-image.ts`、`clipboard-native.ts`，理解跨平台 I/O 的降级策略；接着看 `image-resize-core.ts`、`image-resize.ts`、`image-resize-worker.ts`、`image-convert.ts`，把图片处理链路串起来；然后看 `changelog.ts`、`version-check.ts`、`tools-manager.ts`，理解文本修正、版本探测和外部工具管理；最后对照 `packages/coding-agent/src/cli/file-processor.ts`、`packages/coding-agent/src/modes/interactive/interactive-mode.ts` 和对应测试，确认这些工具在真实流程里怎么被组合使用。
