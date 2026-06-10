# 目录：docker

## 它负责什么

`docker` 目录负责 Hermes Agent 容器镜像运行期的启动、初始化、权限修正和 s6-overlay 服务编排。它不是应用主逻辑目录，也不是 Docker 终端沙箱实现目录；这里更像“容器入口层”：把镜像中的 Hermes 程序、持久化数据目录 `$HERMES_HOME`、非 root 用户 `hermes`、dashboard 服务、profile gateway 服务，以及 `docker exec` 场景下的权限一致性串起来。

从当前片段看，容器采用 s6-overlay 架构：真实 `ENTRYPOINT` 是 `/init`，初始化脚本在 `/etc/cont-init.d/` 阶段运行，用户传入的 `CMD` 由 `docker/main-wrapper.sh` 作为 main program 处理，dashboard 等长驻进程由 `docker/s6-rc.d/` 下的服务定义监督。`docker/entrypoint.sh` 只是保留给旧集成的兼容 shim，不再是推荐入口。

这个目录还承担若干容器特有的“修复层”职责：支持 `PUID/PGID` 或 `HERMES_UID/HERMES_GID` 改写运行用户，修复 bind mount 数据卷所有权，处理 Docker socket 组权限，播种 `.env`、`config.yaml`、`SOUL.md`，同步内置 skills，发现 Playwright Chromium 路径，并保证 `docker exec <container> hermes ...` 写出的配置文件仍属于 `hermes` 用户。

## 直接子目录地图

`docker/cont-init.d` 是容器初始化脚本目录。这里的脚本在 s6-overlay 的 cont-init 阶段执行，主要做静态服务权限修正和 profile gateway 的启动前重建。`015-supervise-perms` 处理 s6 静态服务的 `supervise/`、`event/` 权限，使非 root 的 `hermes` 用户可以查询和控制服务。`02-reconcile-profiles` 会把 `/run/service` 交给 `hermes` 用户，并调用 `hermes_cli.container_boot` 重建每个 profile 对应的 gateway 服务槽。

`docker/s6-rc.d` 是静态 s6 服务定义目录。`dashboard` 定义 dashboard 长驻服务，`main-hermes` 是一个占位型 longrun 服务，`user/contents.d` 把这些服务纳入 s6 的 user bundle。这里的结构遵循 s6-rc 约定：每个服务目录含 `type`、`run`，dashboard 还含 `finish` 和依赖声明。

根目录下的脚本是容器入口和兼容层：`stage2-hook.sh` 是核心初始化脚本；`main-wrapper.sh` 负责实际执行用户的 CMD；`hermes-exec-shim.sh` 是 `docker exec` 调用 `hermes` 时的降权包装；`entrypoint.sh` 是旧入口兼容脚本；`SOUL.md` 是首次启动时播种到 `$HERMES_HOME/SOUL.md` 的默认人格模板。

## 关键入口

最关键的入口是 `docker/stage2-hook.sh`。它被镜像安装到 `/etc/cont-init.d/01-hermes-setup` 后执行，运行身份是 root，发生在用户服务启动前。它完成 `$HERMES_HOME` 创建、UID/GID remap、Docker socket group 加入、数据目录和安装树所有权修正、运行目录创建、安装方式标记写入、默认配置播种、`auth.json` bootstrap、skills 同步，以及浏览器可执行文件路径注入。

`docker/main-wrapper.sh` 是用户命令入口。它通过 `with-contenv` 恢复 s6 环境变量，切到 `/opt/data`，激活 `/opt/hermes/.venv`，然后按参数路由：无参数执行 `hermes`；第一个参数是可执行命令时直接执行，例如 `bash` 或 `sleep`；否则把参数当作 Hermes 子命令，执行 `hermes "$@"`。所有路径都会用 `s6-setuidgid hermes` 降到非 root 用户。

`docker/hermes-exec-shim.sh` 是另一个容易忽略的关键入口。它放在容器内较早的 `PATH` 上，用来拦截 `docker exec <container> hermes ...`。如果当前 UID 是 root，它默认降权到 `hermes` 后再执行真实的 `/opt/hermes/.venv/bin/hermes`，避免 `docker exec hermes login` 之类命令把 `auth.json`、`.env`、`config.yaml` 写成 root-only 文件。

## 主流程位置

