# 目录：db

## 它负责什么

`db` 是这个仓库里用于本地/容器化数据库启动的最小目录，职责不是定义业务数据模型，而是提供一个可被 `docker-compose.yml` 构建的 MySQL 8.0 镜像上下文。它的核心作用有两个：第一，声明数据库镜像基于 `mysql:8.0`；第二，把初始化脚本 `setup.sql` 放入 MySQL 官方镜像约定的 `/docker-entrypoint-initdb.d` 目录，让容器首次初始化数据目录时自动执行。

从当前片段看，`db` 更像基础设施入口，而不是 ORM 层。应用侧真正的数据模型、连接管理和 CRUD 代码分散在相邻目录：前端/Next 侧有 `next/prisma/schema.prisma`、`next/src/server/db.ts`；后端/Platform 侧有 `platform/reworkd_platform/db`、`platform/reworkd_platform/settings.py`、`platform/reworkd_platform/web/lifetime.py`。因此阅读 `db` 时，要把它理解为“数据库容器和初始化权限”的提供者，而不是“数据库业务逻辑”的所在处。

## 直接子目录地图

`db` 当前没有直接子目录，只有两个文件：

`db/Dockerfile`：数据库镜像构建入口。它以 `mysql:8.0` 为基础镜像，并把 `setup.sql` 添加到 `/docker-entrypoint-initdb.d`。这意味着初始化脚本由 MySQL 镜像自身的 entrypoint 机制执行，而不是应用代码显式调用。

`db/setup.sql`：数据库初始化 SQL。它创建 `reworkd_platform` 用户，并授予 `CREATE`、`ALTER`、`DROP`、`INSERT`、`UPDATE`、`DELETE`、`SELECT` 等权限。文件注释说明这些权限主要是为了 Prisma migration 的 shadow database 需求，因为 Prisma 在迁移时需要创建影子数据库。

## 关键入口

本目录最关键入口是 `db/Dockerfile`。它很短，但决定了 `setup.sql` 是否会被 MySQL 官方镜像识别并执行。`ADD setup.sql /docker-entrypoint-initdb.d` 是整个目录的核心连接点。

外部调用入口在 `docker-compose.yml` 的 `agentgpt_db` 服务。该服务使用 `build.context: ./db`，因此 compose 启动数据库时会读取 `db/Dockerfile`。同一个服务还配置了 `MYSQL_DATABASE`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`MYSQL_TCP_PORT`，并挂载命名卷 `agentgpt_db:/var/lib/mysql` 保存数据库文件。

需要特别注意端口：容器内 MySQL 端口配置为 `3307`，compose 映射为宿主机 `3308:3307`。容器网络中的其他服务，例如 `platform`，使用 `agentgpt_db:3307` 访问；宿主机如果直连则应看映射端口。

## 主流程位置

数据库容器主流程大致是：运行 `docker-compose.yml` 后，`agentgpt_db` 服务以 `./db` 为构建上下文构建镜像；`db/Dockerfile` 拉取 MySQL 8.0 并复制 `setup.sql`；MySQL 容器首次启动且 `/var/lib/mysql` 为空时，官方 entrypoint 根据环境变量创建默认数据库和用户，然后执行 `/docker-entrypoint-initdb.d` 下的 SQL 脚本；`setup.sql` 补充创建 `reworkd_platform` 用户并授予 Prisma 迁移需要的权限；随后数据库以 `utf8mb4` 字符集和 `utf8mb4_unicode_ci` 排序规则启动。

应用消费流程不在 `db` 内。根据当前片段推断，后端 `platform` 通过 `docker-compose.yml` 中的 `REWORKD_PLATFORM_DB_HOST`、`REWORKD_PLATFORM_DB_PORT`、`REWORKD_PLATFORM_DB_USER`、`REWORKD_PLATFORM_DB_PASS`、`REWORKD_PLATFORM_DB_BASE` 获得连接信息，再由 `platform/reworkd_platform/settings.py` 组装 MySQL async URL，`platform/reworkd_platform/web/lifetime.py` 在应用生命周期中创建 engine/session factory，`platform/reworkd_platform/db/dependencies.py` 把 `AsyncSession` 注入 API 依赖，具体模型和 CRUD 位于 `platform/reworkd_platform/db`。

Next 侧则使用 `DATABASE_URL`，由 `next/src/env/schema.mjs` 校验环境变量，`next/src/server/db.ts` 创建 `PrismaClient`，模型定义位于 `next/prisma/schema.prisma`。这解释了为什么 `setup.sql` 特意提到 Prisma shadow database：它服务于 Next/Prisma 迁移能力，而不只是 MySQL 自身启动。

## 推荐阅读顺序

建议先读 `docker-compose.yml` 中的 `agentgpt_db` 服务，弄清楚 `db` 是如何被构建、暴露端口、挂载数据卷和设置环境变量的。然后读 `db/Dockerfile`，确认初始化 SQL 的挂载位置。接着读 `db/setup.sql`，理解它为什么授予创建、修改、删除等权限。

之后再跳到应用层：如果关注前端认证、NextAuth 或 Prisma 数据结构，继续看 `next/prisma/schema.prisma` 和 `next/src/server/db.ts`；如果关注后端 API 如何访问数据库，看 `platform/reworkd_platform/settings.py`、`platform/reworkd_platform/web/lifetime.py`、`platform/reworkd_platform/db/dependencies.py`，再进入 `platform/reworkd_platform/db` 下的 models 与 crud。这样的顺序能避免一开始就把容器初始化、ORM schema、业务 CRUD 混在一起。

## 常见误区

第一个误区是把 `db` 当成数据库模型目录。当前 `db` 下没有 schema、migration 或业务表定义，它只负责 MySQL 容器构建和初始化权限。业务模型应去 `next/prisma` 或 `platform/reworkd_platform/db` 查。

第二个误区是以为 `setup.sql` 每次启动都会重新执行。MySQL 官方镜像通常只在数据目录首次初始化时执行 `/docker-entrypoint-initdb.d` 脚本；如果命名卷 `agentgpt_db` 已经存在，修改 `setup.sql` 后重启容器不一定生效，需要理解卷生命周期。

第三个误区是混淆容器端口和宿主机端口。compose 中 `agentgpt_db` 容器内监听 `3307`，宿主机映射到 `3308`；容器间访问通常用服务名 `agentgpt_db` 加容器端口，而不是宿主机端口。

第四个误区是把 `setup.sql` 中的广泛权限视为生产最佳实践。这里的注释明确说明它是为了 Prisma shadow database 迁移需求，且当前配置用户名、密码都偏本地开发风格。若部署到真实环境，应重新评估权限范围、凭据来源和数据库初始化方式。

第五个误区是认为 `MYSQL_USER` 已经足够，不需要 `setup.sql`。普通 MySQL 初始化用户未必具备 Prisma 创建 shadow database 所需的权限，所以这里额外执行授权脚本。换句话说，`docker-compose.yml` 的环境变量负责基础数据库/用户创建，`db/setup.sql` 负责补齐迁移工具需要的权限。
