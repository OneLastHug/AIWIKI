# 文件：Dockerfile

## 一句话定位

`Dockerfile` 是 Hermes Agent 官方容器镜像的构建入口：它把 Python 代理、Node 前端/TUI、Playwright 浏览器、s6-overlay 进程监督、运行时用户和数据卷约定打包成一个可直接运行 `hermes`、`gateway run`、`dashboard` 的生产镜像。

## 它暴露/定义了什么

这个文件定义的是镜像级运行契约，而不是应用内 API。它暴露的关键内容包括：

- 基础运行环境：`debian:13.4`，并从独立阶段复制 `uv`、`node`、`npm`、`corepack`。
- 运行时环境变量：`PYTHONUNBUFFERED=1`、`PLAYWRIGHT_BROWSERS_PATH=/opt/hermes/.playwright`、`HERMES_WEB_DIST=/opt/hermes/hermes_cli/web_dist`、`HERMES_HOME=/opt/data`、以及包含 shim 和虚拟环境的 `PATH`。
- 数据持久化位置：`VOLUME [ "/opt/data" ]`，对应 compose 中的 `~/.hermes:/opt/data`。
- 运行用户模型：构建期创建 `hermes` 用户，容器启动时由 s6 初始化脚本根据 `HERMES_UID`、`HERMES_GID` 做 UID/GID 映射，再让服务以 `hermes` 用户运行。
- 容器入口：`ENTRYPOINT [ "/init", "/opt/hermes/docker/main-wrapper.sh" ]`，`/init` 来自 s6-overlay，`main-wrapper.sh` 决定最终执行 `hermes` 子命令还是普通命令。
- 构建参数：`TARGETARCH`、`S6_OVERLAY_VERSION`、多组 s6 tarball SHA256、`HERMES_GIT_SHA`。

## 谁调用它

直接调用者是 Docker/BuildKit 生态：

- 本地用户通过 `docker build` 或 `docker compose up --build` 构建镜像；`docker-compose.yml` 的 `gateway` 服务使用 `build: .` 和 `image: hermes-agent`。
- CI 通过 `.github/workflows/docker-publish.yml` 构建并发布多架构镜像；根据搜索结果，该 workflow 多处指定 `file: Dockerfile`，并会传入 Git SHA 作为镜像元信息或构建参数。
- 运行时用户通过 `docker run` 或 compose 的 `command` 覆盖参数，例如 `["gateway", "run"]`、`["dashboard", "--host", "127.0.0.1", "--no-open"]`，这些参数最终被 `main-wrapper.sh` 接管。

## 它调用谁

构建阶段主要“调用”或依赖这些仓库内外组件：

- 外部镜像阶段：`ghcr.io/astral-sh/uv:...` 提供 `uv`/`uvx`，`node:22-bookworm-slim` 提供 Node 22 LTS。
- 系统包：通过 `apt-get` 安装 `curl`、`ripgrep`、`ffmpeg`、`gcc`、`python3-dev`、`git`、`openssh-client`、`docker-cli` 等运行和工具执行所需组件。
- s6-overlay：下载并校验 noarch、arch、symlinks tarball，安装到根文件系统，让 `/init` 成为 PID 1。
- Node 构建链：根目录、`web`、`ui-tui` 分别执行 `npm install`，随后 `web` 和 `ui-tui` 执行 `npm run build`。
- Python 构建链：`uv sync --frozen --no-install-project ...` 安装依赖，再 `uv pip install --no-deps -e "."` 建立 editable 安装。
- 仓库脚本和服务目录：`docker/stage2-hook.sh`、`docker/main-wrapper.sh`、`docker/hermes-exec-shim.sh`、`docker/cont-init.d/*`、`docker/s6-rc.d/*`。

## 核心流程

第一步是准备构建来源。文件使用多阶段构建，从 `uv_source` 取 Python 包管理工具，从 `node_source` 取 Node 22 LTS，最终运行镜像基于 Debian 13。这样避免 Debian 自带 Node 版本落后，同时保持运行层相对可控。

第二步是安装系统依赖和 s6-overlay。`apt-get` 装基础命令、编译依赖、Docker CLI 等；随后根据 `TARGETARCH` 映射到 s6 的 `x86_64` 或 `aarch64` 包名，下载对应 tarball，并用 Dockerfile 内固定的 SHA256 校验。这个阶段决定容器是否能作为长期运行的多服务宿主，而不是简单执行单进程。

