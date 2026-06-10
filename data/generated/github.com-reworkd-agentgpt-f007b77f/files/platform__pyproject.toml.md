# 文件：platform/pyproject.toml

## 一句话定位

`platform/pyproject.toml` 是 `platform` 后端 Python 服务的项目清单与工程规则入口，负责定义 Poetry 包元数据、运行依赖、开发依赖、类型检查、测试环境和构建后端；它不承载业务逻辑，但决定 `reworkd_platform` 服务能否被安装、启动、测试、打包和在 Docker 中构建。

## 它暴露/定义了什么

这个文件主要定义五类内容。

第一类是 Poetry 项目信息：包名为 `reworkd_platform`，版本为 `0.1.0`，作者、维护者和 `README.md`。这些元数据会被 Poetry 和 `importlib.metadata` 读取。仓库中 `platform/reworkd_platform/web/application.py` 通过 `metadata.version("reworkd_platform")` 获取版本号，并把它写入 FastAPI 应用的 `version` 字段。

第二类是运行依赖：它把服务固定为 Python `^3.11`，并声明 FastAPI、Uvicorn、Pydantic v1、SQLAlchemy 2、MySQL 驱动、Kafka、Sentry、LangChain、OpenAI SDK、Pinecone、Stripe、AWS SDK、HTTP 客户端、tokenizer 等库。根据依赖组合可以看出，这个后端既提供 HTTP API，也连接数据库、对象存储、向量库、支付、LLM 和外部工具服务。

第三类是开发依赖：包括 `pytest`、`pytest-asyncio`、`pytest-cov`、`mypy`、`black`、`isort`、`flake8`、`pre-commit`、`types-requests` 等，用来支撑测试、格式化、静态检查和类型标注。

第四类是工具配置：`[tool.isort]` 使用 `black` 风格，并指定 `reworkd_platform` 为源码路径；`[tool.mypy]` 开启 `strict = true`，但同时放宽第三方库缺失导入、未类型化调用、装饰器等现实约束；`[tool.pytest.ini_options]` 设置 warning 策略和测试环境变量 `REWORKD_PLATFORM_DB_BASE=reworkd_platform_test`。

第五类是构建系统：`[build-system]` 使用 `poetry-core` 和 `poetry.core.masonry.api`，说明该目录是标准 Poetry 构建项目。

## 谁调用它

最直接的调用者是 Poetry。`platform/README.md` 中的本地运行流程是 `poetry install` 后执行 `poetry run python -m reworkd_platform`，因此安装依赖、创建环境、识别包元数据都依赖这个文件。

Docker 构建也调用它。`platform/Dockerfile` 先复制 `pyproject.toml` 到镜像工作目录，再执行 `poetry install --only main` 安装运行依赖；复制完整源码后又执行一次 `poetry install --only main`。开发镜像阶段则执行 `poetry install`，会包含开发依赖。README 也明确指出，修改 `poetry.lock` 或 `pyproject.toml` 后需要重新 build 镜像。

测试、lint、类型检查工具间接调用它。执行 `pytest` 时会读取 `[tool.pytest.ini_options]`；`mypy` 和 `isort` 会读取对应配置；Poetry 安装开发依赖后，这些命令才能稳定运行。

运行时也有一处间接调用：`platform/reworkd_platform/web/application.py` 使用 `metadata.version("reworkd_platform")` 读取已安装包版本，这个版本来源于 Poetry 元数据。

## 它调用谁

`pyproject.toml` 本身不是程序，不主动“调用”代码。根据当前片段推断，它通过 Poetry 和各类工具把外部包、构建后端、测试配置交给下游执行，主要“指向”的对象包括：

`poetry-core` 负责构建；`fastapi`、`uvicorn`、`pydantic`、`ujson` 支撑 Web API；`sqlalchemy`、`aiomysql`、`mysqlclient` 支撑 MySQL 数据访问；`boto3`、`botocore`、`aws-secretsmanager-caching` 支撑 AWS 相关能力；`langchain`、`openai`、`tiktoken`、`replicate`、`wikipedia`、`pinecone-client` 支撑 Agent、LLM、工具调用和向量记忆；`pytest`、`mypy`、`black`、`isort`、`flake8` 支撑工程质量流程。

