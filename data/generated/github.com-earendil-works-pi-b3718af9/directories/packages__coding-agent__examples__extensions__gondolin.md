# 目录：packages/coding-agent/examples/extensions/gondolin

## 它负责什么

`packages/coding-agent/examples/extensions/gondolin` 是一个独立的 pi extension 示例包，演示如何把 pi 的内置工具执行路由到本地 Gondolin micro-VM 中。它不是核心运行时的一部分，而是 `packages/coding-agent/examples/extensions` 下的可运行扩展示例，重点展示“保留 pi 原有工具接口，但替换工具底层 operations”的扩展写法。

它的核心目标是：启动一个 Gondolin VM，把宿主机当前工作目录挂载到 guest 内的 `/workspace`，然后让 `read`、`write`、`edit`、`bash`、`ls`、`find`、`grep` 等工具在 VM 文件系统和进程环境中执行。对 `/workspace` 下文件的变更会写回宿主机当前项目；guest 里其他文件系统变更则隔离在 VM 内。这样可以让 agent 仍然操作真实项目文件，同时把 shell 命令、路径访问和部分环境副作用放进 VM 边界中。

目录中的 `package.json` 声明包名为 `pi-extension-gondolin`，通过 `pi.extensions` 指向 `./index.ts`，并依赖 `@earendil-works/gondolin`。根据 `index.ts` 文件头注释，它要求 Node.js 版本满足 `@earendil-works/gondolin` 的运行条件，并需要本机安装 QEMU。这个目录的定位更接近“带外部依赖的扩展包示例”，不同于同层许多单文件 extension 示例。

## 直接子目录地图

这个目录本身没有直接子目录，只有少量包级文件：

`index.ts` 是唯一业务入口，包含 Gondolin VM 生命周期、路径映射、工具 operations 适配、命令注册和事件处理。

`package.json` 是扩展包清单，声明 `type: module`、示例脚本、`pi.extensions` 入口和运行依赖。

`package-lock.json` 锁定 npm 依赖版本，用于复现实例扩展的安装环境。

`.gitignore` 处理该示例目录本地依赖或生成物的忽略规则。

因此阅读这个目录时，不需要做深层目录遍历，重点在 `index.ts` 的分段结构和它如何接入 `@earendil-works/pi-coding-agent` 的 extension API。

## 关键入口

关键入口是 `packages/coding-agent/examples/extensions/gondolin/index.ts` 的默认导出：

`export default function (pi: ExtensionAPI)`

pi 加载 extension 时会调用这个工厂函数。函数内部先记录 `localCwd = process.cwd()`，也就是运行 `pi -e ...` 时用户所在项目目录；随后创建一组本地工具定义，例如 `createReadTool(localCwd)`、`createWriteTool(localCwd)`、`createBashTool(localCwd)` 等。这里的本地工具对象主要用于继承工具的名称、参数 schema、描述和渲染信息，真正执行时会被替换为 Gondolin 版本的 operations。

另一个入口层面是 `package.json` 中的：

`"pi": { "extensions": ["./index.ts"] }`

这让该目录可以作为 pi package 被识别。根据 `docs/extensions.md` 的扩展机制，extension 可以通过 `pi -e` 指定路径快速测试，也可以放入自动发现目录或通过 settings/package 方式加载。这个示例头部注释给出的典型用法是先在 `packages/coding-agent/examples/extensions/gondolin` 中安装依赖，然后在目标项目目录下用 `pi -e /path/to/.../gondolin` 启动。

## 主流程位置

主流程集中在 `index.ts` 后半段，按执行顺序可以分为四层。

第一层是路径映射。`GUEST_WORKSPACE` 固定为 `/workspace`。`stripAtPrefix` 处理 pi 常见的 `@path` 输入；`toPosix` 把宿主路径分隔符转为 POSIX 风格；`isInsideHostPath` 判断路径是否在当前工作目录内；`hostPathToGuest` 与 `toGuestPath` 把用户输入路径转换到 guest 路径。这里是理解这个扩展的基础：相对路径默认落到 `/workspace`，宿主工作区内的绝对路径也映射到 `/workspace`，工作区外绝对路径则按 guest 绝对路径处理。

