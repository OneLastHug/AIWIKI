# 目录：nix

## 它负责什么

`nix` 目录是 Hermes Agent 的 Nix/flake 打包与部署层。它不承载核心业务逻辑，而是把仓库里的 Python CLI、Ink/React TUI、Vite/React dashboard、内置 skills/plugins、NixOS service、开发 shell、CI 检查等拼装成可构建、可安装、可部署的 Nix flake 输出。

从根部 `flake.nix` 看，项目使用 `flake-parts` 组织 flake，并把主要实现拆到 `./nix/packages.nix`、`./nix/overlays.nix`、`./nix/nixosModules.nix`、`./nix/checks.nix`、`./nix/devShell.nix`。支持系统包括 `x86_64-linux`、`aarch64-linux`、`aarch64-darwin`。Python 依赖由 `uv2nix` 和 `pyproject-nix` 从 `pyproject.toml`、`uv.lock` 转换，Node 前端依赖通过 `buildNpmPackage` 和固定的 `fetchNpmDeps` hash 构建。

这个目录的角色可以概括为三层：第一层是构建产物，生成 `hermes-agent` 主包、`messaging`、`full`、`tui`、`web`、`fix-lockfiles` 等 flake packages；第二层是运行包装，把 `hermes`、`hermes-agent`、`hermes-acp` 包装成带有 `HERMES_BUNDLED_SKILLS`、`HERMES_BUNDLED_PLUGINS`、`HERMES_WEB_DIST`、`HERMES_TUI_DIR` 等环境变量的命令；第三层是 NixOS 集成，提供 `services.hermes-agent` 模块，负责用户、状态目录、配置合并、MCP server、systemd service 或容器化运行。

## 直接子目录地图

`nix` 下面没有直接子目录，只有一组 `.nix` 模块文件。地图式理解如下：

`packages.nix` 是 flake package 输出表，决定 `.#default`、`.#messaging`、`.#full`、`.#tui`、`.#web`、`.#fix-lockfiles` 指向什么。

`hermes-agent.nix` 是主 derivation，负责组装 Python venv、TUI、Web dashboard、skills、plugins，并生成最终 wrapper 命令。

`python.nix` 是 Python 虚拟环境构建器，使用 `uv2nix.lib.workspace.loadWorkspace` 读取仓库工作区，并通过 `pyproject-nix` 构造 `hermes-agent-env`。

`tui.nix` 构建 `ui-tui`，产物放到 `$out/lib/hermes-tui`，后续由主包复制到 `$out/ui-tui`。

`web.nix` 构建 `web` dashboard，运行 `tsc` 和 `vite build`，产物作为 `web_dist` 打包进主包。

`lib.nix` 是共享 npm helper，核心是 `mkNpmPassthru` 和 `mkFixLockfiles`，用于统一 Node 版本、npm lock hash 维护、dev shell npm 安装和 CI lockfile 检查。

`nixosModules.nix` 是 NixOS module，暴露 `services.hermes-agent` 的完整配置面。

`configMergeScript.nix` 生成一个 Python 脚本，用于把 Nix 声明的 settings 深合并到现有 `config.yaml`。

`checks.nix` 定义 flake checks，覆盖 package、NixOS module、配置合并、lockfile 等构建期验证。

`devShell.nix` 定义开发 shell，收集各 package 的 `passthru.devShellHook`，自动准备 Python 和 npm 依赖。

`overlays.nix` 暴露 `pkgs.hermes-agent`，便于外部 NixOS 配置或其他 flake 通过 overlay 使用此包。

## 关键入口

最外层入口是根目录 `flake.nix`。它只声明 inputs、systems 和 imports，不直接写复杂构建逻辑。读者应该把它看作路由表：`flake-parts.lib.mkFlake` 加载 `nix` 下的模块后，各模块分别贡献 `packages`、`checks`、`devShells`、`overlays`、`nixosModules`。

构建入口是 `nix/packages.nix`。它通过 `pkgs.callPackage ./hermes-agent.nix` 得到 `hermesAgent`，然后派生出不同安装口味：`default` 是基础包，`messaging` 追加 `extraDependencyGroups = [ "messaging" ]`，`full` 追加一批可移植 optional dependency groups，并在 Linux 上额外包含 `matrix`。这说明 Nix 包不是简单复制源码，而是通过同一个 overridable 主包参数化出多个 profile。

主包入口是 `nix/hermes-agent.nix`。这里最重要的是 `installPhase` 和 `makeWrapper`：它把 `../skills`、`../plugins`、`hermesWeb`、`hermesTui` 放进 `$out/share/hermes-agent` 或 `$out/ui-tui`，再包装 `hermes`、`hermes-agent`、`hermes-acp` 三个命令。wrapper 同时补 PATH，并设置 Hermes 运行时查找内置资源所需的环境变量。

