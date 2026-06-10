# 目录：src/cli

## 它负责什么

`src/cli` 是 OpenClaw 命令行界面的主体实现层，负责把用户输入的 `openclaw ...` 参数解析为具体命令，并把命令分发到配置、网关、插件、模型、消息、节点、定时任务、更新等运行逻辑。它不是单纯的“命令文件集合”，而是 CLI 启动、命令注册、帮助输出、参数策略、懒加载、插件命令接入、JSON/错误输出规范等多个关注点的汇合处。

从当前片段看，真正的可执行入口在 `src/entry.ts`，`src/cli` 提供其后的 CLI 构建与命令体系。`src/cli/program.ts` 只做轻量导出，核心构建在 `src/cli/program/build-program.ts`。命令注册被拆成两层：核心命令由 `src/cli/program/command-registry-core.ts` 管理，扩展型或子 CLI 命令由 `src/cli/program/register.subclis-core.ts`、`src/cli/program/register.subclis.ts` 管理。大量顶层 `*-cli.ts` 文件则是具体命令族的注册模块。

## 直接子目录地图

`src/cli/program` 是 CLI 的中枢目录，包含 `build-program.ts`、命令描述符、注册表、路由、帮助、上下文、preaction hook，以及 `message` 命令组的细分注册。阅读 CLI 主流程应优先看这里。

`src/cli/gateway-cli` 承载 `openclaw gateway ...` 命令族。它包含 `register.ts`、`run.ts`、`run-command.ts`、`call.ts`、`discover.ts`、`dev.ts` 等文件，说明这里既处理前台运行 Gateway，也处理调用、发现、开发模式和运行循环。

`src/cli/daemon-cli` 承载网关服务生命周期管理，包含安装、启动、停止、重启、状态、探测、launchd 恢复、token drift、健康检查等逻辑。`src/cli/daemon-cli/test-helpers` 是该命令族的测试辅助。

`src/cli/cron-cli` 是定时任务命令族，包含 `register.ts`、`register.cron-add.ts`、`register.cron-edit.ts`、`register.cron-simple.ts`、调度选项和共享 thread id 处理。

`src/cli/node-cli` 是 headless node host 服务相关命令，目录内主要是 `register.ts`、`daemon.ts` 及测试。

`src/cli/nodes-cli` 是通过 Gateway 管理和调用节点能力的命令族，包含 pairing、status、notify、push、screen、camera、location、invoke、RPC 和格式化输出相关文件。

`src/cli/send-runtime` 根据当前片段只能判断是发送/出站运行时相关支撑目录，依据是邻近文件 `src/cli/outbound-send-deps.ts`、`src/cli/outbound-send-mapping.ts` 以及目录名；未逐文件展开，所以这里按“发送运行时支撑”理解。

`src/cli/shared` 放 CLI 共享小工具，目前片段显示有 `parse-port.ts` 一类低层解析工具。

`src/cli/update-cli` 根据目录名和顶层 `src/cli/update-cli.ts`、`src/cli/program/register.subclis-core.ts` 中的 `update` 注册项推断，是更新命令的实现拆分目录。

## 关键入口

第一入口是 `src/entry.ts`。它处理可执行文件启动时的前置工作：判断是否主模块、设置 `process.title`、安装 warning filter、规范化环境变量、启用 compile cache、处理 Windows argv、`--profile`、`--container`、`--no-color`、root version/help fast path 等。也就是说，很多“为什么命令还没进 Commander 就被处理了”的答案在这里。

CLI 程序构建入口是 `src/cli/program/build-program.ts`。它创建 `commander` 的 `Command`，启用 positional options，设置 `exitOverride`，创建 `ProgramContext`，配置 help，注册 preaction hooks，然后调用 `registerProgramCommands`。

命令注册入口是 `src/cli/program/command-registry.ts`。它把注册拆成 `registerCoreCliCommands` 和 `registerSubCliCommands`。核心命令来自 `src/cli/program/core-command-descriptors.ts`，例如 `setup`、`onboard`、`configure`、`config`、`doctor`、`message`、`agent`、`sessions`、`tasks`。子 CLI 描述来自 `src/cli/program/subcli-descriptors.ts`，例如 `gateway`、`daemon`、`models`、`nodes`、`devices`、`cron`、`docs`、`skills`、`update` 等。

