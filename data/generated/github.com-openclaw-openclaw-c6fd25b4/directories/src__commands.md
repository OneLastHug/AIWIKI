# 目录：src/commands

## 它负责什么

`src/commands` 是 OpenClaw CLI 的命令实现层。它不直接负责把命令挂到 `commander` 程序上；注册动作主要在 `src/cli/program/register.*.ts` 中完成。`src/commands` 更像“命令业务层”：接收 CLI 注册层传入的 options 和 `RuntimeEnv`，然后完成配置读取、鉴权选择、gateway 调用、插件/频道发现、状态扫描、修复迁移、输出格式化等具体工作。

这个目录覆盖的命令面很宽，包括 `agent`、`agents`、`channels`、`models`、`status`、`health`、`doctor`、`configure`、`onboard`、`sessions`、`tasks`、`backup`、`reset`、`uninstall`、`dashboard` 等。目录风格是“复杂域拆子目录，普通命令平铺”：较大的命令域如 `channels`、`models`、`migrate`、`status-all` 会拆成子目录；大量单命令或共享 helper 则直接放在 `src/commands/*.ts`。

从职责边界看，`src/commands` 处在 CLI 与核心运行时之间。它会调用 `src/config` 读取配置，调用 `src/gateway` 与 gateway 通信，调用 `src/plugins` / `src/plugin-sdk` 处理插件与 provider 能力，调用 `src/flows` 复用交互式流程，也会调用 `src/agents` 管理 agent 会话和工作区。根据当前片段推断，它是 CLI 用户路径最集中的编排目录，而不是底层协议、插件 SDK 或 agent 执行器本体。

## 直接子目录地图

`src/commands/agent` 存放 agent 会话相关的局部实现，目前能看到 `session.ts`，与顶层 `agent.ts`、`agent-via-gateway.ts`、`agents.commands.*.ts` 共同组成 agent 命令族。

`src/commands/channel-setup` 负责频道安装和 setup 阶段的发现、插件解析、trusted catalog、registry adapter 等逻辑。它被 `onboard` 流程和 `src/flows/channel-setup*.ts` 使用。

`src/commands/channels` 是 `openclaw channels ...` 的子命令实现目录，包含 `add`、`list`、`logs`、`remove`、`resolve`、`status`、`capabilities` 等。顶层 `src/commands/channels.ts` 是这个子目录的 barrel，统一导出各子命令。

`src/commands/doctor` 承接 doctor 内部的局部模块，例如 channel capability、repair sequencing、legacy config repair、finalize config flow、emit notes 等。大量 doctor 检查仍以 `src/commands/doctor-*.ts` 平铺在顶层，说明 doctor 仍是一个横跨很多系统面的命令族。

`src/commands/gateway-status` 是 gateway status 的专用拆分区，包含 discovery、probe-run、output、helpers 等，角色偏向 gateway 状态探测和展示。

`src/commands/migrate` 负责迁移命令的上下文、provider 选择、skill 选择、apply、output 和类型定义。顶层 `src/commands/migrate.ts` 是命令入口。

`src/commands/models` 是模型配置和模型列表命令的主目录，包含 `list.*`、`set.ts`、`auth.ts`、`fallbacks.ts`、`aliases.ts`、`scan.ts` 等。这里同时处理配置模型、provider catalog、manifest catalog、auth profile、可用性探测和表格输出。

`src/commands/onboard-non-interactive` 是非交互 onboarding 的拆分实现，例如 `api-keys.ts`、`local.ts`、`remote.ts`。顶层 `onboard-non-interactive.ts` 负责串接。

`src/commands/setup` 当前主要放 setup 相关测试目录，命令入口仍在顶层 `setup.ts`。

`src/commands/status-all` 是 `openclaw status --all` 的报告生成区，包含 gateway、channels、diagnosis、report-data、report-lines、report-tables、text-report 等模块，负责把状态扫描结果整理成可读的完整诊断报告。

## 关键入口

最外层入口在 `src/cli/program/register.*.ts`。例如 `src/cli/program/register.agent.ts` 注册 `agent` 和 `agents` 命令，然后懒加载 `src/commands/agent-via-gateway.ts`、`src/commands/agents.commands.add.ts`、`src/commands/agents.commands.bind.ts` 等。`src/cli/program/register.status-health-sessions.ts` 注册 `status`、`health`、`sessions`、`tasks`、`flows` 等，再进入 `src/commands/status.ts`、`src/commands/health.ts`、`src/commands/sessions.ts`、`src/commands/tasks.ts`。`src/cli/program/register.maintenance.ts` 注册 `doctor`、`dashboard`、`reset`、`uninstall`，对应进入 `src/commands/doctor.ts`、`dashboard.ts`、`reset.ts`、`uninstall.ts`。

`src/commands/status.ts` 本身只是导出层，真正的 status 命令主入口在 `src/commands/status.command.ts`。它根据 `--all`、`--json`、普通文本模式分流：`--all` 进入 `src/commands/status-all.ts`，JSON 进入 `src/commands/status-json-command.ts`，普通模式进入 `src/commands/status.scan.ts` 后再构建文本报告。

