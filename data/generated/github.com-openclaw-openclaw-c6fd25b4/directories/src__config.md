# 目录：src/config

## 它负责什么

`src/config` 是 OpenClaw 的配置中枢，负责把用户可编辑的配置文件、运行期默认值、插件/频道元数据、环境变量、路径规则、校验规则和运行期快照组合成核心系统可消费的 `OpenClawConfig`。它不是单纯的类型目录，也不是只负责读写 JSON；这里同时承担“配置契约定义”“配置加载与恢复”“配置写入与审计”“运行期投影”“插件/频道配置接入”“会话存储配置”这些职责。

从当前片段看，核心外部入口集中在 `src/config/config.ts`。该文件大量 re-export `io.ts`、`mutate.ts`、`runtime-snapshot.ts`、`paths.ts`、`recovery-policy.ts`、`runtime-overrides.ts`、`types.ts`、`validation.ts`，说明调用方通常通过 `src/config/config.ts` 获取配置读写、快照、路径、校验和类型能力。实际重逻辑分散在更细的模块里：`io.ts` 处理配置文件 I/O 和运行期加载，`validation.ts` 做结构与业务校验，`zod-schema*.ts` 定义输入 schema，`schema.ts` 生成面向 UI/Gateway 的配置 schema，`types*.ts` 拆分配置类型，`sessions/` 维护会话存储相关配置与状态文件。

## 直接子目录地图

`src/config` 的直接子目录只有一个：`src/config/sessions`。

`src/config/sessions` 负责会话层的持久化与维护，包括 session key 解析、主会话、会话 store 读写、transcript、delivery info、artifact、reset、cleanup、磁盘预算、文件轮转等。根层还有一个聚合入口 `src/config/sessions.ts`，把 `sessions/` 下的主要能力 re-export 给 `src/library.ts`、`src/tui/embedded-backend.ts`、`src/plugins/host-hook-cleanup.ts` 等运行路径使用。

除 `sessions/` 外，`src/config` 根目录是一个大平铺目录。根据文件命名可分为几组：配置读写与恢复如 `io.ts`、`io.*.ts`、`mutate.ts`、`recovery-policy.ts`、`backup-rotation.ts`；schema 与校验如 `zod-schema.ts`、`zod-schema.*.ts`、`schema.ts`、`schema.*.ts`、`validation.ts`；类型契约如 `types.ts`、`types.*.ts`；插件/频道配置如 `plugin-auto-enable.*.ts`、`channel-config*.ts`、`bundled-channel-config-metadata.generated.ts`；路径与环境如 `paths.ts`、`config-paths.ts`、`env-vars.ts`、`env-substitution.ts`、`includes.ts`；运行期快照与覆盖如 `runtime-snapshot.ts`、`runtime-overrides.ts`。

## 关键入口

最重要的入口是 `src/config/config.ts`。它导出 `loadConfig`、`getRuntimeConfig`、`readConfigFileSnapshot`、`writeConfigFile`、`mutateConfigFile`、`validateConfigObject`、`resolveRuntimeConfigCacheKey` 等能力，基本覆盖配置读取、写入、校验、缓存、快照与恢复。

`src/config/types.ts` 是类型聚合入口。它把 `types.openclaw.ts`、`types.models.ts`、`types.plugins.ts`、`types.channels.ts`、`types.secrets.ts`、`types.gateway.ts`、`types.agents.ts` 等领域类型统一导出。注释里明确说类型被拆成聚焦模块以控制文件大小和编辑局部性，因此读类型时不要只看 `types.ts`，它主要是索引。

`src/config/sessions.ts` 是会话配置/状态入口，向外导出 `combined-store-gateway`、`group`、`artifacts`、`metadata`、`main-session`、`paths`、`reset`、`session-key`、`store`、`transcript`、`targets`、`cleanup-service` 等。会话相关调用方通常不直接遍历 `sessions/`，而是从这个聚合入口或具体子模块拿能力。

`src/config/schema.ts` 是配置 schema 的 Gateway/UI 入口。它会把基础配置 schema、敏感字段提示、派生 tags、插件和频道 UI metadata 组合起来，并对插件/频道扩展 schema 做大小预算控制。