参数预判入口是 `src/cli/argv.ts` 和 `src/cli/argv-invocation.ts`。它们在完整注册命令前先识别 root help/version、命令路径、root option、是否只注册 primary command。这是 CLI 启动性能和懒加载策略的基础。

## 主流程位置

主流程可以按四段理解。

第一段在 `src/entry.ts`：先做进程级 bootstrap，包括环境、颜色、profile、container、compile cache、respawn、root version/help fast path。这个阶段还没有进入普通命令 action。

第二段进入 `src/cli/program/build-program.ts`：创建 Commander program，挂载上下文和帮助格式，注册 preaction hook，再交给命令注册层。

第三段在 `src/cli/program/command-registry-core.ts`、`src/cli/program/register.subclis-core.ts`、`src/cli/program/register.subclis.ts`：根据当前 argv 决定注册全部命令、只注册 primary command，还是只注册某些特殊快速路径。命令模块大多通过动态 `import()` 加载，例如 `gateway` 加载 `src/cli/gateway-cli.ts`，而后再转到 `src/cli/gateway-cli/register.ts`。

第四段进入具体命令族：例如 Gateway 命令在 `src/cli/gateway-cli/register.ts` 下分配到 `run`、`call`、`discover`、`dev` 等；daemon 命令经 `src/cli/daemon-cli/register.ts`、`src/cli/daemon-cli/register-service-commands.ts` 转到生命周期 runner；message 命令在 `src/cli/program/register.message.ts` 和 `src/cli/program/message/*` 中展开；config 命令在 `src/cli/config-cli.ts` 中实现 get/set/unset/file/validate 等操作。

## 推荐阅读顺序

1. 先读 `src/entry.ts`，理解 CLI 进入 Commander 前已经处理了哪些 fast path、环境和启动策略。
2. 再读 `src/cli/program/build-program.ts`，把握 Commander program 如何创建、上下文如何挂载、help 和 preaction 如何接入。
3. 读 `src/cli/program/core-command-descriptors.ts`、`src/cli/program/subcli-descriptors.ts`，先建立完整命令地图，不急着看实现。
4. 读 `src/cli/program/command-registry.ts`、`src/cli/program/command-registry-core.ts`、`src/cli/program/register.subclis-core.ts`，理解命令如何懒加载、如何按 primary command 注册。
5. 读 `src/cli/argv.ts`、`src/cli/argv-invocation.ts`、`src/cli/command-registration-policy.ts`，补上“为什么有些命令没有 eager 注册”的判断逻辑。
6. 最后按兴趣进入具体命令族：网关看 `src/cli/gateway-cli`，服务生命周期看 `src/cli/daemon-cli`，节点看 `src/cli/nodes-cli`，消息看 `src/cli/program/message`，配置看 `src/cli/config-cli.ts`。

## 常见误区

不要把 `src/cli/program.ts` 当成主实现文件；它主要导出 `buildProgram`，真正逻辑在 `src/cli/program/build-program.ts` 和注册表文件里。

不要以为所有命令都会在启动时完整加载。当前代码明显有懒加载和 primary command 注册策略，相关判断分布在 `src/cli/argv.ts`、`src/cli/argv-invocation.ts`、`src/cli/command-registration-policy.ts`、`src/cli/program/register-command-groups.ts`。

不要把 `daemon` 和 `gateway` 混为一谈。`gateway` 偏向 Gateway 进程运行、调用和发现；`daemon` 是服务生命周期管理，并且从描述符看还是 legacy alias 语义的一部分。

不要认为插件命令只是静态命令表。`src/cli/program/register.subclis-core.ts` 中存在按命令路径策略加载插件 CLI 的逻辑，插件命令是否注册会受 help/version、命令路径策略等影响。

不要逐个叶子文件阅读这个目录。`src/cli` 是大目录，正确入口是先看命令描述符和注册链，再按命令族深入。测试文件数量很多，适合在理解实现后用来确认行为边界，而不是作为第一阅读材料。

不要在用户可见术语里说 `extensions`。本仓库规则要求产品和文档语境使用 `plugin/plugins`，`extensions/` 只是内部路径概念。
