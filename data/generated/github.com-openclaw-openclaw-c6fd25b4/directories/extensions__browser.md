# 目录：extensions/browser

## 它负责什么

`extensions/browser` 是 OpenClaw 内置的 Browser plugin，负责把“浏览器控制”包装成可被 agent、CLI、gateway 和 node-host 调用的统一能力。它不是普通的网页 UI 目录，而是一个插件包：通过 `openclaw.plugin.json` 声明插件 id 为 `browser`、默认启用、启动时激活，并暴露 `browser` tool、`browser` CLI alias、技能目录和 gateway 方法。

从职责上看，这个目录主要覆盖四层：

第一层是插件注册层。`index.ts` 用 `definePluginEntry` 声明插件元数据，注册 tool、CLI、gateway method、后台 service、node-host command 和 security audit collector。`plugin-registration.ts` 负责惰性注册这些能力，避免启动阶段直接加载完整浏览器运行时代码。

第二层是浏览器控制服务层。`src/server.ts` 启动本机 loopback HTTP control server，加载运行时配置，解析 browser 配置，设置 auth middleware，再把请求路由注册进去。它最终服务的不是公网 API，而是 OpenClaw 内部的浏览器控制面。

第三层是浏览器运行层。`src/browser` 下是最核心的运行逻辑，包含 Chrome/Chromium 启动、CDP/Playwright 会话、tab/profile 管理、snapshot、screenshot、act 操作、download/upload、storage、debug、权限、SSRF 防护、请求策略和 server context 生命周期。

第四层是调用入口层。agent 使用 `browser` tool；用户使用 `openclaw browser ...` CLI；gateway 使用 `browser.request` 方法；node-host 通过 `browser.proxy` 代理远端或节点上的浏览器能力。

## 直接子目录地图

`skills` 存放插件附带的 agent skill。目前主要是 `skills/browser-automation/SKILL.md`，用于指导多步骤浏览器自动化：先查状态、复用 tab、snapshot 后再 act、处理 stale refs、识别登录/权限/2FA 等人工阻塞。

`src` 是实现主体。它下面再按角色拆分。

`src/browser` 是最大、最关键的子目录，承载浏览器控制 server 的业务实现。这里包括配置解析、Chrome 可执行文件发现、CDP 连接、Playwright session、browser routes、client API、profile/tab/session 管理、snapshot/action/debug/storage/download/screenshot 等能力。

`src/browser/routes` 是 HTTP/control route 聚合区。`index.ts` 把 basic、tabs、permissions、agent 等路由组注册到 control server；`agent.ts` 再把 agent 的 snapshot、act、debug、storage 路由分发到更细文件。这里是从 HTTP 请求进入浏览器动作的主要路径。

`src/cli` 是 `openclaw browser` 命令实现。`browser-cli.ts` 定义命令组和懒加载策略，管理类命令在 `browser-cli-manage.ts`，观察类在 `browser-cli-inspect.ts`、`browser-cli-actions-observe.ts`，输入动作在 `browser-cli-actions-input` 目录。

`src/gateway` 是 gateway 适配层。`browser-request.ts` 实现 `browser.request` handler，会先判断是否要转发到 browser-capable node；否则启动本地 browser control service 并通过 route dispatcher 直接调本地路由。

`src/config` 放运行时配置读取、路径和端口默认值相关工具。浏览器实际配置解析的重心在 `src/browser/config.ts`，而 `src/config/config.ts`、`src/config/paths.ts`、`src/config/port-defaults.ts` 更偏插件运行时环境支撑。

`src/infra` 放通用基础设施，如错误、端口、临时目录、WebSocket、网络代理与 SSRF 相关工具。它服务于浏览器控制面，但不直接表达某个浏览器动作。

`src/logging` 是日志子系统封装和脱敏工具。

`src/media` 管理截图、下载、录制等媒体输出的存储服务。

`src/node-host` 负责 node-host 调用入口，核心是 `invoke-browser.ts`，配合顶层注册的 `browser.proxy` command 使用。

`src/security` 和 `src/security-audit.ts` 负责安全相关能力，包括 secret 比较、浏览器 control auth、远程 CDP/私网访问等审计发现。

`src/test-support`、`src/test-utils` 是测试辅助，不属于生产主流程入口。

## 关键入口

插件主入口是 `index.ts`。它声明 `Browser` 插件，导出 `createBrowserTool`、`handleBrowserGatewayRequest`、`runBrowserProxyCommand`、`createBrowserPluginService` 等公开能力。外部插件系统首先看这里。

运行时注册入口是 `plugin-registration.ts`。它把 `browser` tool、CLI、gateway method 和后台 service 注册到 `OpenClawPluginApi`。这里有一个重要设计：实际重型模块通过 `import("./register.runtime.js")` 或相关文件惰性加载，避免单纯发现插件时就启动或解析浏览器运行时。

自动启用/轻量 setup 入口是 `setup-api.ts`。它注册 auto-enable probe：当配置中出现 `browser` 配置、browser plugin 配置，或 agent/tool policy 引用了 `browser` tool 时，插件可被识别为需要启用。

浏览器 tool 入口是 `src/browser-tool.ts`，schema 在 `src/browser-tool.schema.ts`，动作拆到 `src/browser-tool.actions.ts`。agent 调用 `browser` tool 时，会根据 action/参数进入 status、start、tabs、snapshot、act、screenshot、download、profile 等分支，并可能选择 sandbox、host 或 node target。

control server 入口是 `src/server.ts`。`startBrowserControlServerFromConfig` 负责读取配置、校验插件启用状态、解析 auth、创建 Express app、安装 middleware、注册 browser routes，并监听 `127.0.0.1` 上的 control port。

