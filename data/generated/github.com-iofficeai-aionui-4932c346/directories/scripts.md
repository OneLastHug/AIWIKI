# 目录：scripts

## 它负责什么

`scripts` 是仓库根部的工程脚本中心，主要承担“把源码变成可运行、可发布、可验证产物”的外围流程，而不是承载应用业务逻辑。它连接了 Electron 桌面端构建、WebUI/CLI 打包、i18n 类型生成与校验、发布资产整理、安装脚本、冒烟测试、性能基准、PR 自动化等流程。

从 `package.json` 可以看到，许多顶层命令直接落到这里：`webui`、`resetpass`、`dist`、`build-*`、`i18n:types`、`bench:report`、`bench:startup`、`postinstall` 等都调用 `scripts/*`。因此这个目录更像项目的“工程操作层”：它知道仓库布局、打包工具、发布产物命名规则、CI/本地自动化约束，但通常不定义产品功能本身。

目录规模不算深，直接子目录只有 `scripts/codemods`，大多数脚本直接平铺在 `scripts` 根下。根据当前片段推断，这种布局是为了让 `package.json`、CI、electron-builder hook 和人工运维命令能以稳定路径引用脚本。

## 直接子目录地图

`scripts/codemods` 是目前唯一的直接子目录，用于放代码迁移或批量改写脚本。当前可见文件是 `scripts/codemods/assistantSnakeCase.ts`，从命名看，它属于一次性或低频运行的源码结构调整工具，而不是常规构建链路的一部分。

`scripts` 根目录本身按职责可分成几组。第一组是构建和打包：`build-with-builder.js`、`build-mcp-servers.js`、`afterPack.js`、`afterSign.js`、`rebuildNativeModules.js`、`prepareAioncore.js`、`prepareHubResources.js`、`resolveAioncoreVersion.js`。第二组是 WebUI/CLI 与安装：`webui.ts`、`pack-web-cli.js`、`install-web.sh`、`install-ubuntu.sh`、`smoke-test-web-cli.sh`、`smoke-test-install-web.sh`、`packaged-launch.mjs`。第三组是发布资产：`prepare-release-assets.sh`、`verify-release-assets.sh`、`create-mock-release-artifacts.sh`、`prepare-managed-acp-tools.sh`。第四组是质量检查和类型生成：`generate-i18n-types.js`、`check-i18n.js`、`check-agents-invoke.js`、`postinstall.js`。第五组是性能与自动化：`run-benchmarks.ts`、`benchmark-startup.ts`、`benchmark-acp-startup.ts`、`pr-automation.sh`、`pr-automation.conf`、`fix-issues-daemon.sh`、`fix-sentry-daemon.sh`。

## 关键入口

最重要的构建入口是 `scripts/build-with-builder.js`。`package.json` 中的 `dist`、`dist:mac`、`dist:win`、`dist:linux`、`build-mac`、`build-win`、`build-deb` 等命令都指向它。它负责协调 `electron-vite` 与 `electron-builder`，并包含增量构建、跳过 Vite 编译、跳过 native rebuild、仅打包等控制点。它还维护构建哈希，读取 `package.json`、锁文件、`packages/desktop/electron.vite.config.ts`、`packages/desktop/electron-builder.yml`、`justfile`、`packages/desktop/src`、`packages`、`public`、`scripts` 等路径来判断源变化。

`afterPack.js` 和 `afterSign.js` 是 electron-builder 生命周期入口。`afterPack.js` 在打包后验证资源目录、检查 `app.asar.unpacked`、校验 bundled Aioncore 资源，并在必要时重建 native modules。`afterSign.js` 主要处理 macOS 签名和 notarization：先检查 app 是否已签名，必要时尝试 ad-hoc 签名，只有在 Apple 凭据存在时才继续 notarization。

`generate-i18n-types.js` 与 `check-i18n.js` 是 i18n 主入口。前者从参考语言 locale 模块生成 `packages/desktop/src/renderer/services/i18n/i18n-keys.d.ts`，后者检查类型文件是否同步、语言模块是否完整一致。`package.json` 的 `i18n:types` 直接调用前者，项目贡献说明中也要求修改 renderer、locales 或 i18n 配置后运行相关检查。

