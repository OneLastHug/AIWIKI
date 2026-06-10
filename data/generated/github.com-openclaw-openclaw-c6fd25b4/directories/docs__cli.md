# 目录：docs/cli

## 它负责什么

`docs/cli` 是 OpenClaw 命令行工具 `openclaw` 的参考文档目录，核心作用是把“怎么启动、怎么配置、怎么交互、怎么运维、怎么排障”拆成一组按命令组织的页面。根据当前片段推断，这里不是讲设计理念的总览目录，而是面向实际使用者的命令索引层：先用 `index.md` 把全量命令分组，再把每个常用子命令放到独立页面里说明参数、示例和相关命令。

它覆盖的范围很广，但主轴很清晰：首次安装和引导、已有环境的配置调整、消息和代理相关操作、网关与会话状态、模型与推理、插件与安全、审批与沙箱、以及日志和健康检查。换句话说，这个目录就是 `openclaw` CLI 的地图。

## 直接子目录地图

这里没有更深一层的子目录，`docs/cli` 的直接内容主要是一组命令页和一个总索引页。按功能看，可以粗分成几块：

- 总入口与导航：`index.md`
- 初始化与引导：`setup.md`、`onboard.md`、`configure.md`、`config.md`、`completion.md`、`doctor.md`、`dashboard.md`
- 账号、通道、通信：`channels.md`、`message.md`、`agent.md`、`agents.md`、`acp.md`、`mcp.md`、`sessions.md`
- 网关与运行态：`gateway.md`、`daemon.md`、`logs.md`、`status.md`、`health.md`、`system.md`
- 模型与能力：`models.md`、`infer.md`、`memory.md`、`commitments.md`、`wiki.md`
- 组织与发现：`directory.md`、`nodes.md`、`node.md`、`devices.md`、`dns.md`
- 安全与控制：`approvals.md`、`sandbox.md`、`security.md`、`secrets.md`、`proxy.md`
- 自动化与扩展：`cron.md`、`tasks.md`、`hooks.md`、`webhooks.md`、`plugins.md`、`skills.md`
- 其它辅助页：`browser.md`、`qr.md`、`path.md`、`reset.md`、`uninstall.md`、`update.md`、`voicecall.md`、`meeting-notes.md` 等

如果只看目录角色，不必把每个叶子都展开理解；这些文件本质上是围绕命令树做的分组说明。

## 关键入口

最关键的入口是 `index.md`。它的作用不是单独解释某一个命令，而是给整个 CLI 提供一张总目录：命令分组、全局标志、输出模式、完整命令树都集中在这里。对于不知道该找哪个命令的人，先读它最省时间。

第二层入口是几个“主干命令页”：

- `setup.md`：初始化本地配置和工作区
- `onboard.md`：完整的新手引导流程
- `configure.md`：对已有安装做局部配置
- `message.md`：消息与频道相关的主交互入口
- `gateway.md`：网关运行、探测、安装、启动与重启
- `plugins.md`：插件的安装、启用、停用、诊断与市场
- `doctor.md`：健康检查和修复入口
- `approvals.md`：执行策略与审批控制
- `tui.md`：终端交互界面入口

从文件头和索引表看，这些页面基本覆盖了 `openclaw` 最常被直接调用的命令面。

## 主流程位置

这个目录里的主流程不是按代码调用链写的，而是按用户任务流组织的。最典型的路径是：

1. 初次使用：先看 `index.md`，再进入 `setup.md` 或 `onboard.md`。
2. 后续调整：通过 `configure.md`、`config.md`、`channels.md`、`models.md`、`plugins.md` 完成局部修改。
3. 日常使用：围绕 `message.md`、`agent.md`、`agents.md`、`sessions.md`、`tui.md` 做交互。
4. 运行与监控：通过 `gateway.md`、`status.md`、`health.md`、`logs.md`、`system.md` 查看和维护运行态。
5. 故障处理：优先转到 `doctor.md`、`security.md`、`secrets.md`、`approvals.md`、`sandbox.md`。

如果把它理解成一条流程线，入口通常是 `index.md`，真正承载主流程的则是 `setup.md`、`onboard.md`、`configure.md`、`gateway.md`、`message.md`、`doctor.md` 这几页。`index.md` 负责导航，其他页面负责执行意图。

## 推荐阅读顺序

1. `index.md`：先建立整体命令树。
2. `setup.md`、`onboard.md`、`configure.md`：先搞清楚首次使用、完整引导和后续配置的分工。
3. `gateway.md`、`status.md`、`health.md`、`logs.md`：再看运行态和排障入口。
4. `message.md`、`agent.md`、`agents.md`、`sessions.md`：理解日常交互和会话管理。
5. `models.md`、`infer.md`、`plugins.md`、`approvals.md`、`sandbox.md`：最后补齐能力、扩展与安全控制面。

如果只想建立目录地图，读到第 2 步通常就够了；后面的步骤是为了把“命令分类”变成“能在实际场景里找到入口”。

## 常见误区

- 把 `docs/cli/index.md` 当成某个单独命令的说明。它其实是总索引，不是某个动作的完整手册。
- 只看 `setup.md` 就以为覆盖了所有初始化流程。实际上 `onboard.md`、`configure.md`、`config.md` 各自承担不同层次的配置任务。
- 把 `gateway.md`、`daemon.md`、`system.md`、`status.md` 混为一类。它们都和运行态有关，但关注点不同：有的是服务生命周期，有的是状态查询，有的是系统层事件。
- 只盯着主命令，不看索引页里的别名和分组。像 `capability`、`exec-policy`、`chat`/`terminal` 这类别名，往往决定你该读哪个页面。
- 以为这里有复杂子目录结构。根据当前片段推断，`docs/cli` 的组织方式主要是“平铺页面 + 索引分组”，而不是“多层目录树”。
