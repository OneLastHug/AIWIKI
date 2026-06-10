# 文件：platform/README.md

## 一句话定位

`platform/README.md` 是 `platform` 后端服务的本地开发、容器启动、配置约定和测试/质量检查入口说明文档；它不参与运行时执行，但承担“新开发者如何启动并验证 `reworkd_platform` FastAPI 服务”的导航职责。

## 它暴露/定义了什么

这个文件主要定义了几类使用约定，而不是定义代码 API。第一类是本地启动方式：通过 `poetry install` 安装依赖，再用 `poetry run python -m reworkd_platform` 启动服务。第二类是 Docker 启动方式：README 中写的是使用 `deploy/docker-compose.yml` 和可选的 `deploy/docker-compose.dev.yml` 组合启动、构建和测试。第三类是项目结构说明，解释 `reworkd_platform` 包下 `db`、`services`、`settings.py`、`web`、`tests` 等目录的职责。第四类是配置约定：所有环境变量应以 `REWORKD_PLATFORM_` 为前缀，并由 `reworkd_platform/settings.py` 中的 `Settings.Config.env_prefix` 控制。第五类是工程质量入口，包括 `pre-commit`、`black`、`autoflake`、`flake8`、`mypy`、`pytest` 和覆盖率命令。

需要注意的是，根据当前片段推断，这份 README 带有模板生成痕迹。依据是开头写明项目由 `fastapi_template` 生成，并且 README 提到的 `platform/deploy` 目录在当前仓库片段中未发现；实际仓库根目录存在 `docker-compose.yml`，但 README 未直接描述它。因此它的部分 Docker 指令可能已经落后于当前仓库结构。

## 谁调用它

运行时没有任何 Python 模块调用 `platform/README.md`。它的“调用者”是人和工程流程：新成员阅读它来搭建开发环境，维护者参考它统一测试、格式化、类型检查命令，CI/脚本作者可能根据其中命令设计自动化流程，但当前片段没有证据表明 CI 直接解析或执行该 README。

从包配置看，`platform/pyproject.toml` 的 `readme = "README.md"` 会在 Python 包元数据生成或发布时引用同目录 README。因此它也可能被 Poetry 构建流程作为项目说明读取，但这属于打包元数据用途，不是业务调用。

## 它调用谁

README 本身不调用代码，但它指导用户间接调用多个系统入口。`poetry run python -m reworkd_platform` 会进入 `platform/reworkd_platform/__main__.py`，其中 `main()` 调用 `uvicorn.run()`。`uvicorn` 的应用目标是 `reworkd_platform.web.application:get_app`，并以 `factory=True` 的方式创建 FastAPI 应用。

配置方面，启动入口读取 `reworkd_platform.settings.settings`。`Settings` 继承 `pydantic.BaseSettings`，会读取 `.env` 和以 `REWORKD_PLATFORM_` 为前缀的环境变量。Web 应用工厂 `get_app()` 又读取同一个 `settings`，用于 CORS、文档路径、路由挂载和生命周期事件注册。

工具链方面，README 指向 Poetry、Docker Compose、pre-commit、pytest、black、autoflake、flake8、mypy 等命令。外部文档链接在原文中出现，但这里按要求不展开真实地址，仅可视为 `[URL已移除]`。

## 核心流程

本地开发流程是：开发者进入 `platform` 目录，安装 Poetry 依赖，然后执行 `python -m reworkd_platform`。Python 模块入口加载 `settings`，`main()` 将 host、port、workers、reload、log_level 等配置传给 `uvicorn.run()`。Uvicorn 再调用 `get_app()` 构造 FastAPI 实例，应用工厂配置日志、创建 `FastAPI`、注册 CORS 中间件、挂载 `/api` 路由、注册启动/关闭事件，并把自定义异常 `PlatformaticError` 绑定到统一异常处理器。启动后，接口文档路径为 `/api/docs`。

配置流程是：开发者在 `.env` 中写入 `REWORKD_PLATFORM_PORT`、`REWORKD_PLATFORM_RELOAD`、`REWORKD_PLATFORM_ENVIRONMENT` 等变量；`Settings.Config` 通过 `env_file = ".env"` 和 `env_prefix = ENV_PREFIX` 读取它们。派生属性如 `db_url`、`kafka_enabled`、`pusher_enabled`、`sid_enabled` 会把原始配置转换成运行时判断或连接信息。

测试流程是：README 建议先启动 MySQL，再运行 `pytest -vv .`；也提供了 Docker Compose 中运行 `api pytest` 的方式。但由于当前片段没有 `platform/deploy`，这部分 Docker 流程需要和实际编排文件重新校准。

## 关键函数的高层作用

`reworkd_platform.__main__.main()` 是 README 中本地启动命令最终进入的函数。它不处理业务，只负责把配置传给 `uvicorn.run()`，并指定应用工厂字符串 `reworkd_platform.web.application:get_app`。修改 README 的启动命令时，必须理解这个入口，否则容易造成服务启动路径、reload 行为或日志级别说明不一致。

`reworkd_platform.web.application.get_app()` 是真实 Web 应用构造点。它创建 FastAPI 实例，设置 API 文档路径，添加 CORS，注册生命周期事件，挂载 `api_router`，并配置平台级异常处理。README 里关于 Swagger、端口和服务可用性的描述，最终都依赖该函数和 `settings` 的组合。

`Settings` 及其属性是配置约定的落点。`db_url` 负责拼接 MySQL async URL；`kafka_consumer_group` 在开发环境使用本机名，生产环境固定为 `platform`；`pusher_enabled`、`kafka_enabled`、`helicone_enabled`、`sid_enabled` 用于判断外部能力是否启用。README 的环境变量说明如果变更，应同步检查这些字段名称和默认值。

## 修改风险

最大风险是 README 与真实仓库结构漂移。当前 README 仍描述 `deploy/docker-compose.yml`，但当前片段未发现 `platform/deploy`，这会直接误导 Docker 启动、构建和测试流程。若要修改该文件，应先确认实际容器入口是根目录 `docker-compose.yml`、其他 compose 文件，还是曾经遗漏的部署目录。

第二个风险是配置前缀说明和 `Settings.Config.env_prefix` 不一致。README 写的是 `REWORKD_PLATFORM_`，实际代码通过 `ENV_PREFIX` 注入；如果以后修改 `constants.py` 中的前缀，README 必须同步，否则 `.env` 示例会失效。

第三个风险是端口、文档路径和启动方式说明过时。`__main__.py` 默认读取 `settings.port`，`settings.py` 默认端口为 `8000`，`get_app()` 的文档路径是 `/api/docs`。这些值一旦调整，README 中的本地访问说明、Docker 暴露端口和 API 文档说明都需要一起更新。

第四个风险是测试依赖描述不足。README 只强调 MySQL 和 pytest，但 `pyproject.toml` 显示服务还依赖 OpenAI、Kafka、Pinecone、Sentry、Pusher、Stripe 等外部能力；虽然很多能力可通过配置关闭或为空，但集成测试或特定模块测试可能仍需要额外环境变量。修改测试说明时应区分“最小测试环境”和“完整集成环境”。

第五个风险是把模板说明当成权威架构文档。README 的项目结构树较概括，且可能没有覆盖当前实际业务模块。对关键服务、路由、数据库模型或外部服务集成做架构判断时，应以 `reworkd_platform/web`、`reworkd_platform/db`、`reworkd_platform/services` 和 `settings.py` 的当前代码为准。
