# 目录：hermes_cli/dashboard_auth

## 它负责什么

`hermes_cli/dashboard_auth` 是 Hermes Dashboard 的“公开部署认证门禁”子系统。它不处理普通 CLI 的模型登录，也不保存模型供应商 API key；它专门服务于 Web Dashboard 在非 loopback 绑定、且需要对外访问时的浏览器登录、OAuth 回调、会话 cookie 校验、登出、审计日志和 WebSocket 升级认证。

从代码注释和调用关系看，这套机制只在 `app.state.auth_required is True` 时启用。也就是说，Dashboard 如果运行在本机 loopback 或 `--insecure` 这类不要求 OAuth 门禁的模式下，仍由 `hermes_cli/web_server.py` 里的旧 `_SESSION_TOKEN` 风格 `auth_middleware` 处理。公开部署时则走这里的 `gated_auth_middleware`，要求请求携带由某个已注册 `DashboardAuthProvider` 验证通过的会话 cookie。

这个目录还定义了 provider 插件协议。默认 provider 根据注释位于 `plugins/dashboard-auth-nous/`，第三方 provider 通过插件上下文 `ctx.register_dashboard_auth_provider` 注册进来。因此这里更像认证框架和网关层，而不是某个具体 OAuth 服务的实现。

## 直接子目录地图

该目标目录下没有直接子目录，只有一组同级 Python 模块。按角色可分成几类：

`base.py`、`registry.py`、`__init__.py` 组成 provider 框架层，定义 `DashboardAuthProvider`、`Session`、`LoginStart`、异常类型以及 provider 注册表。

`routes.py`、`middleware.py` 是 HTTP 主入口层，分别负责 OAuth 相关路由和请求门禁。

`cookies.py`、`ws_tickets.py` 是浏览器状态和 WebSocket 辅助认证层，处理 session cookie、PKCE cookie、一次性 WS ticket。

`prefix.py`、`public_paths.py` 是部署形态适配层，处理反向代理路径前缀、公开 URL 推断、公开 API allowlist。

`audit.py`、`login_page.py` 是支撑层，分别负责认证审计日志和无需 SPA bundle 的服务端登录页 HTML。

## 关键入口

最核心的抽象入口是 `hermes_cli/dashboard_auth/base.py` 里的 `DashboardAuthProvider`。它规定 provider 必须实现 `start_login`、`complete_login`、`verify_session`、`refresh_session`、`revoke_session`，并返回或消费 `Session`、`LoginStart`。虽然接口里仍保留 `refresh_session`，但 `cookies.py` 的注释显示当前 OAuth contract v1 下刷新 token 逻辑已经弱化，空 `refresh_token` 不会被写入 cookie，过期会话通常转为重新登录。

provider 的注册入口在 `hermes_cli/dashboard_auth/registry.py`，主要函数是 `register_provider`、`get_provider`、`list_providers`。`hermes_cli/plugins.py` 中的 `register_dashboard_auth_provider` 会校验对象是否继承 `DashboardAuthProvider`，再调用这里的注册表。

Web 路由入口是 `hermes_cli/dashboard_auth/routes.py` 中的 `router = APIRouter()`。它提供 `/login`、`/api/auth/providers`、`/auth/login`、`/auth/callback`、`/auth/logout`、`/api/auth/me`、`/api/auth/ws-ticket`。这些路由本身不主动 gate；真正的拦截逻辑放在 `middleware.py`。

门禁入口是 `hermes_cli/dashboard_auth/middleware.py` 的 `gated_auth_middleware(request, call_next)`。`hermes_cli/web_server.py` 通过 `_dashboard_auth_gate` 引入它，并根据 Dashboard 启动时判定的 `auth_required` 决定是否生效。

## 主流程位置

登录主流程从未认证用户访问受保护页面开始。`gated_auth_middleware` 先检查路径是否在公开 allowlist 中；如果不是公开路径，就读取 `cookies.py` 中定义的 session cookie。没有 cookie 时，HTML 请求会被 302 到 `/login`，API 请求会收到 401 JSON，响应体带 `login_url`，供前端做整页跳转。

