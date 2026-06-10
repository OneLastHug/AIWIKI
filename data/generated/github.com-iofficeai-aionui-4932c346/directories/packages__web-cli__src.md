# 目录：packages/web-cli/src

## 它负责什么

`packages/web-cli/src` 是 `@aionui/web-cli` 的 CLI 编排层，负责把 WebUI 的启动过程串起来，而不是承载具体业务页面或后端实现。根据当前片段推断，这个目录的职责主要有三件事：解析启动参数与环境变量，定位运行时资源；启动 `@aionui/web-host` 提供的 Web 宿主或静态站点；在首次启动时处理浏览器自动打开、初始管理员密码提示等用户体验细节。

它更像“启动控制台”，而不是“功能实现目录”。真正的后端能力来自 `@aionui/web-host`，静态资源来自 `static/`，CLI 这里只负责把这些部件装配起来。

## 直接子目录地图

根据当前片段推断，`src` 下面没有子目录，只有 3 个直接文件：

- `src/index.ts`：主入口，负责命令解析、路径解析、启动流程和分支控制。
- `src/browser.ts`：浏览器自动打开相关工具函数，封装平台差异。
- `src/ensureAdminPassword.ts`：首次启动时的管理员密码初始化与提示逻辑。

这意味着 `src` 的结构非常扁平，所有核心控制逻辑都集中在这三个文件里，没有再向下拆分到更细的模块树。

## 关键入口

最关键的入口是 `src/index.ts`。`packages/web-cli/package.json` 里 `exports` 把包入口指向了 `./src/index.ts`，同时 `bin/aionui-web.js` 也代表这个包对外的命令行入口。换句话说，用户运行 `aionui-web` 时，最终会落到这里的启动编排。

`index.ts` 里最重要的几个节点是：

- `resolveCliRoot()`：区分打包后的单文件二进制和开发态运行，决定资源根目录怎么找。
- `parseArgs()`：解析 `start`、`--port`、`--static-dir`、`--backend-bin`、`--open` 等参数。
- `resolveBackendBinary()`、`resolveStaticDir()`、`resolveDataDir()`、`resolveLogDir()`：处理路径与环境变量覆盖。
- `runStart()`：真正执行启动，决定走“带后端”还是“仅前端静态服务”。
- `ensureAdminPassword()`：在后端可用时，继续完成首登账号密码的引导。

## 主流程位置

主流程基本都在 `src/index.ts` 的 `runStart()` 中。

整体顺序可以概括为：

1. 解析命令与标志位，默认命令是 `start`。
2. 推导后端二进制、静态目录、数据目录、日志目录和端口。
3. 检查静态目录是否存在，不存在就直接退出。
4. 判断后端二进制是否存在。
5. 如果后端缺失，降级到 `startStaticServer()`，只提供前端壳。
6. 如果后端存在，调用 `startWebHost()` 启动完整 Web 宿主。
7. 根据 `shouldAutoOpenBrowser()` 决定是否自动打开浏览器。
8. 后端启动后，再走 `ensureAdminPassword()`，完成首次管理员密码的探测、重置与提示。

其中 `browser.ts` 只负责“要不要打开”和“怎么打开”，`ensureAdminPassword.ts` 只负责“后端状态确认、重置密码、打印提示”。主流程在 `index.ts`，辅流程在另外两个文件。

## 推荐阅读顺序

1. 先看 `package.json`，确认这个包的入口、bin 命令和依赖边界。
2. 再看 `src/index.ts`，把 CLI 的启动路径、参数、分支逻辑串起来。
3. 然后看 `src/browser.ts`，理解自动打开浏览器的策略和平台差异。
4. 最后看 `src/ensureAdminPassword.ts`，理解首次安装时的账号引导是怎么补上的。

这个顺序能最快建立“命令如何进入、资源如何定位、服务如何启动、首次登录如何兜底”的完整心智模型。

## 常见误区

一个常见误区是把 `packages/web-cli/src` 当成 WebUI 前端页面源码。实际上它不是 UI 组件目录，而是 CLI 启动层，真正的页面资产在 `static/`，真正的服务能力在 `@aionui/web-host`。

第二个误区是把“自动打开浏览器”理解成启动主逻辑的一部分。实际上它只是附属体验，由 `src/browser.ts` 单独封装，主流程即使不开浏览器也能完成启动。

第三个误区是以为 `ensureAdminPassword.ts` 是账号体系核心。它不是认证系统本身，而是首次启动时的引导辅助：探测 `needs_setup`，必要时调用重置接口，打印初始密码和登录提示。

第四个误区是忽略打包态与开发态的差异。`resolveCliRoot()` 明确区分了单文件二进制和源码运行环境，所以这里很多路径逻辑不是“写死”的，而是围绕运行形态动态推导的。
