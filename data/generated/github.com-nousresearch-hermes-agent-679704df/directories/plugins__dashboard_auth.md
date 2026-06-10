# 目录：plugins/dashboard_auth

## 它负责什么

`plugins/dashboard_auth` 是 Hermes dashboard 的认证提供者插件目录。它不直接实现 dashboard 的中间件、路由、cookie 或前端登录页，而是提供可被主程序注册的 `DashboardAuthProvider` 实现，让 dashboard 在非 loopback 绑定、需要 OAuth 鉴权门控时，有一个实际的身份提供方可用。

当前目录下只有一个内置提供者：`plugins/dashboard_auth/nous`。它实现的是面向 Nous Portal 的 OAuth 2.0 authorization-code + PKCE 流程。根据当前片段推断，这个插件的定位是“默认随仓库分发，但按配置激活”：插件可以被自动发现和加载，但只有在存在有效 `client_id` 时才会向 dashboard auth registry 注册 provider。这样本地 loopback 使用、或显式 `--insecure` 场景不会被强制卷入 OAuth 流程。

它处理的核心职责包括：生成 OAuth 授权跳转 URL、生成和保存 PKCE `code_verifier` / `state` 需要的 cookie payload、用授权码向 token endpoint 交换 token、校验 RS256 JWT、读取 JWKS 并缓存、把认证结果转换成 `hermes_cli.dashboard_auth.Session`。刷新 token 在当前契约里并不支持，`refresh_session` 会走过期错误路径，由宿主 dashboard 中间件把用户重新导向登录。

## 直接子目录地图

`plugins/dashboard_auth` 目前只有一个直接子目录：

`plugins/dashboard_auth/nous`：Nous Research 的 dashboard OAuth provider 插件。这里包含插件清单 `plugin.yaml` 和 Python 入口 `__init__.py`。没有更深层的业务子目录，也没有把 provider 拆成多个模块；主要逻辑集中在一个文件中。

这个目录不是 dashboard auth 框架本体。框架本体在 `hermes_cli/dashboard_auth`，例如 provider 抽象、registry、middleware、routes、cookies、audit、login_page、public_paths、ws_tickets 等都在那里。`plugins/dashboard_auth/nous` 只是框架的一种 provider 实现。

## 关键入口

`plugins/dashboard_auth/nous/plugin.yaml` 是插件元数据入口。它声明插件名 `nous`、版本、作者、`kind: backend`，并通过描述说明它是 dashboard auth provider，会在配置了 `dashboard.oauth.client_id` 或 `HERMES_DASHBOARD_OAUTH_CLIENT_ID` 时激活。`requires_env` 中列出 `HERMES_DASHBOARD_OAUTH_CLIENT_ID`，但从实现注释看，配置文件方式同样是正式入口。

`plugins/dashboard_auth/nous/__init__.py` 是运行时入口。关键类是 `NousDashboardAuthProvider`，继承自 `hermes_cli.dashboard_auth.DashboardAuthProvider`。关键方法包括 `start_login`、`complete_login`、`refresh_session`，以及用于 token/JWT 校验的内部逻辑。模块底部的 `register(ctx)` 是插件系统调用的注册函数，它读取配置和环境变量，检查 `client_id` 形态，然后通过 `ctx.register_dashboard_auth_provider(provider)` 注册到宿主。

`LAST_SKIP_REASON` 是这个插件比较重要的辅助出口。插件未注册时，不只是静默跳过，而是记录“为什么跳过”，例如缺少或格式错误的 `client_id`。`hermes_cli/web_server.py` 的 fail-closed 分支会读取这个原因，用于给 operator 更明确的启动失败提示。

## 主流程位置

主流程可以分成“插件注册”和“请求鉴权”两条线。