## 核心流程

安装流程从 `platform/pyproject.toml` 开始：Poetry 读取包元数据和依赖约束，结合 `platform/poetry.lock` 解析出确定版本，然后把依赖安装到本地虚拟环境或 Docker 镜像环境中。Docker 中还关闭了 Poetry 虚拟环境创建，即依赖直接进入镜像 Python 环境。

启动流程是：依赖安装完成后，命令执行 `python -m reworkd_platform`，进入 `platform/reworkd_platform/__main__.py` 的 `main()`。`main()` 调用 `uvicorn.run()`，目标应用工厂是 `reworkd_platform.web.application:get_app`。`get_app()` 构造 FastAPI 应用，读取包版本、注册 CORS、中间件、启动/关闭事件、API router 和异常处理器。这个链路是否能启动，取决于 `pyproject.toml` 中声明的运行依赖是否完整且版本兼容。

测试流程是：开发依赖安装后运行 `pytest`，pytest 读取本文件中的 warning 规则和环境变量。这里把 `REWORKD_PLATFORM_DB_BASE` 指向 `reworkd_platform_test`，目的是把测试数据库基础名和默认运行环境隔离。

质量检查流程是：`isort` 使用 `black` profile 保持导入格式一致；`mypy` 以 strict 模式作为基线，但允许常见第三方库和历史代码中的弱类型边界。

## 关键函数的高层作用

这个文件没有函数。与它关系最密切的关键函数是 `platform/reworkd_platform/__main__.py` 的 `main()` 和 `platform/reworkd_platform/web/application.py` 的 `get_app()`。

`main()` 是服务进程入口，负责把配置中的 host、port、worker、reload、log level 传给 Uvicorn。它依赖 `uvicorn` 存在，而 `uvicorn` 正是在 `pyproject.toml` 的运行依赖中定义。

`get_app()` 是 FastAPI 应用工厂，负责组装应用对象。它依赖 `fastapi`、`ujson`、`pydantic` 配置体系以及包元数据读取能力；其中 `metadata.version("reworkd_platform")` 要求项目以正确包名安装，否则版本读取可能失败。

辅助配置如 `[tool.pytest.ini_options]`、`[tool.mypy]`、`[tool.isort]` 没有运行时函数，但会改变测试、类型检查和导入排序的行为。

## 修改风险

最大风险是依赖版本兼容性。当前项目使用 `pydantic <2.0`、`fastapi ^0.98.0`、`openai ^0.28.0`、`langchain ^0.0.295`，这些都是旧接口生态。贸然升级到 Pydantic v2、OpenAI SDK 1.x 或较新的 LangChain，可能导致模型定义、设置读取、LLM 调用、tool schema、异步行为全面不兼容。

第二个风险是数据库依赖。`aiomysql`、`mysqlclient`、`sqlalchemy` 与 Dockerfile 中的系统包 `default-libmysqlclient-dev`、`gcc`、`pkg-config` 有耦合。删除或替换这些依赖，可能让镜像构建失败，或者让运行时数据库连接失败。

第三个风险是包名和版本元数据。`name = "reworkd_platform"` 被运行时代码读取；改名不仅影响安装，还会影响 `metadata.version("reworkd_platform")`。如果确实要改包名，需要同步修改应用代码和构建发布流程。

第四个风险是测试隔离配置。`pytest` 环境变量控制测试数据库命名，随意删除可能导致测试连接默认库，造成测试污染开发数据。warning 策略中 `"error"` 会把大部分警告提升为错误，升级依赖后测试可能因为新警告失败。

第五个风险是 Poetry 配置结构。文件同时存在旧式 `[tool.poetry.dev-dependencies]` 和新版 `[tool.poetry.group.dev.dependencies]`。这在当前 Poetry 版本下可能可用，但继续演进时容易出现依赖重复或解析差异，例如 `mypy` 在两处声明了不同版本范围。调整开发依赖时应顺手检查 `poetry lock` 结果和 Docker dev/prod 两种安装路径。
