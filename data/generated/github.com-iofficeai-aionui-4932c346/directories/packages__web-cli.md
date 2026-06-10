# 目录：packages/web-cli

## 它负责什么

`packages/web-cli` 是 AionUi 的独立 WebUI 命令行运行时包，包名为 `@aionui/web-cli`。它的定位不是 Electron 桌面端，也不是前端 SPA 本身，而是把已经构建好的 Web 静态资源、后端 `aioncore` 二进制、运行时数据目录和本地 HTTP 服务串起来，形成一个可通过命令启动的 Web 版 AionUi。

从 `package.json` 看，它暴露的命令是 `aionui-web`，描述为 `standalone web runtime (no Electron)`。也就是说，这个包主要解决“没有 Electron 外壳时，如何启动 WebUI”的问题：解析 CLI 参数，定位静态资源目录，定位或接收后端二进制路径，准备数据目录和日志目录，启动 `@aionui/web-host` 提供的 Web host，并在首次启动时尝试初始化管理员密码。

它依赖的核心包是 `@aionui/web-host`。`web-cli` 更像一个启动器和运行时适配层，真正的静态服务、后端托管、代理等 Web host 能力由 `@aionui/web-host` 承担。

## 直接子目录地图

`packages/web-cli` 的直接结构很小，只有两个子目录和少量配置文件：

`bin/` 是命令行可执行入口目录。当前关键文件是 `bin/aionui-web.js`，它是 `package.json` 中 `bin.aionui-web` 指向的脚本，负责把用户执行的 `aionui-web` 命令接到源码主入口。

`src/` 是 CLI 的主要 TypeScript 实现目录。这里承载参数解析、运行路径解析、浏览器自动打开逻辑、管理员密码初始化逻辑，以及 `start`、`resetpass`、`version`、`help` 等命令分发。

根目录下的 `package.json` 定义包名、版本、命令入口、导出入口、脚本和依赖；`tsconfig.json` 是该包自己的 TypeScript 配置。当前片段未看到 README 正文，因此目录语义主要依据 `package.json`、`src/index.ts` 和源码注释推断。

## 关键入口

第一层入口是 `packages/web-cli/package.json`。其中 `bin` 字段把命令 `aionui-web` 映射到 `./bin/aionui-web.js`；`exports` 字段把包入口映射到 `./src/index.ts`；`scripts.build` 使用 `tsc`，说明这个包自身以 TypeScript 编译为主。

第二层入口是 `packages/web-cli/bin/aionui-web.js`。这是用户实际调用 CLI 时最先进入的脚本。它的职责很薄，主要是加载主实现，并在启动失败时输出 `Failed to start aionui-web` 一类错误。

核心入口是 `packages/web-cli/src/index.ts`。这个文件承担了大多数主流程：解析参数、解析路径、读取版本、启动服务、处理命令分支、注册退出行为，并调用 `main()`。从当前片段看，它没有使用 `commander` 之类命令行框架，而是通过 `parseArgs(argv)` 自己解析形如 `--port 25808`、`--static-dir <path>` 的参数。

辅助入口包括 `packages/web-cli/src/browser.ts` 和 `packages/web-cli/src/ensureAdminPassword.ts`。前者处理是否自动打开浏览器以及不同平台的打开命令；后者处理首次启动或重置场景下的管理员密码探测与初始化。

## 主流程位置

启动主流程集中在 `packages/web-cli/src/index.ts` 的 `main()` 和 `runStart()`。

`main()` 先通过 `parseArgs()` 得到命令和 flags。默认命令是 `start`，因此直接执行 `aionui-web` 等价于启动 WebUI。它还处理 `version`、`help`、`resetpass` 等命令；如果遇到未知命令，会提示可用命令形式。根据当前片段，`start`、`resetpass`、`version`、`help` 是这个 CLI 的主要用户界面。

`runStart()` 是启动 WebUI 的中心。它会依次解析后端二进制路径、静态资源目录、数据目录、日志目录、端口、是否允许远程访问、版本号和是否自动打开浏览器。默认端口是 `25808`；默认数据目录是用户 home 下的 `.aionui-web`；默认静态资源目录根据 CLI 根目录下的 `static` 推断；默认后端二进制位于 `bundled-aioncore/<platform>-<arch>/aioncore`，Windows 下是 `aioncore.exe`。这些默认值也可以通过参数或环境变量覆盖，例如 `--backend-bin`、`--static-dir`、`--data-dir`、`--log-dir`、`--port`，以及 `AIONUI_BACKEND_BIN`、`AIONUI_DATA_DIR`、`AIONUI_LOG_DIR`、`AIONUI_PORT`、`PORT` 等。

