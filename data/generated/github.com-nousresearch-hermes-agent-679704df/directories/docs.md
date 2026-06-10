# 目录：docs

## 它负责什么

`docs` 是仓库根目录下的轻量级工程资料区，不是主要的用户文档站源码。根据当前片段推断，真正面向用户和开发者的 Docusaurus 文档主要在 `website/docs`，而这里的 `docs` 更像是“设计说明、实施计划、安全部署补充、架构规格”的存放处。它承载的内容有三类：一是已经固化成规格的 PDF，例如 `docs/hermes-kanban-v1-spec.pdf`；二是带日期的实施计划，集中在 `docs/plans`；三是安全部署指南，集中在 `docs/security`。

这个目录的文档不是运行时代码入口，也不是自动发现的插件、技能或配置目录。它的价值在于解释某些大型改动为什么这样设计、涉及哪些模块、测试和验证路径在哪里。代码里有若干注释直接引用这些文档，例如 `Dockerfile` 引用 s6-overlay 计划，`hermes_cli/kanban.py`、`hermes_cli/kanban_db.py` 引用 Kanban PDF，因此它也承担“长期架构依据”的角色。

## 直接子目录地图

`docs/plans` 保存按日期命名的工程实施计划。当前片段里有三个文件：`docs/plans/2026-05-02-telegram-dm-user-managed-multisession-topics.md`、`docs/plans/2026-05-07-s6-overlay-dynamic-subagent-gateways.md`、`docs/plans/2026-05-15-acp-zed-edit-approval-diffs.md`。它们都不是普通教程，而是面向实现者的 PR 级计划，包含目标、架构选择、范围边界、任务拆分、测试要求和验证步骤。

`docs/security` 保存安全部署相关的说明。当前只有 `docs/security/network-egress-isolation.md`，主题是 Docker 部署下的网络出口隔离。它从威胁模型出发，解释如何用 Docker 网络和可选代理限制 agent 容器的外部访问能力，防御通过 shell 工具外传数据的提示注入攻击。

根目录下还有 `docs/hermes-kanban-v1-spec.pdf`。根据代码引用，它是 Kanban 功能的完整设计规格，供 `hermes_cli/kanban.py`、`hermes_cli/kanban_db.py` 等实现参考。由于它是 PDF，不适合像 Markdown 一样逐段检索阅读，但从引用位置看，它是 Kanban 子系统的权威设计附件。

## 关键入口

`docs/hermes-kanban-v1-spec.pdf` 是 Kanban 相关资料的入口。代码注释显示，`hermes_cli/kanban.py` 用它解释完整设计背景，`hermes_cli/kanban_db.py` 也把它作为数据库设计或工作流设计的参考。阅读 Kanban 代码前，可以先确认这个 PDF 的范围，再进入 `plugins/kanban`、`hermes_cli/kanban.py`、`hermes_cli/kanban_db.py`。

`docs/plans/2026-05-07-s6-overlay-dynamic-subagent-gateways.md` 是 Docker 内 s6-overlay 监督体系的关键入口。它描述从 `tini` 切换到 s6-overlay、主进程和 dashboard 的监督、动态 per-profile gateway 注册、容器重启后的 profile gateway 恢复等内容。相关代码散布在 `Dockerfile`、`docker/s6-rc.d`、`docker/cont-init.d`、`hermes_cli/service_manager.py`、`hermes_cli/container_boot.py`、`hermes_cli/profiles.py`、`hermes_cli/status.py`、`hermes_cli/doctor.py`、`hermes_cli/gateway.py`。

`docs/plans/2026-05-02-telegram-dm-user-managed-multisession-topics.md` 是 Telegram DM 多会话 topic 模式的入口。它讨论 `message_thread_id`、root DM 作为 system lobby、topic 到 Hermes session lane 的绑定、`/topic` 和 `/new` 行为。相关主线应在 `gateway/platforms/telegram.py`、`gateway/run.py`、`hermes_state.py` 或会话绑定相关存储中查找。

`docs/plans/2026-05-15-acp-zed-edit-approval-diffs.md` 是 ACP/Zed 文件编辑前审批的入口。它关注 `write_file`、`patch` 等文件变更工具在真正落盘前生成 diff，并通过 ACP permission 请求让用户批准或拒绝。相关主线在 `acp_adapter`、`model_tools.py`、文件工具实现和 `tests/acp`。

`docs/security/network-egress-isolation.md` 是安全部署补充入口。它不改核心代码，而是解释 Docker Compose 网络拆分、gateway/dashboard/agent 的网络边界和可选 egress proxy 策略。

## 主流程位置