第二层是 VM 文件系统 operations。`createGondolinReadOps`、`createGondolinWriteOps`、`createGondolinEditOps`、`createGondolinLsOps` 把 pi 内置工具需要的读写、访问、建目录、列目录、stat 等能力转接到 `vm.fs`。也就是说，工具仍然由 `createReadTool`、`createWriteTool` 等内置工厂创建，但底层 I/O 不再直接访问 Node 本地文件系统，而是访问 Gondolin VM 的 VFS。

第三层是搜索和 shell。`walkGuestFiles` 负责在 guest 内递归遍历文件，并跳过 `.git`、`node_modules`。`createGondolinFindOps` 基于它实现 glob 查找；`executeGondolinGrep` 基于它实现 grep，包含匹配数量限制、上下文行、长行截断和总输出截断。`createGondolinBashOps` 则通过 `vm.exec([shellPath, "-lc", command])` 执行命令，并处理 cwd、环境变量、输出流、超时和 abort 信号。

第四层是 extension 注册。`startVm` 使用 `VM.create` 创建 VM，并把 `localCwd` 通过 `RealFSProvider` 挂载到 `/workspace`；随后探测 guest 中是否有 `bash`，没有则回退到 `/bin/sh`。`ensureVm` 负责懒启动和并发复用。`pi.on("session_start")` 启动 VM，`pi.on("session_shutdown")` 关闭 VM，`pi.registerCommand("gondolin")` 提供状态查看命令。随后多次 `pi.registerTool` 覆盖式注册内置工具的 VM 版本，最后 `pi.on("user_bash")` 让用户 bash 也使用 Gondolin bash operations。

## 推荐阅读顺序

建议先读 `package.json`，确认这是一个以 `./index.ts` 为入口、依赖 `@earendil-works/gondolin` 的扩展包，而不是普通源码模块。

然后读 `index.ts` 顶部注释，先建立运行模型：当前工作目录会被挂载到 guest 的 `/workspace`，工作区写入会回写宿主机，其他 guest 文件系统变化被隔离。

接着读 `index.ts` 中的路径转换函数：`toGuestPath`、`hostPathToGuest`、`isInsideHostPath`。这部分决定工具参数里的路径最终落在哪里，也是避免误解“VM 隔离范围”的关键。

之后读 operations 工厂：`createGondolinReadOps`、`createGondolinWriteOps`、`createGondolinEditOps`、`createGondolinLsOps`、`createGondolinFindOps`、`executeGondolinGrep`、`createGondolinBashOps`。这些函数展示了如何把 pi 工具抽象绑定到另一个执行后端。

最后读默认导出函数，重点看 `startVm`、`ensureVm`、`session_start`、`session_shutdown`、`registerTool`、`user_bash` 的串联关系。读完这里，就能理解整个示例如何在 pi 生命周期里启动 VM、替换工具执行、展示状态并清理资源。

## 常见误区

第一个误区是把这个目录当成 Gondolin 的完整实现。实际上它只是 pi extension 示例，VM、VFS、进程执行能力来自 `@earendil-works/gondolin`，本目录主要负责把 pi 工具协议适配到 Gondolin API。

第二个误区是认为所有文件写入都完全隔离。根据当前片段可见，`localCwd` 被 `RealFSProvider` 挂载到 guest 的 `/workspace`，所以 `/workspace` 下的文件改动会写回宿主项目。隔离主要发生在 guest 其他文件系统区域，以及命令运行环境层面。

第三个误区是忽略启动位置。`localCwd = process.cwd()` 取的是运行 pi 时的当前目录，不是 extension 所在目录。也就是说，从哪个项目目录启动 pi，哪个目录就会被挂载到 `/workspace`。

第四个误区是把 `grep` 和 `find` 理解为直接调用系统命令。这里的 `find` 和 `grep` 是 TypeScript 层实现：通过 `vm.fs` 遍历 guest 文件，做 glob 和正则/字面量匹配；只有 `bash` 路径会通过 `vm.exec` 调 guest shell。

第五个误区是以为 `registerTool` 新增了别名工具。这里更准确地说，是用同名工具定义重新注册/覆盖内置工具执行逻辑：外观仍像 pi 的内置工具，但执行后端被换成 Gondolin operations。