容器启动主流程大致是：`/init` 启动 s6-overlay；`docker/stage2-hook.sh` 在 cont-init 早期完成数据卷、用户、配置和 skills 初始化；`docker/cont-init.d/015-supervise-perms` 修复静态 s6 服务控制目录权限；`docker/cont-init.d/02-reconcile-profiles` 调用 `hermes_cli/container_boot.py`，根据 `$HERMES_HOME/profiles` 和各 profile 的 `gateway_state.json` 重建 `/run/service/gateway-<profile>`；随后 s6-rc 启动 user bundle 中的静态服务；最后 Docker CMD 由 `docker/main-wrapper.sh` 执行，决定是进入 Hermes CLI、执行 Hermes 子命令，还是运行用户指定的普通可执行程序。

dashboard 的主流程在 `docker/s6-rc.d/dashboard/run`。只有 `HERMES_DASHBOARD` 为真时才启动 `hermes dashboard --host ... --port ... --no-open`；否则 `run` 直接退出，`docker/s6-rc.d/dashboard/finish` 返回 125，告诉 s6 不要循环重启这个服务。dashboard 的监听地址和端口来自 `HERMES_DASHBOARD_HOST`、`HERMES_DASHBOARD_PORT`，是否跳过认证保护由 `HERMES_DASHBOARD_INSECURE` 显式控制。

profile gateway 的主流程不直接写在 `docker` 目录的静态服务里，而是由 `docker/cont-init.d/02-reconcile-profiles` 转到 `hermes_cli/container_boot.py`。该模块会总是注册 `gateway-default`，再扫描 `$HERMES_HOME/profiles/<name>/` 中带 `SOUL.md` 的真实 profile；若上次 `gateway_state.json` 为 `running`，则自动启动，否则只注册为 down 状态等待用户显式启动。根据当前片段推断，运行期 profile 服务的创建逻辑还复用 `hermes_cli.service_manager.S6ServiceManager` 的 run-script 渲染，以保持启动时重建和运行时注册一致。

## 推荐阅读顺序

建议先读 `docker/stage2-hook.sh`，因为它解释了容器环境的基本假设：`HERMES_HOME` 默认是 `/opt/data`，应用安装在 `/opt/hermes`，运行用户是 `hermes`，很多权限问题都在这里被处理。

第二步读 `docker/main-wrapper.sh` 和 `docker/hermes-exec-shim.sh`。前者回答“容器启动后用户命令怎么跑”，后者回答“进入已运行容器执行 hermes 命令时为什么不会污染数据卷权限”。

第三步读 `docker/s6-rc.d/dashboard/run`、`docker/s6-rc.d/dashboard/finish`、`docker/s6-rc.d/main-hermes/run`。这能看清静态服务的边界：dashboard 是真实可选服务，`main-hermes` 当前主要是满足 s6 user bundle 结构的占位服务，并不承载用户 CMD。

第四步读 `docker/cont-init.d/015-supervise-perms`、`docker/cont-init.d/02-reconcile-profiles`，再跳到 `hermes_cli/container_boot.py`。这样可以理解容器重启后，持久化 profile 如何重新变成 s6 动态服务。

最后看 `docker/entrypoint.sh` 和 `docker/SOUL.md`。前者是兼容历史入口的迁移提示，后者只是默认人格文件模板，不是启动控制逻辑。

## 常见误区

一个常见误区是把 `docker/entrypoint.sh` 当作当前镜像的真实入口。当前代码明确说明真实入口已经是 `/init`，`entrypoint.sh` 只会转发到 `stage2-hook.sh`，并且不会执行用户 CMD。旧 wrapper 如果硬编码它，可能只完成初始化却不启动预期程序。

另一个误区是以为 `docker/s6-rc.d/main-hermes/run` 会运行 Hermes 主进程。实际上它当前执行 `sleep infinity`，作用是提供一个静态 user service 槽位。用户传入的 `hermes`、`hermes chat`、`bash`、`sleep infinity` 等命令由 `docker/main-wrapper.sh` 处理，不由这个服务处理。

还容易混淆的是“容器里的 Hermes 镜像运行”和“工具系统里的 Docker backend”。`docker` 目录管理的是 Hermes 自身作为容器运行时的初始化和服务编排；而 agent 使用 Docker 作为终端沙箱的逻辑分散在 `tools/file_tools.py`、`tools/environments/` 等邻近区域，不属于这个目录的直接职责。

最后，不要把 profile gateway 的服务目录当作持久文件。`/run/service` 是 tmpfs，容器重启会丢失；真正持久的是 `$HERMES_HOME` 和 `$HERMES_HOME/profiles`。因此 `hermes_cli/container_boot.py` 的职责是每次启动时根据持久 profile 状态重建服务槽，而不是恢复旧的 PID 或旧的 `/run/service` 内容。
