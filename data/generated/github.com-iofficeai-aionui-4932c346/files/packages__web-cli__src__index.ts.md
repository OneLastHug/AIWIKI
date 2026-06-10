# 文件：packages/web-cli/src/index.ts

## 一句话定位

`packages/web-cli/src/index.ts` 是 `@aionui/web-cli` 的命令行主入口，负责把打包后的 `aionui-web` 可执行文件、静态前端资源、内置或外部后端二进制、用户数据目录和端口配置串起来，最终启动一个不依赖 Electron 的 standalone WebUI 运行时。

## 它暴露/定义了什么

这个文件没有显式 `export` 公共 API，而是作为可执行入口在模块加载时直接执行 `main()`。它定义了几类能力：

一是命令分发能力：`main()` 解析 `process.argv`，支持 `start`、`resetpass`、`version`、`help`，其中 `start` 是默认命令。

二是运行路径解析能力：`resolveCliRoot()` 判断当前是 bun compile 后的 `aionui-web` 单文件二进制，还是源码开发模式。打包模式下用 `process.execPath` 找到 tarball 内的兄弟目录；开发模式下回退到 `import.meta.url` 所在目录。这一点很关键，因为 bun compile 场景里 `import.meta.url` 会指向虚拟路径，不能用来定位真实资源。

三是运行参数解析能力：`parseArgs()`、`resolveBackendBinary()`、`resolveStaticDir()`、`resolveDataDir()`、`resolveLogDir()`、`resolvePort()`、`resolveAllowRemote()` 分别把 CLI flag、环境变量和默认值统一成启动所需配置。

四是两个核心执行流程：`runStart()` 用于启动 WebUI；`runResetPassword()` 用于临时拉起后端并调用重置密码接口。

## 谁调用它

直接调用入口是 `packages/web-cli/bin/aionui-web.js`，该文件通过动态 import 加载 `../src/index.js`，所以用户执行 `aionui-web` 时最终会进入这里。`packages/web-cli/package.json` 的 `bin` 字段把命令名 `aionui-web` 指向这个 bin 文件，同时 `exports` 暴露了源码入口。

发布链路中，`scripts/pack-web-cli.js` 会把 `packages/web-cli/src/index.ts` 作为 bun compile 的入口，生成 tarball 内的 standalone 可执行文件。安装脚本和 smoke test 也围绕这个产物工作，例如 `scripts/install-web.sh` 安装后提示用户运行 `aionui-web start`，`scripts/smoke-test-web-cli.sh` 会验证 `aionui-web version` 和 `aionui-web start` 的基本行为。

根据当前片段推断，普通终端用户、安装脚本产物、发布验证脚本是它的主要调用方；依据是 `rg` 结果里围绕 `aionui-web` 命令的 pack、install、smoke-test 脚本都指向这个 CLI。

## 它调用谁

最重要的下游是 `@aionui/web-host`。正常后端可用时，`runStart()` 调用 `startWebHost()`，由 `web-host` 继续编排 `startBackend()` 和 `startStaticServer()`：先启动后端，再启动静态服务器和 API 代理，最后返回包含 `localUrl`、`networkUrl`、`backendPort`、`stop()` 的 handle。后端二进制缺失时，`runStart()` 不直接失败，而是调用 `startStaticServer()` 进入 frontend-only 模式，让 SPA 仍可加载，只是 API 调用会失败。

它还调用 `./ensureAdminPassword.js` 的 `ensureAdminPassword()`。首次完整启动后，该函数轮询后端认证状态；如果需要初始化管理员密码，就请求 `/api/webui/reset-password` 并打印初始密码；如果已有密码，则打印登录用户名和重置提示。

浏览器自动打开由 `./browser.js` 提供：`shouldAutoOpenBrowser()` 决定是否打开，`openBrowserUrl()` 根据平台执行 `open`、`cmd /c start` 或 `xdg-open`。

系统层面还使用 `fs` 创建数据和日志目录、检查静态资源和后端二进制是否存在；使用 `os.homedir()` 得到默认 `~/.aionui-web`；使用 `path` 处理跨平台路径；使用 `fetch` 访问本机后端接口；使用 `node:timers/promises` 的 `delay()` 做后端 readiness 轮询。

## 核心流程

启动时，模块底部执行 `main().catch(...)`。如果任何未捕获错误冒泡，日志会输出 fatal 信息，并尽量调用 `currentHandle.stop()` 清理当前 WebHost 或静态服务器，然后以非零状态退出。

`main()` 首先调用 `parseArgs(process.argv.slice(2))`。没有命令时默认为 `start`。如果命令是 `version`、`--version` 或 `-v`，它读取 `cliRoot/package.json` 并打印版本；如果是 `help`、`--help` 或 `-h`，它打印命令和参数说明；如果是 `resetpass`，进入密码重置流程；否则只接受 `start`，未知命令会报错并退出。