这个目录本身没有主流程函数，主流程都在仓库其他位置。`docs` 的作用是把“为什么”和“怎么验证”绑定到具体实现。

Kanban 主流程位置根据当前片段可定位到 `hermes_cli/kanban.py` 和 `hermes_cli/kanban_db.py`。前者偏 CLI/功能编排，后者偏数据库与任务状态模型；PDF 是设计依据而不是执行入口。

s6-overlay 主流程分两层：容器启动阶段在 `Dockerfile`、`docker/s6-rc.d`、`docker/cont-init.d`、`docker/main-wrapper.sh` 一类文件；Hermes CLI 对 gateway 服务的生命周期管理在 `hermes_cli/service_manager.py`、`hermes_cli/gateway.py`、`hermes_cli/profiles.py`。计划文档里提到的 profile gateway 恢复逻辑对应 `hermes_cli/container_boot.py`。

Telegram topic 多会话主流程应从消息进入平台适配器开始，即 `gateway/platforms/telegram.py` 接收 Telegram update，再经 `gateway/run.py` 的命令分发和 session 选择进入 agent。会话持久化和检索则关联 `hermes_state.py` 以及 gateway 的 session key 生成逻辑。

ACP/Zed 编辑审批主流程应在工具调用前置拦截层，而不是工具执行后的事件渲染层。计划文档明确指出不要放到 post-execution 的 `acp_adapter/events.py`，而要在 `model_tools.py` 或 ACP session 上下文包装处，在 `write_file`、`patch` 真正执行前计算 proposal、请求 permission、根据结果继续或返回拒绝。

网络出口隔离的主流程不在 Python 代码里，而在部署拓扑：Docker Compose 清除默认 `network_mode: host`，把服务拆到 internal 和 egress 网络，并可通过代理 allowlist 控制外连目标。

## 推荐阅读顺序

第一步先看目录形状：`docs` 根目录、`docs/plans`、`docs/security`。确认它不是 `website/docs`，避免把内部工程资料和站点文档混在一起。

第二步读 `docs/security/network-egress-isolation.md`。它篇幅较短，能快速建立 Hermes Docker 部署的安全边界概念，也能帮助理解为什么 gateway、dashboard、agent 的网络职责要分开。

第三步读 `docs/plans/2026-05-07-s6-overlay-dynamic-subagent-gateways.md`。这是当前 `docs/plans` 中信息量最大且已标注 shipped 的文档，适合用来学习“计划文档如何映射到真实代码”：从 `Dockerfile` 到 `hermes_cli/service_manager.py`，再到 profile 生命周期。

第四步读 `docs/plans/2026-05-02-telegram-dm-user-managed-multisession-topics.md`。它适合理解 gateway 平台适配、会话 lane、命令行为之间的关系。

第五步读 `docs/plans/2026-05-15-acp-zed-edit-approval-diffs.md`。它更偏工具调用安全和 ACP 集成，建议结合 `acp_adapter`、`model_tools.py`、`tests/acp` 阅读。

最后再看 `docs/hermes-kanban-v1-spec.pdf`，并配合 `hermes_cli/kanban.py`、`hermes_cli/kanban_db.py`、`plugins/kanban`。PDF 通常更适合当作专题规格，而不是第一次浏览仓库时的入口。

## 常见误区

不要把根目录 `docs` 当成 Docusaurus 文档源码。项目的站点文档在 `website/docs`，并由 `website/docusaurus.config.ts`、`website/sidebars.ts` 管理；根目录 `docs` 更像内部设计和补充资料。

不要认为 `docs/plans` 里的每个计划都等于当前未完成任务。有的计划已经标注 shipped，例如 s6-overlay 文档，它现在更像实施后的架构记录和决策日志。阅读时应结合代码现状，而不是机械按计划里的每个 task 判断代码一定缺失。

不要把 Markdown 计划当成唯一真实来源。计划会描述目标架构、建议文件和测试路径，但最终实现可能经过 PR 讨论调整。遇到差异时，应以当前代码为准，并把计划作为理解设计意图的依据。

不要忽略这些文档和代码注释之间的关联。`Dockerfile`、`hermes_cli/kanban.py` 等文件已经把 `docs` 中的资料作为背景引用；如果只看代码不看这些资料，容易漏掉容器监督、Kanban 工作流、编辑审批这类跨模块设计的边界条件。

不要在阅读安全文档时只关注 Compose 片段。`network-egress-isolation.md` 的核心不是某个固定配置，而是威胁模型：即使 agent 能执行 shell 命令，也要通过网络边界减少任意外连和数据外传的风险。