部署入口是 `nix/nixosModules.nix`。它暴露 `flake.nixosModules.default`，用户启用 `services.hermes-agent.enable` 后，模块会根据选项生成用户、目录、配置、插件链接、systemd service，或在 `container.enable` 时生成容器化启动方式。

## 主流程位置

包构建主流程是：`flake.nix` 导入 `packages.nix`，`packages.nix` 调用 `hermes-agent.nix`，`hermes-agent.nix` 再分别调用 `python.nix`、`tui.nix`、`web.nix`、`lib.nix`。其中 `python.nix` 产出 sealed Python venv，`tui.nix` 和 `web.nix` 产出 Node 前端构建结果，最后由 `hermes-agent.nix` 统一安装、复制资源并创建命令 wrapper。

开发环境主流程在 `devShell.nix`。它取 `self'.packages` 的所有包，收集每个包的 `passthru.devShellHook`。主包的 hook 会根据 `pyproject.toml` 和 `uv.lock` hash 决定是否执行 `uv venv`、`uv pip install -e ".[all]"`；TUI/Web 的 hook 来自 `lib.nix` 的 `mkNpmPassthru`，根据 `package.json` 和 `package-lock.json` stamp 决定是否安装 npm 依赖并预取 hash。

NixOS 运行主流程在 `nixosModules.nix` 的 `config = lib.mkIf cfg.enable (lib.mkMerge [...])` 区域。根据当前片段推断，模块先把 `mcpServers` 映射进 Hermes config，再处理用户和系统包，然后通过 activation script 建立 `stateDir`、`.hermes`、配置文件、插件链接和 GC root，最后按 `container.enable` 分支生成普通 `systemd.services.hermes-agent` 或容器后端的 service。依据是文件中出现了 `system.activationScripts."hermes-agent-setup"`、`systemd.services.hermes-agent`、`virtualisation.docker.enable`、`ExecStart` 等关键节点。

检查流程在 `checks.nix`。它至少覆盖默认包构建、配置 key、NixOS module 行为、`configMergeScript` roundtrip，以及 `messaging` 包是否真的包含消息平台依赖等场景。CI 侧 `.github/workflows/nix.yml` 调用 `nix flake check` 和 `nix build`，lockfile hash 失配时提示运行 `nix run .#fix-lockfiles`。

## 推荐阅读顺序

建议先读根部 `flake.nix`，确认 flake inputs、systems 和模块拆分方式。然后读 `nix/packages.nix`，理解对外暴露的 package 名称和不同安装口味。第三步读 `nix/hermes-agent.nix`，这是最能解释“最终安装出来的 Hermes 长什么样”的文件，重点看 `let` 中如何构造 `hermesVenv`、`hermesTui`、`hermesWeb`，以及 `installPhase` 里的 wrapper 环境变量。

之后读 `nix/python.nix`，理解 Python 依赖如何从 uv workspace 进入 Nix。再读 `nix/tui.nix`、`nix/web.nix` 和 `nix/lib.nix`，把 Node 构建、npm hash、`fix-lockfiles` 的逻辑串起来。若关心部署，再集中读 `nix/nixosModules.nix`，优先看 `options.services.hermes-agent` 的选项区和 `config = lib.mkIf cfg.enable` 的生成区。最后读 `nix/checks.nix`，用测试反推哪些行为被认为是稳定契约。

## 常见误区

不要把 `nix` 目录理解成 Hermes 的业务入口。真正的 agent loop、CLI、工具注册仍在 Python 源码中；`nix` 只是把这些内容构建、封装和部署。

不要以为 `tui`、`web` 是运行时现装 npm 依赖。Nix 包构建时会用固定 hash 的 `fetchNpmDeps`，hash 不匹配需要更新 `nix/tui.nix` 或 `nix/web.nix` 里的 `hash`，通常通过 `nix run .#fix-lockfiles` 处理。

不要忽略 `makeWrapper` 设置的环境变量。Nix store 是只读的，运行时发现 bundled skills、plugins、Web dist、TUI bundle 主要依赖这些变量，而不是假设源码目录存在。

不要把 NixOS module 的 `settings` 当成完全覆盖用户配置。`configMergeScript.nix` 明确做 deep merge：Nix keys 覆盖同名项，但用户已有的其他 keys 会保留。

不要随意新增 Python 依赖到主包外侧。`hermes-agent.nix` 对 `extraPythonPackages` 做 collision 检查，避免插件包和 sealed venv 内包名冲突；常规可选依赖更符合项目模式的是通过 `extraDependencyGroups` 参数进入 `python.nix`。

不要认为 macOS 和 Linux checks 完全等价。`checks.nix` 注释显示完整 Python venv 检查偏 Linux-only，包和 devShell 仍面向 macOS 可用，但某些依赖或测试会按平台分支处理。
