# 文件：docker-compose.yml

## 一句话定位

`docker-compose.yml` 是仓库根目录的一键本地编排入口，用 Docker Compose 同时拉起 AgentGPT 的前端 `frontend`、后端平台服务 `platform` 和 MySQL 数据库 `agentgpt_db`，把开发环境所需的构建、端口、环境变量、数据卷和服务依赖集中声明在一个文件中。

## 它暴露/定义了什么

这个文件定义了 Compose 版本 `3.9`，并声明三个核心服务。

`frontend` 使用 `./next/Dockerfile` 构建 Next.js 应用，容器名为 `frontend`，把宿主机端口 `3000` 映射到容器 `3000`。它挂载 `./next/.env` 到容器内 `/next/.env`，并把 `./next/` 整个目录挂载到 `/next/`，同时用匿名卷保护 `/next/node_modules` 和 `/next/.next`，避免宿主目录覆盖容器内依赖和构建缓存。

`platform` 使用 `./platform/Dockerfile` 的 `prod` 阶段构建 Python 后端，容器名为 `platform`，暴露 `8000:8000`，设置 `restart: always`。它挂载 `./platform` 到 `/app/src/`，读取 `next/.env` 作为 `env_file`，并额外覆盖数据库连接相关环境变量，例如 `REWORKD_PLATFORM_DB_HOST=agentgpt_db`、端口 `3307`、用户和库名 `reworkd_platform`。

`agentgpt_db` 基于 `mysql:8.0`，同时指定 `./db` 构建上下文；`db/Dockerfile` 会把 `setup.sql` 放入 MySQL 初始化目录。它把宿主机 `3308` 映射到容器内 MySQL `3307`，使用命名卷 `agentgpt_db` 持久化 `/var/lib/mysql`，并通过 `mysqld` 命令指定 `utf8mb4` 字符集和排序规则。

## 谁调用它

直接调用者是 Docker Compose CLI，例如开发者在仓库根目录执行 `docker compose up --build` 或兼容旧命令 `docker-compose up --build` 时会读取该文件。根据 README 片段推断，仓库的安装/启动脚本或文档流程也会间接依赖它，因为文档要求用户按脚本提示补齐 API keys 后访问前端服务。

在运行时层面，开发者、CI 或本地启动脚本并不是调用某个函数，而是把该 YAML 交给 Docker Compose，由 Compose 根据服务图构建镜像、创建网络、挂载卷并启动容器。

## 它调用谁

它“调用”的对象主要是 Docker 构建上下文和容器镜像，而不是源码函数。

`frontend` 调用 `next/Dockerfile`。该 Dockerfile 基于 `node:19-alpine`，安装依赖，复制 `wait-for-db.sh` 和 `entrypoint.sh`，暴露 `3000`，入口为 `/entrypoint.sh`，默认命令是 `npm run dev`。

`platform` 调用 `platform/Dockerfile` 的 `prod` target。该 Dockerfile 基于 `python:3.11-slim-buster`，安装 MySQL client 编译依赖、OpenJDK、Poetry，执行 `poetry install --only main`，最后通过 `python -m reworkd_platform` 启动后端。

`agentgpt_db` 调用 `mysql:8.0` 镜像和 `db/Dockerfile`，后者把 `db/setup.sql` 注入 `/docker-entrypoint-initdb.d`，由 MySQL 官方 entrypoint 在首次初始化数据目录时执行。

## 核心流程

第一步，Compose 读取服务定义并构建镜像。`frontend` 从 `./next` 构建 Node/Next.js 镜像；`platform` 从 `./platform` 构建 Python 后端镜像；`agentgpt_db` 从 `./db` 构建带初始化 SQL 的 MySQL 镜像。

第二步，Compose 创建默认网络和命名卷。三个服务处在同一个 Compose 网络中，因此 `platform` 可以用服务名 `agentgpt_db` 作为数据库主机名。数据库数据写入命名卷 `agentgpt_db`，容器删除后数据仍保留。

第三步，数据库容器启动并监听容器内 `3307`。它通过 `MYSQL_TCP_PORT=3307` 改变 MySQL 服务端口，同时对宿主机开放 `3308`。这意味着容器间访问应使用 `agentgpt_db:3307`，宿主机调试访问应使用本机 `3308`。

第四步，`platform` 依赖 `agentgpt_db`，Compose 会先启动数据库容器，再启动后端容器。需要注意，`depends_on` 只保证启动顺序，不保证 MySQL 已经可连接；如果后端启动阶段没有自带重试机制，仍可能遇到数据库未就绪的竞态。

第五步，`frontend` 启动 Next.js 开发服务并暴露 `3000`。它通过挂载源码目录支持本地改动在容器中生效，通过 `next/.env` 获得前端和部分后端配置，例如 `.env.example` 中出现的 `NEXT_PUBLIC_BACKEND_URL`、`NEXTAUTH_URL`、`REWORKD_PLATFORM_*` 等变量。

## 关键函数的高层作用

这个文件没有传统意义上的函数。可把三个 service 视为它的核心“模块”。

`frontend` 的高层作用是承载用户界面和前端开发服务器。它负责把浏览器请求引入 Next.js 应用，并通过 `.env` 中的后端地址与平台服务协作。

`platform` 的高层作用是承载业务 API、Agent 执行逻辑和第三方能力集成。它读取 `REWORKD_PLATFORM_*` 配置，连接 MySQL，并对外开放 `8000` 端口供前端访问。

`agentgpt_db` 的高层作用是提供平台持久化数据库。它负责初始化 schema、保存运行数据，并作为 `platform` 的状态依赖。

`volumes.agentgpt_db` 是辅助定义，用于声明数据库持久化卷；它本身没有业务逻辑，但决定了数据库状态是否跨容器生命周期保留。

## 修改风险

最高风险是端口和数据库环境变量不一致。当前配置中容器内 MySQL 使用 `3307`，宿主机映射为 `3308:3307`，同时 `.env.example` 也指向容器网络内的 `agentgpt_db:3307`。如果只改 Compose 端口而不改 `REWORKD_PLATFORM_DB_PORT`、`DATABASE_PORT` 或应用配置，后端会连接失败。

第二个风险是环境变量命名可能存在新旧约定差异。Compose 中使用 `REWORKD_PLATFORM_DB_HOST`、`REWORKD_PLATFORM_DB_PORT` 等变量，而 `.env.example` 里也出现 `REWORKD_PLATFORM_DATABASE_HOST`、`REWORKD_PLATFORM_DATABASE_URL`。根据当前片段推断，后端配置层可能兼容其中一种或多种命名；修改时需要确认 `platform` 的配置读取代码，否则容易出现看似设置正确但运行时未生效的问题。

第三个风险是卷挂载会改变镜像内文件状态。`frontend` 挂载整个 `./next/`，同时用匿名卷隔离 `node_modules` 和 `.next`；如果删除这些匿名卷声明，宿主机空目录可能覆盖容器依赖，导致 `npm run dev` 找不到包。`platform` 挂载 `./platform:/app/src/`，会覆盖镜像构建时复制进去的代码，适合开发，但也可能掩盖镜像构建产物问题。

第四个风险是 `depends_on` 的语义有限。把它当作“数据库已可用”会导致偶发启动失败；如果要提高稳定性，应在后端启动脚本或应用连接层加入等待/重试，而不是只调整 Compose 顺序。

第五个风险是数据库卷持久化。修改 `MYSQL_DATABASE`、用户、密码或初始化 SQL 后，已有 `agentgpt_db` 卷不会自动重新初始化；开发者可能需要显式删除卷才会重新执行 `db/setup.sql`，但这会清空本地数据。