第三步是做依赖缓存优化。文件先复制 `package.json`、各层 `package-lock.json`、`pyproject.toml`、`uv.lock`，先安装 Node 和 Python 依赖，再复制完整源码。这种层顺序让普通源码改动不会反复重装依赖。Playwright 的 Chromium shell 也在构建期安装，并通过 `PLAYWRIGHT_BROWSERS_PATH` 放到 `/opt/hermes/.playwright`，避免运行时被 `/opt/data` 数据卷覆盖。

第四步是构建应用资产并修正权限。源码复制后构建 `web` Dashboard 和 `ui-tui` 终端 UI；再给 `/opt/hermes` 设置可读权限，并让 `.venv`、`ui-tui`、`node_modules` 对 `hermes` 用户可写，以支持运行时 lazy dependency 和 TUI 可能触发的 npm 行为。

第五步是写入运行时契约。可选写入 `.hermes_build_sha`，复制 s6 服务定义，注册 cont-init 脚本，设置 `HERMES_HOME=/opt/data`，安装 `docker/hermes-exec-shim.sh` 到 `/opt/hermes/bin/hermes`，最后把入口设为 `/init + main-wrapper.sh`。

## 关键函数的高层作用

`Dockerfile` 没有传统函数；这里的关键“函数级”单元是 Docker 指令和被接入的脚本。

`FROM ... AS uv_source` 和 `FROM ... AS node_source` 负责把工具链来源固定下来，最终镜像只复制需要的二进制和 JS 模块，减少运行镜像对上游镜像布局的直接耦合。

`s6-overlay install` 相关 `ARG`、`ADD`、`RUN` 是容器进程模型的核心。它不只是安装 init，而是通过校验和、多架构分支、tar 解包建立 `/init`、`s6-rc`、`cont-init.d` 可用的监督体系。

`uv sync --frozen --no-install-project ...` 是 Python 依赖层的核心。它按 `uv.lock` 固定解析结果安装生产镜像需要的 extras，刻意不使用 `--all-extras`，避免把训练、benchmark、Android 等不属于发布镜像的重依赖拉进来。

`npm install` 和 `npm run build` 负责前端资产。根目录、`web`、`ui-tui` 分开安装，说明镜像同时承载浏览器 Dashboard 与 Ink TUI，而不是只打包 CLI。

`ENTRYPOINT` 和 `CMD` 定义运行入口。`/init` 先执行 s6 初始化、权限修复、服务注册，然后 `main-wrapper.sh` 处理无参数、Hermes 子命令、普通 shell 命令等路由。根据当前片段推断，`main-wrapper.sh` 是保持 `docker run image --tui`、`docker run image gateway run`、`docker run image sleep infinity` 都能工作的关键脚本，依据是 Dockerfile 注释明确描述了这些参数形态。

`docker/hermes-exec-shim.sh` 解决 `docker exec <container> hermes ...` 默认 root 执行的问题。它位于 `PATH` 前面，当 root 调用 `hermes` 时切换到 `hermes` 用户再执行真实虚拟环境里的命令，避免 `$HERMES_HOME` 下配置文件被 root 写成普通服务不可读。

## 修改风险

最高风险是改 `ENTRYPOINT`、`PATH`、s6 目录或 cont-init 脚本复制位置。`docker-compose.yml` 明确提示不要绕过 `/init`，否则 UID/GID 映射、数据卷 chown、profile gateway 重建、Dashboard 开关和监督树都可能失效。

依赖层顺序也很敏感。把 `COPY . .` 提前会破坏缓存，使普通源码改动触发 Python/Node 依赖全量重装；改 `npm_config_install_links=false` 可能让 workspace/file 依赖变成复制模式，进而触发 TUI 启动时反复 `npm install` 或权限错误。

权限相关修改容易造成运行时隐性故障。`.venv` 必须可写以支持 `tools/lazy_deps.py` 安装剩余可选依赖；`ui-tui` 和 `node_modules` 对 `hermes` 用户可写是为了容忍运行时 TUI 检查；`/opt/data` 是数据卷，若 UID/GID 映射或 shim 被改坏，网关、Dashboard、`docker exec hermes` 会在配置文件所有权上互相踩踏。

供应链风险集中在基础镜像 digest、s6 版本和 checksum、Python/Node lockfile。升级 Node、uv、Debian 或 s6 不是简单改版本号，还要验证 glibc 兼容、多架构 tarball 名称、SHA256、Playwright 浏览器安装、前端构建和 CI 发布 workflow。

最后，`HERMES_GIT_SHA` 和 `.hermes_build_sha` 虽不影响运行主流程，但影响问题排查。删除这段会让容器中的 `hermes dump` 或启动横幅无法稳定显示构建来源，降低线上镜像问题定位能力。