服务启动有两个分支。如果后端二进制存在，`runStart()` 调用 `startWebHost()`，传入应用版本、打包状态、资源路径、用户数据路径、静态目录、端口、日志目录、工作目录，以及 `ownBackend` 类型的后端解析函数。启动成功后会打印本地访问地址，必要时自动打开浏览器，并调用 `ensureAdminPassword()` 尝试完成首次管理员密码初始化。

如果后端二进制不存在，流程会降级为 frontend-only 模式，调用 `startStaticServer()` 只托管前端静态资源。源码注释说明此时 API 调用会失败，前端应向用户展示后端缺失状态。这个设计让 SPA 壳仍可加载，便于诊断或手动指定后端。

密码相关主流程在 `packages/web-cli/src/ensureAdminPassword.ts` 和 `runResetPassword()`。`ensureAdminPassword()` 会等待后端状态可用，读取管理员用户名，在新安装场景下调用后端重置密码接口并打印明文凭据；失败时不阻断整体启动。`resetpass` 命令则使用和 `start` 相同的数据目录解析逻辑，启动一个用于重置密码的 host，再执行密码重置流程。根据当前片段推断，这样可以保证用户针对同一个数据目录重置对应实例的管理员密码。

## 推荐阅读顺序

建议先读 `packages/web-cli/package.json`，确认这个包的身份、命令名、入口和依赖边界。重点看 `bin`、`exports`、`dependencies`，理解它为什么依赖 `@aionui/web-host`。

第二步读 `packages/web-cli/bin/aionui-web.js`，只需确认它如何跳转到 `src/index.ts`，不必停留太久。

第三步读 `packages/web-cli/src/index.ts`。阅读时可以按函数分组：先看 `resolveCliRoot()` 理解打包运行和源码运行的路径差异；再看 `parseArgs()` 和各个 `resolve*()` 函数理解配置来源；然后看 `runStart()` 理解正常启动和 frontend-only 降级；最后看 `runResetPassword()` 与 `main()` 理解命令分发。

第四步读 `packages/web-cli/src/browser.ts`。这里适合补齐“什么时候自动打开浏览器、不同系统如何打开”的细节。

第五步读 `packages/web-cli/src/ensureAdminPassword.ts`。它涉及后端状态探测、管理员用户名读取和重置密码，是启动后初始化体验的关键补充。

最后再跳到邻近包 `packages/web-host`。`web-cli` 只是调用 `startWebHost()` 和 `startStaticServer()`，如果要继续追踪 HTTP 服务、静态资源托管、API 代理、后端进程管理，真正的实现边界应进入 `@aionui/web-host`。

## 常见误区

不要把 `packages/web-cli` 理解成 Web 前端应用源码。它不负责 React 页面、路由或界面组件，前端静态产物通过 `staticDir` 被托管，真正的 SPA 源码在仓库其他位置。

不要把它理解成 Electron 主进程。`package.json` 明确描述为 no Electron 的独立 Web runtime；它使用 Node/Bun 运行时能力启动服务，而不是打开 Electron 窗口。

不要以为后端一定随 CLI 可用。`runStart()` 明确检查后端二进制是否存在，不存在时会进入 frontend-only 模式。这个模式能加载前端，但 API 会失败，所以看到页面不代表完整系统已经可用。

不要忽略打包路径差异。`resolveCliRoot()` 的注释指出，Bun compile 后 `import.meta.url` 可能指向虚拟路径，因此打包态必须依赖 `process.execPath` 寻找同级的 `package.json`、`bundled-aioncore/` 和 `static/`。如果改启动路径解析，很容易破坏发布包运行。

不要把 `resetpass` 当成纯本地文件修改。根据当前片段，它会启动 `startWebHost()`，通过后端接口完成密码重置；因此数据目录、后端二进制和端口解析仍然重要。

不要在阅读时只看 `bin/`。`bin/aionui-web.js` 只是薄包装，真正的主流程、配置优先级、降级策略、退出行为都在 `src/index.ts`。