`/login` 由 `login_page.py` 渲染服务端 HTML，不依赖 React SPA。页面通过 `list_providers()` 展示可用 provider，用户点击后进入 `/auth/login?provider=N`。`routes.py` 的 `auth_login` 调用 provider 的 `start_login`，拿到外部身份提供方的跳转地址和 PKCE/CSRF 状态，并通过 `set_pkce_cookie` 写入短期 HttpOnly cookie。

外部 OAuth 完成后回到 `/auth/callback`。`auth_callback` 读取 PKCE cookie，校验 provider、state 和 code，再调用 provider 的 `complete_login` 换取 `Session`。成功后用 `set_session_cookies` 写入 access token cookie，清理 PKCE cookie，并跳回登录前的安全相对路径。

后续请求再次经过 `gated_auth_middleware`，它会遍历 `list_providers()`，调用每个 provider 的 `verify_session(access_token=...)`。第一个识别并返回 `Session` 的 provider 获胜，结果挂到 `request.state.session`。`/api/auth/me` 正是读取这个 `request.state.session` 给 SPA 返回当前用户身份。

WebSocket 相关流程在 `routes.py` 的 `/api/auth/ws-ticket` 和 `ws_tickets.py`。由于浏览器 WebSocket upgrade 不能可靠设置 `Authorization` header，已登录 SPA 会先 POST 获取 30 秒 TTL、单次使用的 ticket，再把它作为查询参数交给 WS endpoint 消费。根据当前片段推断，实际消费点在 `hermes_cli/web_server.py` 的 WebSocket handler 附近，依据是 `ws_tickets.py` 注释提到 `/api/pty`、`/api/ws`、`/api/pub`、`/api/events` 使用 `?ticket=`。

## 推荐阅读顺序

建议先读 `base.py`，理解 provider 协议、`Session` 数据结构和异常语义。接着读 `registry.py` 和 `__init__.py`，确认插件如何把 provider 暴露给认证门禁。

第二步读 `middleware.py`，因为它解释了整个目录为什么存在：哪些路径公开、哪些路径需要 cookie、HTML 与 API 未认证响应有什么差别，以及 `request.state.session` 是在哪里设置的。

第三步读 `routes.py`，按 `/login`、`/auth/login`、`/auth/callback`、`/auth/logout`、`/api/auth/me`、`/api/auth/ws-ticket` 的顺序串起 OAuth 往返流程。

第四步读 `cookies.py`、`prefix.py`、`public_paths.py`。这三者解释了为什么 cookie 名称会有 `__Host-`、`__Secure-` 变体，为什么部署在反向代理路径前缀下时要调整 cookie `Path`，以及哪些 API 可以在未登录时公开。

最后读 `audit.py`、`login_page.py`，它们是安全审计和用户入口页面的配套实现，不是主控制流，但对排查登录失败和前端启动问题很有帮助。

## 常见误区

不要把 `dashboard_auth` 和 `hermes_cli/auth.py` 混为一谈。前者保护 Dashboard Web 访问，后者更偏模型供应商、CLI 登录、运行时凭据解析等认证状态。

不要以为 `routes.py` 自己会保护 `/api/auth/me`。实际 gate 在 `middleware.py`，路由里只做防御性检查。若中间件未启用，路由层的行为不能代表完整安全边界。

不要随意扩大 `PUBLIC_API_PATHS`。`public_paths.py` 明确说明这里只能放真正无敏感信息、只读、适合公开探测的 API；新接口如果需要用户上下文，应在登录后由 SPA 请求，而不是加入 allowlist。

不要忽略反向代理前缀。`prefix.py`、`cookies.py`、`routes.py` 共同依赖 `X-Forwarded-Prefix` 或 `dashboard.public_url` 来构造回调 URL、登录跳转 URL 和 cookie path。路径前缀处理不一致会导致 OAuth 回调、cookie 读取或登出清理失效。

不要把 refresh token 当成当前主流程必然存在。`cookies.py` 注释显示当前 contract v1 下 `refresh_token=""` 会跳过写入，失效会话的主要恢复路径是 401 或 302 后重新登录。