service 入口是 `src/plugin-service.ts`。它用 `startLazyPluginServiceModule` 惰性加载 `src/server.ts`，并提供 `browser-control` 服务生命周期。环境变量可以跳过或覆盖 control module，但覆盖 specifier 有安全校验。

CLI 入口是 `src/cli/browser-cli.ts`。它注册 `openclaw browser` 下的 status/start/stop/tabs/open/snapshot/act/debug/storage 等命令组，并按当前 argv 懒加载对应命令实现。

gateway 入口是 `src/gateway/browser-request.ts`。它处理 `browser.request`，既可以调用连接的 browser-capable node，也可以本地启动 control service 后走 route dispatcher。

## 主流程位置

agent 使用浏览器的主流程大致是：插件系统加载 `index.ts`，`plugin-registration.ts` 注册 lazy browser tool；agent 调用 `browser` tool 后进入 `src/browser-tool.ts`；工具按 action 选择 client 函数或 gateway/node 代理；本地路径通常调用 `src/browser/client.ts`、`src/browser/client-actions.ts` 中的 HTTP client helper；请求最终到 `src/server.ts` 启动的 control server，再由 `src/browser/routes/index.ts` 注册的路由进入 `src/browser/routes/agent.*.ts`、`tabs.ts`、`basic.ts`、`permissions.ts`；真正浏览器操作落到 `src/browser/pw-session.ts`、`src/browser/pw-tools-core.ts`、`src/browser/cdp.ts`、`src/browser/chrome.ts`、`src/browser/server-context.ts` 等运行层。

CLI 主流程类似，但入口从 `src/cli/browser-cli.ts` 开始。CLI 子命令模块会复用 browser client/action helper，因此 CLI 和 agent tool 最终共享同一套 control server 与 route 实现。

gateway 主流程更特殊：`src/gateway/browser-request.ts` 先根据 `gateway.nodes.browser` 配置和已连接 node 判断是否代理到 node-host。如果有匹配 node，会调用 `browser.proxy`；如果没有，则启动本地 browser control service，并用 `createBrowserRouteDispatcher(createBrowserControlContext())` 直接分发到 routes。这里说明 gateway 不只是 HTTP 转发器，也能在同进程内复用 route dispatcher。

配置主流程集中在 `src/browser/config.ts`。它把 `OpenClawConfig.browser` 解析成 `ResolvedBrowserConfig` 和 `ResolvedBrowserProfile`，处理 enabled、control/CDP port、CDP host、profile、headless、attachOnly、timeouts、SSRF policy、tab cleanup、extra args 等。doctor 相关逻辑在 `src/doctor-browser.ts` 和 `src/browser/doctor.ts`，用于 readiness 检查、Chrome MCP 版本提示和历史 profile residue 处理。

## 推荐阅读顺序

1. 先看 `openclaw.plugin.json` 和 `package.json`，理解这是默认启用的 bundled plugin，以及它声明了 tool、command alias、startup activation、skills 和依赖。
2. 再看 `index.ts`、`plugin-registration.ts`，建立“插件如何把 tool/CLI/gateway/service 挂到 OpenClaw”的整体图。
3. 接着看 `src/browser-tool.schema.ts`、`src/browser-tool.ts`，理解 agent 可调用的 browser tool 参数和 action 分发。
4. 然后看 `src/server.ts`、`src/browser/routes/index.ts`、`src/browser/routes/agent.ts`，掌握 control server 到 route 的路径。
5. 再读 `src/browser/client.ts`、`src/browser/client-actions.ts`，理解 CLI/tool 与 control server 之间的 client 封装。
6. 之后进入 `src/browser/config.ts`、`src/browser/server-context.ts`、`src/browser/pw-session.ts`、`src/browser/pw-tools-core.ts`、`src/browser/cdp.ts`、`src/browser/chrome.ts`，这些是浏览器生命周期和真实动作执行的核心。
7. 最后看 `src/cli/browser-cli.ts`、`src/gateway/browser-request.ts`、`src/node-host/invoke-browser.ts`、`skills/browser-automation/SKILL.md`，补齐 CLI、gateway、node-host 和 agent 操作规范。

## 常见误区

不要把 `extensions/browser` 当作核心 `src/channels` 或 gateway 内建功能。根据 `extensions/AGENTS.md`，这里是 bundled plugin 边界，生产代码应通过 `openclaw/plugin-sdk/*` 和本插件自己的 barrel/API 交互，而不是随意深导入核心内部。

不要以为 `browser` tool 直接操作 Playwright。tool 层主要做参数读取、target 选择、结果包装和代理决策；真实浏览器动作大多经过 client、control server routes、server context，再进入 Playwright/CDP 层。

不要把 `profile="user"` 当作默认路径。默认浏览器 profile 是 OpenClaw 管理的隔离 profile；`user` 或 existing-session profile 是为了复用用户已登录的 Chromium 会话，且某些 action 不接受 per-call `timeoutMs` 覆盖。

不要把 `browser.request` 理解成本地专用。它可能按 gateway node 策略转发到 browser-capable node，并通过 `browser.proxy` 返回结果和文件路径映射；只有没有合适 node 时才走本地 control service。

不要跳过 auth 和 SSRF 逻辑。`src/server.ts` 会安装 browser control auth middleware，`src/security-audit.ts` 会检查无 auth、远程 CDP HTTP、私网 CDP 等风险；浏览器控制能力能读写页面、文件上传下载和会话状态，所以安全边界是主流程的一部分。

不要逐个叶子文件学习。这个目录测试文件很多，运行文件也细分很深；overview 阶段应先抓住 `index.ts`、`plugin-registration.ts`、`src/browser-tool.ts`、`src/server.ts`、`src/browser/routes`、`src/browser/config.ts`、`src/gateway/browser-request.ts` 这几条主线，再按具体问题深入。