插件注册线：启动 dashboard 时，`hermes_cli/main.py` 会先发现并加载插件，确保类似 `plugins/dashboard_auth/nous` 的 provider 有机会在 `start_server` 前注册。插件系统的上下文能力在 `hermes_cli/plugins.py`，其中 `PluginContext.register_dashboard_auth_provider` 会检查对象是否继承 `DashboardAuthProvider`，然后调用 `hermes_cli.dashboard_auth.registry.register_provider`。`plugins/dashboard_auth/nous/__init__.py` 的 `register(ctx)` 负责决定是否真的注册：环境变量优先于 `config.yaml`，空环境变量按未设置处理，`client_id` 需要是 `agent:{instance_id}` 形态，portal 地址没有配置时使用默认生产地址；文档中如果必须提到该外部地址，应写作 `[URL已移除]`。

请求鉴权线：dashboard 的 ASGI 应用在 `hermes_cli/web_server.py` 中挂载 auth routes，并在需要时进入 `_dashboard_auth_gate`，实际逻辑转到 `hermes_cli.dashboard_auth.middleware.gated_auth_middleware`。未登录访问会通过 `hermes_cli.dashboard_auth.routes` 进入 `/login`、`/auth/*`、`/api/auth/*` 等 OAuth 回合。登录开始时路由选择 provider，调用 `NousDashboardAuthProvider.start_login` 生成跳转地址和 PKCE cookie payload；回调时路由校验 `state`，再调用 `complete_login` 用 `code` 换 token，并由 provider 校验 JWT 和 claims，最终写入 session cookie。后续请求由 middleware 读取 cookie，调用 provider 验证 session；WebSocket 场景还有 `hermes_cli.dashboard_auth.ws_tickets` 参与单次 ticket 流程。

## 推荐阅读顺序

1. 先读 `plugins/dashboard_auth/nous/plugin.yaml`，确认这是一个 backend 插件，而不是普通 dashboard UI 插件或工具插件。
2. 再读 `hermes_cli/dashboard_auth/base.py`，理解 `DashboardAuthProvider`、`LoginStart`、`Session`、`ProviderError`、`InvalidCodeError`、`RefreshExpiredError` 这些契约对象。
3. 回到 `plugins/dashboard_auth/nous/__init__.py`，按 `register(ctx)`、`NousDashboardAuthProvider.__init__`、`start_login`、`complete_login`、token/JWKS 校验、`refresh_session` 的顺序读。
4. 然后读 `hermes_cli/plugins.py` 中 `register_dashboard_auth_provider`，看 provider 如何进入 registry。
5. 最后读 `hermes_cli/dashboard_auth/routes.py`、`hermes_cli/dashboard_auth/middleware.py`、`hermes_cli/web_server.py`，把 provider 的方法调用和 dashboard HTTP 生命周期对上。
6. 如果要验证行为，测试入口主要看 `tests/plugins/dashboard_auth/test_nous_provider.py`，再扩展到 `tests/hermes_cli/test_dashboard_auth_*` 系列。

## 常见误区

不要把 `plugins/dashboard_auth` 当成完整认证系统。完整系统在 `hermes_cli/dashboard_auth`，这里只是 provider 插件目录；cookie 名、路由路径、登录页、middleware 放行规则、audit log 都不归这个目录所有。

不要以为插件被发现就一定启用。`nous` 插件会自动加载，但只有配置了有效 `client_id` 才注册 provider。缺配置时它会设置 `LAST_SKIP_REASON` 并跳过，dashboard 在需要 auth gate 但没有 provider 时会拒绝启动，而不是退回到“允许所有人”。

不要把 `requires_env` 理解成唯一配置方式。实现注释明确说明 `dashboard.oauth.client_id` 是 canonical surface，环境变量是 operator override，并且环境变量优先。

不要期待 refresh token 流程已经可用。当前契约下 V1 没有 refresh token，`refresh_session` 的语义是让中间件重定向登录；`complete_login` 对 refresh token 的兼容保存只是面向未来。

不要在文档或日志学习时暴露真实外部服务地址。源码里有默认 portal 地址和 well-known/token/authorize 路径，但学习文档中如需提及外部地址，应写作 `[URL已移除]`。
