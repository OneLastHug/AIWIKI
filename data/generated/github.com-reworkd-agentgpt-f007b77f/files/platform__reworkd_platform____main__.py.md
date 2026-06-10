# 文件：platform/reworkd_platform/__main__.py

## 一句话定位

`platform/reworkd_platform/__main__.py` 是后端 `reworkd_platform` 包的命令行启动入口：当以 Python 模块方式运行该包时，它负责把配置读取出来，并交给 `uvicorn` 启动 FastAPI 应用。

## 它暴露/定义了什么

这个文件只定义了一个核心函数 `main()`，以及一个标准的 `if __name__ == "__main__": main()` 执行保护。

`main()` 没有构造业务对象，也不直接注册路由、数据库或中间件。它的职责非常集中：调用 `uvicorn.run()`，指定应用工厂字符串 `"reworkd_platform.web.application:get_app"`，并把监听地址、端口、worker 数、热重载和日志级别等运行参数从 `reworkd_platform.settings.settings` 注入进去。

因此它暴露的是“进程启动方式”，不是 Web 应用本身。真正的 FastAPI 实例由 `platform/reworkd_platform/web/application.py` 中的 `get_app()` 创建。

## 谁调用它

直接调用者通常不是仓库内其他 Python 模块，而是运行时环境。根据当前片段推断，典型方式是执行类似 `python -m reworkd_platform`，Python 会寻找包内的 `__main__.py` 并运行。依据是该文件位于包根 `reworkd_platform` 下，并包含标准 `__main__` 入口判断。

仓库测试侧没有直接使用这个入口，而是在 `platform/reworkd_platform/conftest.py` 中直接导入并调用 `get_app()` 构造测试应用。这说明测试绕过了 `uvicorn` 进程层，验证重点在 FastAPI 应用对象和依赖覆盖，而不是启动命令本身。

部署侧根据当前片段推断可能由 Docker 或启动脚本间接触发，因为 `docker-compose.yml` 挂载了 `./platform:/app/src/`，且后端配置集中在环境变量中；但当前读取片段未看到完整启动命令，所以不能确认具体命令行。

## 它调用谁

它直接调用两类对象：

`uvicorn.run()`：ASGI 服务器启动函数，负责创建监听 socket、管理 worker、加载 ASGI 应用并运行事件循环。

`reworkd_platform.settings.settings`：全局配置实例，来自 `platform/reworkd_platform/settings.py` 的 `Settings()`。该对象基于 `pydantic.BaseSettings`，支持从 `.env` 和带 `ENV_PREFIX` 的环境变量读取配置。

`uvicorn.run()` 再通过字符串 `"reworkd_platform.web.application:get_app"` 间接调用 `platform/reworkd_platform/web/application.py` 的 `get_app()`。由于参数 `factory=True`，这里传入的不是已经创建好的 ASGI app，而是一个“应用工厂函数”。Uvicorn 会导入该函数并调用它来得到 FastAPI 实例。

## 核心流程

启动流程可以概括为四步。

第一步，模块导入 `uvicorn` 和 `settings`。导入 `settings` 时，`Settings()` 已经实例化，运行参数会从默认值、`.env`、环境变量中解析出来，例如 `host`、`port`、`workers_count`、`reload`、`log_level`。

第二步，如果文件作为主入口执行，进入 `main()`。

第三步，`main()` 调用 `uvicorn.run()`，传入应用工厂路径、worker 数、监听地址、端口、reload 开关、日志级别和 `factory=True`。

第四步，Uvicorn 加载 `reworkd_platform.web.application:get_app`。`get_app()` 会配置日志，创建 `FastAPI` 实例，设置 API 文档路径和默认响应类，注册 CORS 中间件，挂载启动/关闭生命周期事件，包含主 API 路由 `api_router`，并注册 `PlatformaticError` 的异常处理器。

应用启动事件继续进入 `platform/reworkd_platform/web/lifetime.py`：`register_startup_event()` 注册的 `_startup()` 会调用 `_setup_db(app)` 创建 SQLAlchemy async engine 与 session factory，并调用 `init_tokenizer(app)` 初始化 tokenizer；关闭事件会释放 `app.state.db_engine`。

## 关键函数的高层作用

`main()` 是本文件唯一值得关注的函数。它是“配置到运行时”的桥接层：不关心业务 API，不关心数据库细节，只负责把 `settings` 中的进程级参数翻译给 Uvicorn。

其中最关键的是应用目标字符串和 `factory=True`。如果没有 `factory=True`，Uvicorn 会把 `get_app` 当成 ASGI 应用对象而不是工厂函数，启动语义会出错。这个设计也让应用创建逻辑集中在 `web/application.py`，便于测试直接调用 `get_app()`，同时让生产启动仍走 Uvicorn。

`settings.log_level.lower()` 是一个小转换：`Settings.log_level` 的类型约束使用大写字面量，如 `"INFO"`、`"DEBUG"`，而 Uvicorn 常用小写日志级别字符串。这个转换避免配置层和服务器层格式不一致。

`if __name__ == "__main__"` 是样板入口保护，只用于确保模块被直接执行时才启动服务，被导入时不会产生副作用。

## 修改风险

这个文件虽短，但属于进程启动关键路径，修改风险集中在运行时可用性上。

首先，应用工厂路径 `"reworkd_platform.web.application:get_app"` 一旦写错，服务会在启动阶段无法导入应用。移动或重命名 `get_app()` 时必须同步这里，否则测试中直接调用 `get_app()` 可能仍通过，但真实启动失败。

其次，`factory=True` 不能随意删除。当前 `web/application.py` 暴露的是工厂函数，不是模块级 `app` 对象；删除后会改变 Uvicorn 加载语义。

第三，`workers_count` 与 `reload` 的组合要谨慎。开发环境默认 `reload=True`、`workers_count=1` 比较合理；如果在生产中调整 worker、reload 或导入副作用，可能影响多进程启动、资源初始化次数和日志行为。

第四，`host`、`port`、`log_level` 来自全局 `settings`。如果在这里硬编码，会绕过环境变量配置体系，破坏 Docker、本地开发和部署环境的一致性。

第五，这里不应该加入数据库初始化、路由注册或业务预热逻辑。那些职责已经在 `get_app()` 和 `web/lifetime.py` 中分层处理；把它们塞进入口文件会让测试启动路径和真实启动路径产生差异，也会增加 Uvicorn reload 或多 worker 场景下的重复执行风险。
