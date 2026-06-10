# 子系统：src/plugins/compat

## 解决什么问题

`src/plugins/compat` 负责维护“插件兼容性登记表”。它把历史兼容、弃用中的 API、配置键、SDK 子路径、运行时别名等行为，统一用结构化记录描述出来，供注册表、状态诊断、边界报告和测试校验使用。根据当前片段推断，这里不是插件执行逻辑本身，而是一个面向迁移和治理的元数据层：它告诉系统哪些旧能力仍可识别、哪些已经进入弃用窗口、替代方案是什么、相关文档和测试在哪里。

它的价值在于把“兼容性”从散落的条件分支里抽出来，集中成可枚举、可查询、可审计的数据源。这样上层可以稳定地产生诊断信息、构建迁移提示，并对旧入口做一致的保留或下线判断。

## 相关目录和文件

核心文件只有三个：`src/plugins/compat/types.ts` 定义兼容记录的数据结构；`src/plugins/compat/registry.ts` 维护完整记录表和查询函数；`src/plugins/compat/registry.test.ts` 验证代码唯一性、弃用窗口、可操作性和外部表面的一致性。

这个目录的直接消费者分布在插件边界周围：`src/plugins/registry.ts` 会读取特定兼容项，例如 `legacy-deactivate-hook-alias`；`src/plugins/installed-plugin-index-policy.ts` 会把兼容记录转成索引策略数据；`scripts/plugin-boundary-report.ts` 会筛出 `deprecated` 记录生成边界报告。测试侧还会回连到 `src/plugins/status.test.ts`、`src/plugins/contracts/*`、`src/plugins/provider-runtime.test.ts` 等更广的契约测试。

## 核心对象

最重要的类型是 `PluginCompatRecord`。它包含 `code`、`status`、`owner`、`introduced`、`deprecated`、`warningStarts`、`removeAfter`、`replacement`、`docsPath`、`surfaces`、`diagnostics`、`tests`、`releaseNote` 等字段。它把一个兼容点的生命周期、归属、影响面和验证证据都装进同一条记录里。

`PluginCompatStatus` 只有四种值：`active`、`deprecated`、`removal-pending`、`removed`。`PluginCompatOwner` 则把责任归到 `sdk`、`provider`、`channel`、`setup`、`config`、`core`、`plugin-execution`、`agent-runtime` 等边界上。`registry.ts` 里的 `PLUGIN_COMPAT_RECORDS` 是唯一事实源；`PluginCompatCode`、`KnownPluginCompatRecord` 以及 `pluginCompatRecordByCode` 都是围绕这张表派生出来的读取面。

## 运行流程

运行时并没有复杂流程，核心是“查表”。调用方通常先通过 `listPluginCompatRecords()` 拿到全量记录，再按状态、owner 或 surface 过滤；需要单点查询时用 `getPluginCompatRecord(code)`；需要判断任意字符串是否属于登记表时用 `isPluginCompatCode(code)`；需要拿出所有已弃用项时用 `listDeprecatedPluginCompatRecords()`。

从记录内容看，系统会把兼容表用于三类工作：一是状态诊断，比如提示某个旧 hook、旧 SDK 子路径仍被识别；二是迁移提示，比如 `replacement` 指明新入口；三是审计和边界报告，比如 `scripts/plugin-boundary-report.ts` 只关心 `deprecated` 项。测试还会校验弃用记录必须带日期窗和替代方案，保证它不是“空的提醒”。

## 上下游依赖

上游依赖主要是插件边界和契约语义：`src/plugins/compat` 依赖插件 SDK、配置迁移、provider/channel/agent-runtime 等模块已经提供稳定的可识别 surface。换句话说，这里不发明规则，只登记已经存在或正在退场的契约。

下游依赖更明显。`src/plugins/registry.ts` 会据此处理具体旧别名；`src/plugins/installed-plugin-index-policy.ts` 会把记录投喂给索引策略；`scripts/plugin-boundary-report.ts` 会生成对外的边界视图；`src/plugins/compat/registry.test.ts` 负责防止记录失控。结合 `src/plugins/AGENTS.md` 可知，这个目录处在插件控制面边界上，要求保持轻量、可枚举、避免把运行时分支塞回核心路径。

## 修改时最容易踩的坑

第一，不要把它改成“散落的兼容开关集合”。这里的正确形态是集中登记，不是把兼容逻辑埋进各个调用点。

第二，`deprecated` 记录必须保持完整窗口信息。当前测试会检查 `deprecated`、`warningStarts`、`removeAfter` 都是日期格式，而且 `removeAfter` 不能离 `warningStarts` 太远。漏字段会直接破坏迁移节奏。

第三，`code` 必须唯一。`registry.test.ts` 明确把唯一性和查找安全当作硬约束。

第四，`surfaces`、`diagnostics`、`tests` 不是装饰字段，而是后续报告、诊断和验证的输入。改记录时如果不同步更新这些字段，会让文档、告警和测试引用脱节。

第五，新增或改动兼容项时要考虑 owner 边界。比如 SDK、provider、channel、config 的兼容语义属于不同责任域，不能混写成笼统的“插件兼容”。

## 推荐阅读顺序

先看 `src/plugins/compat/types.ts`，理解记录结构；再看 `src/plugins/compat/registry.ts`，掌握完整记录表和查询 API；然后看 `src/plugins/compat/registry.test.ts`，理解它被如何约束；最后顺着 `src/plugins/registry.ts`、`src/plugins/installed-plugin-index-policy.ts`、`scripts/plugin-boundary-report.ts` 看它在真实调用链里怎么被消费。这样能先建立“这是一张兼容性事实表”的整体认知，再去看具体条目会更稳。