`runStart()` 是主启动流程。它解析后端二进制路径、静态资源目录、数据目录、日志目录、端口、远程访问开关和版本号，然后决定是否自动打开浏览器。启动前它会强校验 `staticDir`，因为没有 SPA 静态资源时 WebUI 无法成立。随后打印关键运行信息。

如果 `backendBin` 不存在，它进入降级模式：调用 `startStaticServer({ backendPort: 0 })` 启动静态站点，API 代理会因为无效后端端口而干净失败。这种设计对发布包或本地调试更友好，至少能验证前端 shell 和静态资源。

如果 `backendBin` 存在，它调用 `startWebHost()`，传入 `app` 元数据、目录配置和 `ownBackend` resolver。启动成功后打印本地和网络访问地址，再调用 `ensureAdminPassword()` 完成首启管理员密码引导，最后按策略打开浏览器。

无论前端-only 还是完整模式，`runStart()` 都会注册 `SIGINT` 和 `SIGTERM`，收到信号后只执行一次 shutdown，调用当前 handle 的 `stop()` 并退出。

`runResetPassword()` 是短生命周期流程。它要求后端二进制必须存在，解析同一套 `dataDir` 和 `logDir`，然后用 `startWebHost()` 在随机端口启动一个临时 WebHost。它轮询 `/api/auth/status` 最多 15 秒，后端 ready 后 POST `/api/webui/reset-password`，解析响应里的 `new_password` 和 `username`，打印新密码，最后在 `finally` 中停止 WebHost。

## 关键函数的高层作用

`resolveCliRoot()` 决定资源根目录，是打包模式和源码模式能共用一套逻辑的基础。它直接影响 `package.json`、`static/`、`bundled-aioncore/<plat-arch>/aioncore` 的定位。

`parseArgs()` 是轻量参数解析器，只支持 `--key value` 和 `--flag` 形式，不处理短参数组合、等号参数或复杂命令结构。

`resolveBackendBinary()` 按优先级选择后端路径：`--backend-bin` 高于 `AIONUI_BACKEND_BIN`，再回退到 tarball 内按 `process.platform-process.arch` 分目录存放的 bundled 后端。

`resolveDataDir()` 和 `resolveLogDir()` 决定持久化边界。默认数据目录是 `~/.aionui-web`，日志默认在 `<data-dir>/logs`。`resetpass` 复用同一解析逻辑，因此重置的是正常启动时同一个 SQLite 数据库。

`runStart()` 是服务启动总控，负责把配置解析、资源检查、后端存在性判断、WebHost 启动、首启密码处理、浏览器打开、信号清理串成一个完整用户流程。

`runResetPassword()` 是运维型命令入口，核心不是服务常驻，而是临时启动后端、等待 ready、调用重置密码接口、清理进程。

`readPackageVersion()` 是容错版本读取，失败时返回 `0.0.0`。辅助解析函数和浏览器打开逻辑都偏薄，主要服务于核心流程。

## 修改风险

最大风险是资源路径解析。`resolveCliRoot()` 的打包模式依赖可执行文件名必须是 `aionui-web` 或 `aionui-web.exe`；如果发布产物改名、tarball 布局调整、bun compile 行为变化，静态资源、版本文件和 bundled 后端都会找错位置。

第二类风险是数据目录兼容性。`runStart()` 和 `runResetPassword()` 必须保持相同的 `dataDir` 解析规则，否则用户执行 `aionui-web resetpass` 可能重置到另一个数据库，表现为密码重置成功但登录仍失败。

第三类风险是端口和远程访问语义。`--remote`、`AIONUI_ALLOW_REMOTE`、`AIONUI_REMOTE` 会影响绑定地址，也影响默认是否自动打开浏览器。改动这里可能造成远程部署不可访问，或服务器环境意外尝试打开本机浏览器。

第四类风险是 frontend-only 降级。当前后端缺失时仍启动静态站点，这是有意设计；如果改成直接退出，会影响 smoke test、安装验证和用户排障体验。反过来，如果静态目录缺失仍继续启动，则 WebUI 根页面无法正常返回。

第五类风险是密码输出格式。`ensureAdminPassword.ts` 注释表明 smoke test 会 grep 初始密码日志，`runResetPassword()` 的输出也可能被脚本或用户流程依赖。调整日志文案、字段名解析或接口路径时，要同步检查 `scripts/smoke-test-web-cli.sh`、`scripts/resetpass.ts` 以及后端 `/api/auth/status`、`/api/webui/reset-password` 的响应结构。

第六类风险是进程清理。`currentHandle` 同时可能指向完整 WebHost 或静态服务器，`SIGINT`、`SIGTERM` 和 fatal catch 都依赖 `stop()` 正确释放后端和 HTTP server。若新增异步分支或提前 `process.exit()`，要确认不会留下后台后端进程或占用端口。