`src/commands/doctor.ts` 是一个薄包装，它导入 `src/flows/doctor-health.ts` 并调用其中的 `doctorCommand`。因此 doctor 的主流程不完全在 `src/commands` 内部，而是在 `src/flows` 中聚合，再回调大量 `doctor-*` 命令模块提供检查和修复能力。

`src/commands/onboard.ts` 是 onboarding 的关键入口，导出 `setupWizardCommand` 和 `onboardCommand`。它先做运行时检查、旧 auth choice 兼容处理、reset scope 校验、非交互风险确认，再分流到 `runNonInteractiveSetup` 或 `runInteractiveSetup`。

`src/commands/channels.ts`、`src/commands/models/list.list-command.ts`、`src/commands/models/set.ts`、`src/commands/agents.commands.*.ts` 是阅读频道、模型、agent 管理命令时的优先入口。

## 主流程位置

典型 CLI 主流程是：`src/cli/program/register.*.ts` 解析参数并创建 action；action 通过 `runCommandWithRuntime` 注入 `defaultRuntime`；然后懒加载 `src/commands` 下的具体 command function；command function 读取配置、解析 secrets、调用 gateway 或本地运行时；最后通过 `runtime.log`、`runtime.error`、`runtime.exit` 或设置 `process.exitCode` 输出结果。

`status` 主流程集中在 `src/commands/status.command.ts`、`src/commands/status.scan.ts`、`src/commands/status.scan-overview.ts`、`src/commands/status-runtime-shared.ts` 和 `src/commands/status-all/*`。其中 `collectStatusScanOverview` 会加载配置、判断是否有已配置频道、收集 OS/Tailscale/update/agent/gateway/channel 状态，再交给报告层渲染。

`doctor` 主流程集中在 `src/flows/doctor-health.ts` 和 `src/flows/doctor-health-contributions.ts`，而 `src/commands/doctor-*.ts` 提供具体检查点，例如 auth、gateway health、plugin registry、state integrity、session locks、security、workspace、skills 等。根据当前片段推断，doctor 采用“flow 编排 + commands 检查模块”的结构。

`models list` 主流程在 `src/commands/models/list.list-command.ts`。它先解析 provider filter，读取模型配置和默认 agent workspace，加载 manifest metadata 与 auth index，然后根据 `--all`、`--local`、provider 过滤决定是否加载 registry，最后由 row sources 和 table formatter 输出模型行。

`channels` 主流程从 `src/commands/channels.ts` 进入对应子命令文件；setup 阶段则常从 `src/flows/channel-setup.ts` 调用 `src/commands/channel-setup/*`，完成频道插件发现、安装确认和 wizard adapter 解析。

## 推荐阅读顺序

1. 先读 `src/cli/program/register.agent.ts`、`src/cli/program/register.status-health-sessions.ts`、`src/cli/program/register.maintenance.ts`、`src/cli/program/register.configure.ts`，理解 CLI 注册层如何懒加载 `src/commands`。
2. 再读薄入口：`src/commands/status.ts`、`src/commands/doctor.ts`、`src/commands/channels.ts`、`src/commands/onboard.ts`，建立命令分流地图。
3. 选择一条主线深入。状态诊断读 `src/commands/status.command.ts`、`src/commands/status.scan-overview.ts`、`src/commands/status-all.ts`；模型管理读 `src/commands/models/list.list-command.ts` 和 `src/commands/models/shared.ts`；频道管理读 `src/commands/channels/add.ts`、`src/commands/channels/status.ts` 和 `src/commands/channel-setup/*`。
4. 最后看测试文件。这个目录下测试非常密集，`*.test.ts` 往往比实现文件更直接展示命令的输入、输出和边界行为。

## 常见误区

不要把 `src/commands` 当成 CLI 注册入口。命令名、选项描述、help 文案和 commander action 大多在 `src/cli/program/register.*.ts`，`src/commands` 主要是 action 背后的实现。

不要把 `doctor.ts` 误读为完整 doctor 实现。它只是代理到 `src/flows/doctor-health.ts`，真正检查点分散在 `src/flows/doctor-*` 和 `src/commands/doctor-*`。

不要认为所有命令都有子目录。这个目录采用混合布局：复杂命令域拆目录，许多命令仍是顶层单文件或顶层文件组，例如 `backup.ts`、`configure.*.ts`、`sessions*.ts`、`status.*.ts`。

不要绕过 `RuntimeEnv` 直接理解输出。命令实现通常通过 `runtime.log`、`runtime.error`、`runtime.exit` 处理输出和退出，这也是测试注入和 CLI 行为统一的关键。

不要把插件/频道/provider 的真实所有权放到这里。`src/commands` 会编排这些能力，但核心插件契约在 `src/plugin-sdk`、插件加载在 `src/plugins`、gateway 协议在 `src/gateway`，命令层应优先被理解为用户操作到这些系统的桥接层。
