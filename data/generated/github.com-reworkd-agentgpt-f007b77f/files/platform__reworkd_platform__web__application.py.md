# 文件：platform/reworkd_platform/web/application.py

## 一句话定位

`platform/reworkd_platform/web/application.py` 是后端 FastAPI 应用的总装配入口：它不承载具体业务逻辑，而是负责创建 `FastAPI` 实例、配置跨域、注册生命周期事件、挂载 API 总路由，并统一接入平台级异常处理。

## 它暴露/定义了什么

该文件只定义了一个核心函数：`get_app() -> FastAPI`。

`get_app()` 是应用工厂函数，返回一个完整可运行的 `FastAPI` 对象。它将应用标题、版本、文档路径、OpenAPI 路径、默认响应类型等基础元信息集中配置在这里。版本号通过 `importlib.metadata.version("reworkd_platform")` 读取包元数据，因此运行环境中必须能正确安装或识别 `reworkd_platform` 包。

它还隐式决定了几个全局行为：默认响应使用 `UJSONResponse`；API 文档路径为 `/api/docs`、`/api/redoc`；OpenAPI schema 路径为 `/api/openapi.json`；所有业务 API 统一挂在 `/api` 前缀下。

## 谁调用它

生产启动链路中，`platform/reworkd_platform/__main__.py` 通过 `uvicorn.run("reworkd_platform.web.application:get_app", factory=True, ...)` 调用它。`factory=True` 表示 Uvicorn 会把字符串指向的对象当作应用工厂执行，而不是直接当作 ASGI app 使用。

测试链路中，`platform/reworkd_platform/conftest.py` 的 `fastapi_app` fixture 会调用 `get_app()` 创建测试应用，然后覆盖 `get_db_session` 依赖，让测试请求使用测试数据库 session。`client` fixture 再基于这个应用构造 `httpx.AsyncClient`。

因此，这个文件同时是运行时入口和测试应用入口，任何全局配置变更都会影响真实服务和大部分 API 测试。

## 它调用谁

`get_app()` 首先调用 `reworkd_platform.logging.configure_logging()`，把标准 logging 与 Uvicorn 日志接入 loguru，并按 `settings.log_level` 输出。

随后它读取 `reworkd_platform.settings.settings` 中的跨域配置，包括 `frontend_url` 和 `allowed_origins_regex`，并通过 `fastapi.middleware.cors.CORSMiddleware` 配置 CORS。

生命周期方面，它调用 `reworkd_platform.web.lifetime.register_startup_event(app)` 和 `register_shutdown_event(app)`。启动事件会初始化数据库 engine、`async_sessionmaker`，并调用 tokenizer 初始化逻辑；关闭事件会释放数据库 engine。

路由方面，它导入并挂载 `reworkd_platform.web.api.router.api_router`。该总路由继续聚合 `monitoring`、`agent`、`models`、`auth`、`metadata` 等子路由。

异常方面，它把 `PlatformaticError` 绑定到 `platformatic_exception_handler`。当业务代码抛出这类预期异常时，FastAPI 会返回统一 JSON 结构，而不是走默认异常响应。

## 核心流程

核心流程可以理解为“创建空应用，再逐层插入平台能力”。

第一步是日志初始化。这里放在应用实例创建之前，目的是让后续启动、路由处理、Uvicorn 访问日志都进入统一日志系统。由于 `configure_logging()` 会重设部分 logger handler，重复调用 `get_app()` 时也会重复配置日志，这是测试和多 worker 环境中需要注意的点。

第二步是构造 `FastAPI`。构造参数集中定义了应用元信息和文档入口，`default_response_class=UJSONResponse` 使普通接口默认采用更快的 JSON 序列化响应。

第三步是配置 CORS。允许来源由配置项决定：固定来源使用 `settings.frontend_url`，正则来源使用 `settings.allowed_origins_regex`。同时允许 credentials、任意 method 和任意 header，这说明前端可能依赖 cookie、认证头或跨域凭据请求。

第四步是注册生命周期事件。启动时，`lifetime._setup_db()` 会创建异步数据库 engine 和 session factory，并写入 `app.state.db_engine`、`app.state.db_session_factory`；`init_tokenizer(app)` 也会把 tokenizer 相关状态挂到应用上。关闭时释放 `app.state.db_engine`。根据当前片段推断，依赖注入层的数据库 session 获取逻辑会从 `app.state.db_session_factory` 派生 session，依据是测试中覆盖了 `get_db_session`，而生命周期里正好初始化了 session factory。

第五步是挂载 API 路由。`api_router` 被统一加上 `/api` 前缀，所以子路由中的 `/agent`、`/auth` 等最终会暴露为 `/api/agent`、`/api/auth` 等路径。

第六步是注册平台异常处理器。`PlatformaticError` 及其子类如 `OpenAIError`、`ReplicateError`、`MaxLoopsError` 会被转为带 `error`、`detail`、`code` 字段的 JSON 响应，HTTP 状态码固定为 `409`。

## 关键函数的高层作用

`get_app()` 是唯一关键函数。它的作用不是处理请求，而是定义后端应用的“运行外壳”：日志、FastAPI 元信息、跨域边界、启动/关闭资源管理、API 路由入口、异常响应规范都在这里汇合。

`register_startup_event()` 和 `register_shutdown_event()` 是它依赖的生命周期注册函数，不在本文件实现，但对本文件语义很重要：它们决定应用启动后是否具备数据库连接池、session factory 和 tokenizer 服务。

`api_router` 是业务路由聚合点。`application.py` 不直接知道每个接口的实现细节，只负责把总路由接到 `/api` 下。

`platformatic_exception_handler` 是异常出口。它把平台内“可预期业务异常”转为统一响应，同时按异常对象的 `should_log` 决定是否记录日志。

## 修改风险

最高风险是调整 `get_app()` 的调用形态或返回值。`__main__.py` 依赖 `get_app` 作为 Uvicorn factory，测试 fixture 也直接调用它；如果改成模块级 `app = FastAPI()` 或需要额外参数，会同时破坏启动脚本和测试夹具。

修改 CORS 配置也有明显风险。当前允许 credentials、任意方法和任意 header，但来源受 `frontend_url` 和正则限制。放宽来源会引入安全问题；收紧来源则可能导致前端登录、认证请求或本地开发环境失败。

修改生命周期注册顺序需要谨慎。数据库 engine 被写入 `app.state`，关闭事件假定 `app.state.db_engine` 一定存在；如果启动过程中跳过 `_setup_db()`，关闭时可能报错。反过来，如果关闭事件未执行，数据库连接可能泄漏。

修改 API 前缀会产生外部兼容性影响。`/api` 是文档、OpenAPI 和业务路由的一致入口；改变它会影响前端请求路径、测试用例、部署反向代理配置和外部调用方。

异常处理器的行为也不宜随意改。当前 `PlatformaticError` 返回 HTTP `409`，同时响应体里另有业务 `code` 字段；如果改成使用异常自身的 `code` 作为 HTTP 状态码，客户端错误处理逻辑可能需要同步调整。

最后，`metadata.version("reworkd_platform")` 依赖包元数据。若在未安装包、仅源码直接运行的环境中调用 `get_app()`，可能出现版本读取失败。修改打包、模块名或运行方式时，需要验证这条路径仍然成立。