`webui.ts` 是 WebUI 运行入口，`package.json` 中的 `webui`、`webui:remote`、`webui:prod`、`webui:prod:remote` 都指向它。`resetpass.ts` 是独立维护入口，用于 `resetpass` 命令。`postinstall.js` 是依赖安装后的自动入口，由 `prepare`/`postinstall` 生命周期间接参与本地环境准备。

## 主流程位置

桌面应用发布主流程大致从 `scripts/build-with-builder.js` 开始：先做 Electron/Vite 构建，再调用 electron-builder 生成平台产物；打包过程中进入 `afterPack.js` 做资源和 native module 处理；macOS 产物在签名阶段进入 `afterSign.js`。如果涉及 MCP 内置服务，还会通过 `build-mcp-servers.js` 把相关 TypeScript 服务打成自包含 CJS 文件，避免外部 `node` 进程在 `app.asar.unpacked` 环境里解析依赖失败。

WebUI/CLI 发布链路分布在 `webui.ts`、`pack-web-cli.js`、`install-web.sh` 和两个 smoke test 中。根据当前片段推断，`pack-web-cli.js` 负责生成 `aionui-web-*.tar.gz` 一类产物，`install-web.sh` 负责从 release mirror 拉取并安装到本机目录，`smoke-test-web-cli.sh` 验证 tarball 内应包含 `aionui-web` 可执行文件、`package.json`、`static/`、`bundled-aioncore/`，`smoke-test-install-web.sh` 则验证安装脚本能完成下载、安装、软链和版本命令。

发布资产整理主流程在 `prepare-release-assets.sh` 和 `verify-release-assets.sh`。前者把多平台构建产物规整到 `release-assets/`，处理 desktop 分发包、Web CLI tarball、校验和、安装脚本和 updater metadata；后者检查 canonical metadata 与平台特定 metadata 是否存在，并确认 metadata 指向的文件真实存在。

PR 自动化主流程从 `pr-automation.sh` 进入，配置来自 `pr-automation.conf`。脚本会循环启动 Claude 实例，清理残留 bot labels、处理中断后的 rebase/worktree 状态，并通过环境变量控制轮询间隔、最大运行时间、PR 时间窗口、关键路径匹配等。

## 推荐阅读顺序

先读 `package.json` 的 `scripts` 字段，建立“哪些 npm/bun 命令会进入 `scripts`”的索引。然后读 `scripts/build-with-builder.js`，这是理解桌面端构建发布的主干。接着看 `afterPack.js`、`afterSign.js`、`rebuildNativeModules.js`，补齐 electron-builder hook、资源校验和 native module 处理。

如果关注 WebUI/CLI，下一步读 `webui.ts`、`pack-web-cli.js`、`install-web.sh`、`smoke-test-web-cli.sh`、`smoke-test-install-web.sh`。如果关注国际化和质量门禁，优先读 `generate-i18n-types.js`、`check-i18n.js`、`check-agents-invoke.js`。如果关注发布流水线，再读 `prepare-release-assets.sh`、`verify-release-assets.sh`、`prepare-managed-acp-tools.sh`。最后再看 `run-benchmarks.ts`、`benchmark-startup.ts`、`benchmark-acp-startup.ts` 和 `pr-automation.sh`，它们属于性能评估和维护自动化层。

## 常见误区

不要把 `scripts` 当成业务代码目录。这里的脚本大量依赖仓库结构、构建产物目录、平台名、架构名和 CI 环境变量，改动时要优先确认调用方来自 `package.json`、electron-builder 配置、CI workflow 还是人工命令。

不要只看单个脚本文件判断完整流程。例如桌面打包不是只有 `build-with-builder.js`，还会在 electron-builder 生命周期中进入 `afterPack.js` 和 `afterSign.js`；发布资产也不是构建完成就结束，还需要 `prepare-release-assets.sh` 规整和 `verify-release-assets.sh` 验证。

不要忽略脚本中的平台差异。这里同时处理 `darwin`、`win32`、`linux`，以及 `arm64`、`x64` 等架构；native rebuild、macOS notarization、Linux 预编译资源、Web CLI tarball 命名都可能有平台特化逻辑。

不要在用户界面代码变更后跳过 i18n 脚本。项目约定要求用户可见文本走 i18n，`generate-i18n-types.js` 和 `check-i18n.js` 是类型同步与完整性检查的关键路径。

不要把 `scripts/codemods` 里的内容视作日常构建入口。它更像迁移工具区，通常需要结合具体变更背景和调用说明再运行。