## 主流程位置

配置读取主流程在 `src/config/io.ts`。从导入关系能看出它串起 `paths.ts`、`includes.ts`、`env-substitution.ts`、`env-vars.ts`、`materialize.ts`、`validation.ts`、`runtime-snapshot.ts`、`plugin-install-config-migration.ts`、`io.observe-recovery.ts` 等模块。概括起来是：解析配置路径，读取 JSON5，处理 include，替换环境变量，合并/迁移插件安装配置，校验原始对象，物化为运行期配置，再写入或选择运行期快照。

配置写入主流程也在 `io.ts`，但写入准备被拆到 `src/config/io.write-prepare.ts`，实际变更 API 在 `src/config/mutate.ts`。写入会关注 env 引用恢复、unset path、显式设置路径、merge patch、Nix mode 写保护、原子替换、审计记录、备份轮转和 last-known-good 恢复状态。根据当前片段推断，配置写入不是“覆盖整个对象”这么简单，而是尽量保留用户源文件形态和运行期投影之间的差异。

配置校验主流程在 `src/config/validation.ts`，schema 基础来自 `src/config/zod-schema.ts` 和各个 `zod-schema.*.ts`。它不仅做 Zod 结构校验，还结合插件 registry、官方外部插件目录、频道 ID、模型引用、SecretRef 策略、agent 目录重复检测、允许值提示等上下文做业务校验。

会话存储主流程在 `src/config/sessions/store.ts`。它通过 `getRuntimeConfig` 读取当前配置，解析 store path，加载/规范化 session store，执行维护策略、裁剪、磁盘预算、文件轮转，再通过 writer 队列写回。`src/config/sessions/paths.ts`、`session-key.ts`、`store-load.ts`、`store-writer.ts`、`store-maintenance.ts` 是阅读该流程时的关键配套位置。

## 推荐阅读顺序

1. 先读 `src/config/config.ts`，建立公共 API 地图，理解外部调用方主要依赖哪些入口。
2. 再读 `src/config/types.ts` 和 `src/config/types.openclaw.ts`，掌握 `OpenClawConfig` 的类型边界；遇到具体领域再跳到对应 `types.*.ts`。
3. 接着读 `src/config/zod-schema.ts`、`src/config/validation.ts`，理解配置对象如何被接受、拒绝或规范化。
4. 然后读 `src/config/io.ts`，重点看 `loadConfig`、`getRuntimeConfig`、`writeConfigFile` 一类导出函数如何串起路径、include、env、校验、物化和快照。
5. 写配置相关再补 `src/config/mutate.ts`、`src/config/io.write-prepare.ts`、`src/config/runtime-snapshot.ts`。
6. UI/Gateway 配置面板相关读 `src/config/schema.ts`、`src/config/schema.hints.ts`、`src/config/channel-config-metadata.ts`。
7. 会话状态相关最后读 `src/config/sessions.ts`，再进入 `src/config/sessions/store.ts`、`paths.ts`、`session-key.ts`、`transcript.ts`。

## 常见误区

不要把 `src/config` 理解成“静态默认值目录”。默认值只是其中一部分，真正关键的是源配置、运行期配置、插件/频道扩展、环境变量和快照之间的转换边界。

不要绕过 `src/config/config.ts` 直接随意读写配置文件。这里存在 include、env 引用保留、审计、备份、恢复、Nix mode 写保护、插件安装配置迁移等规则，直接写 JSON 容易破坏用户配置契约。

不要认为 `types.ts` 包含完整类型细节。它只是聚合层，具体领域分散在 `types.models.ts`、`types.plugins.ts`、`types.channels.ts`、`types.secrets.ts` 等文件里。

不要把 `sessions/` 当作普通配置 schema 的一部分。它更像运行期会话状态存储子系统，虽然挂在 `src/config` 下，但关注的是 session store、transcript、cleanup、disk budget 和文件轮转。

不要在核心配置里硬编码插件策略。目录里有 `plugin-auto-enable.*.ts`、`channel-config*.ts` 等模块，但根规则强调核心应保持 plugin-agnostic；配置层应通过 manifest、registry、metadata 和 SDK 契约接入插件行为。
