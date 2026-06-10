# 文件：package.json

## 一句话定位

`package.json` 是 Hermes Agent 仓库根目录的 Node.js 依赖入口，主要职责不是构建前端或运行主程序，而是为 Python 主体工程补齐浏览器自动化所需的 `agent-browser` CLI，并声明最低 Node.js 运行环境。

## 它暴露/定义了什么

这个文件定义了根包 `hermes-agent` 的 npm 元数据：`name`、`version`、`description`、`private`、`license`、`repository`、`bugs`、`homepage` 等。其中 `repository`、`bugs`、`homepage` 指向项目外部地址，文档中可理解为项目源码、问题追踪和主页入口，真实地址此处记为 `[URL已移除]`。

真正有运行影响的是三块：

`dependencies` 只声明了 `agent-browser`，版本范围为 `^0.26.0`。这说明根 npm 环境服务于浏览器工具链，而不是整个 Hermes 的主依赖管理；Python 依赖由 `pyproject.toml`、虚拟环境和安装脚本管理。

`scripts.postinstall` 只输出提示文本：浏览器工具已准备好，并提示运行 `python run_agent.py --help`。它不下载浏览器、不启动服务，也不执行 Python 初始化。

`engines.node` 要求 `>=20.0.0`，与文档和安装脚本中“浏览器工具需要 Node.js 20+ / 22”的说法一致。`overrides.lodash` 将 `lodash` 固定到 `4.18.1`，但根据当前片段推断，它是面向传递依赖的安全或兼容覆盖；依据是根依赖本身没有直接引用 `lodash`，锁文件中也只展示了 `agent-browser` 的直接包信息。

## 谁调用它

最直接调用者是 npm：开发者或安装脚本在仓库根目录执行 `npm install` 时，npm 会读取 `package.json`，安装 `agent-browser`，生成或更新 `package-lock.json`，并触发 `postinstall`。

仓库安装脚本也依赖它。`scripts/install.sh` 会在检测到根目录 `package.json` 后执行根级 `npm install`，失败时提示浏览器工具可能不可用；`scripts/install.ps1` 在 Windows 安装路径中也会处理根 npm 安装，并额外管理全局或前缀下的 `agent-browser`。

运行期检查也会间接依赖它的结果。`hermes_cli/tools_config.py` 会尝试把 `agent-browser` 安装到根 `node_modules/`，并通过 `node_modules/.bin/agent-browser` 执行浏览器安装；`hermes_cli/doctor.py` 会检查根 `node_modules/agent-browser` 或 PATH 中的 `agent-browser`。`tools/browser_tool.py` 在本地浏览器模式中会搜索全局 CLI、扩展 PATH、根 `node_modules/.bin/`，找不到时提示可在仓库根目录执行 `npm install`。

此外，`website/`、`ui-tui/`、`web/`、`scripts/whatsapp-bridge/` 都有各自的 `package.json`，它们是独立 Node 子项目；根 `package.json` 不负责这些子项目的构建脚本。

## 它调用谁

`package.json` 本身不是代码模块，不主动调用函数。它通过 npm 的生命周期机制“调用”两类对象：

第一是 npm 安装解析器，根据 `dependencies.agent-browser` 拉取并安装 `agent-browser` 包。锁文件显示当前解析到 `agent-browser@0.26.0`，并暴露可执行命令 `agent-browser`，入口为包内 `bin/agent-browser.js`。

第二是 `postinstall` 脚本，它只调用 shell 的 `echo` 输出提示，不做业务初始化。

运行期的真实浏览器调用链不在这个文件中，而是在 `tools/browser_tool.py` 等 Python 工具中：这些工具找到 `agent-browser` 后，通过子进程执行导航、点击、截图、评估脚本等浏览器命令。

## 核心流程

典型流程是：用户或安装器在仓库根目录执行 `npm install`；npm 读取 `package.json`，确认 Node 版本满足 `>=20.0.0`，按 `package-lock.json` 安装 `agent-browser@0.26.0` 到 `node_modules/`；安装完成后执行 `postinstall` 输出提示；之后 Hermes 的浏览器工具在运行时从 PATH、Hermes 管理目录或根 `node_modules/.bin/agent-browser` 中定位 CLI；若定位成功，`tools/browser_tool.py` 等模块通过该 CLI 驱动本地 Chromium 或相关浏览器后端。

从项目分层看，根 `package.json` 是 Python Agent 与 Node 浏览器侧车工具之间的桥。它不参与 `run_agent.py` 的主对话循环，也不参与 `ui-tui`、`website`、`web` 的构建；它只保证根安装路径下有一个可被 Python 工具发现的浏览器自动化 CLI。

## 关键函数的高层作用

此文件没有 JavaScript 函数或类。可以把 npm 字段视为声明式入口：

`dependencies.agent-browser` 是核心声明，决定本地浏览器工具是否能通过根 `npm install` 获得 CLI。

`scripts.postinstall` 是安装后的提示钩子，只承担用户引导，不承担安装逻辑。

`overrides.lodash` 是依赖树覆盖策略，用于强制传递依赖版本。根据当前片段推断，它的修改需要结合完整锁文件和安全策略评估，不能只看根依赖数量。

`engines.node` 是运行环境门槛，影响安装器、开发文档和用户机器兼容性判断。

## 修改风险

修改 `agent-browser` 版本风险最高。`tools/browser_tool.py` 中大量逻辑依赖 `agent-browser` 的 CLI 行为、会话参数、引擎参数、JSON 输出、Chromium 安装路径和守护进程行为。升级可能带来命令行参数变化、输出格式变化、浏览器安装位置变化或 Windows shim 兼容问题；降级则可能缺少当前代码假设存在的能力。

删除根依赖会让“在仓库根目录执行 `npm install` 后浏览器工具可用”这个路径失效。安装脚本、doctor 检查、工具配置和用户文档都把根安装视为一种可用方案。

修改 `engines.node` 会影响安装体验。放宽可能让旧 Node 版本安装成功但运行 `agent-browser` 失败；收紧会让可工作的用户环境被 npm 警告或阻断。

修改 `postinstall` 要谨慎。当前脚本没有副作用，适合跨平台；若加入下载、启动服务、写配置等动作，可能破坏无网络安装、CI、发行版打包或安全审计流程。

修改 `overrides` 也有供应链风险。仓库开发规范强调依赖上界和安全固定，根 npm 依赖虽然少，但任何覆盖都可能改变传递依赖解析结果，需要同步检查 `package-lock.json`、安装脚本和浏览器工具回归。
