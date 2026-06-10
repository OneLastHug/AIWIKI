# 目录：extensions/memory-wiki

## 它负责什么

`extensions/memory-wiki` 是 OpenClaw 内置的 Memory Wiki 插件。它不替代 active memory plugin 的召回、promotion、dreaming 等职责，而是把长期知识整理成可导航的 Markdown vault：包括源材料页、实体页、概念页、综合页、报告页、索引、机器可读 digest，以及可选的 Obsidian CLI 操作入口。

从插件清单 `extensions/memory-wiki/openclaw.plugin.json` 和入口 `extensions/memory-wiki/index.ts` 看，它主要提供四类能力：一是注册 `wiki_status`、`wiki_lint`、`wiki_apply`、`wiki_search`、`wiki_get` 这些 agent tools；二是注册 `openclaw wiki ...` CLI 子命令；三是注册 Gateway RPC，比如 `wiki.status`、`wiki.compile`、`wiki.search`、`wiki.apply`、`wiki.obsidian.open` 等；四是把 wiki 作为 memory corpus supplement 和 prompt supplement 接入 OpenClaw 的 memory 上下文。

它的默认工作模式是 `isolated`，使用自己的 vault。另有 `bridge` 模式从 active memory plugin 的公开 artifacts 读取内容，以及 `unsafe-local` 模式读取本机私有路径；后者从命名和 README 说明看是显式实验性逃生口，不应视为常规集成方式。

## 直接子目录地图

`extensions/memory-wiki/src` 是插件的主要实现目录。这里集中放置配置解析、vault 初始化、导入、编译、查询、工具、CLI、Gateway、Obsidian 集成、bridge/unsafe-local 同步、Markdown 解析渲染、健康检查和测试辅助等逻辑。概览阅读时应把它当成“运行时核心”来看，而不是逐个文件孤立理解。

`extensions/memory-wiki/skills` 是插件随包暴露的 agent skill 目录，目前包含 `obsidian-vault-maintainer` 和 `wiki-maintainer` 两个技能。根据当前片段推断，它们是给 agent 在 wiki 或 Obsidian vault 维护场景中使用的操作指南，插件通过 `openclaw.plugin.json` 的 `skills` 字段暴露它们。

根层文件也很关键。`extensions/memory-wiki/index.ts` 是完整插件入口；`extensions/memory-wiki/cli-metadata.ts` 是轻量 CLI metadata 入口；`extensions/memory-wiki/setup-api.ts`、`extensions/memory-wiki/contract-api.ts`、`extensions/memory-wiki/doctor-contract-api.ts` 负责配置迁移和 doctor/setup 合约；`extensions/memory-wiki/api.ts` 是插件本地使用的 SDK barrel；`extensions/memory-wiki/README.md` 是功能和操作面概览；`extensions/memory-wiki/package.json` 声明包名、依赖、插件入口和 peer contract。

## 关键入口

插件运行入口是 `extensions/memory-wiki/index.ts`。这里调用 `definePluginEntry` 定义 `memory-wiki`，读取 `resolveMemoryWikiConfig` 后依次注册 memory prompt supplement、memory corpus supplement、Gateway methods、agent tools 和 CLI。理解这个文件可以快速建立“OpenClaw 如何发现并启用插件”的视角。

配置入口是 `extensions/memory-wiki/src/config.ts`。它定义 `vaultMode`、`vault.renderMode`、`obsidian`、`bridge`、`unsafeLocal`、`ingest`、`search`、`context`、`render` 等配置结构、默认值和解析规则。`openclaw.plugin.json` 中的 `configSchema` 是控制面可见的配置描述，而 `src/config.ts` 是运行时实际解析与补默认值的位置。

CLI 入口是 `extensions/memory-wiki/src/cli.ts`，并由 `extensions/memory-wiki/index.ts` 和 `extensions/memory-wiki/cli-metadata.ts` 间接注册。它覆盖 `status`、`doctor`、`init`、`ingest`、`compile`、`lint`、`search`、`get`、`apply`、`bridge import`、`unsafe-local import`、`chatgpt import/rollback`、`obsidian ...` 等命令面。

Gateway 入口是 `extensions/memory-wiki/src/gateway.ts`。它把本地能力映射成 RPC 方法，并区分 `operator.read`、`operator.write`、`operator.admin` 等 scope。UI 或其他控制面如果不直接跑 CLI，大概率会走这里。

Agent tool 入口是 `extensions/memory-wiki/src/tool.ts`。它定义工具 schema 和执行逻辑：`wiki_search`、`wiki_get` 负责读，`wiki_apply` 负责结构化写入 synthesis 或 metadata，`wiki_lint` 和 `wiki_status` 负责健康检查与摘要输出。

## 主流程位置

初始化 vault 的主流程在 `extensions/memory-wiki/src/vault.ts`。它创建 `entities`、`concepts`、`syntheses`、`sources`、`reports`、`_attachments`、`_views`、`.openclaw-wiki` 等目录，并写入 `AGENTS.md`、`WIKI.md`、`index.md`、`inbox.md`、`.openclaw-wiki/state.json`、`.openclaw-wiki/log.jsonl` 等基础文件。README 中展示的 vault shape 与这里的实现相互印证。

导入本地源文件的流程在 `extensions/memory-wiki/src/ingest.ts`。它读取输入文本、生成 `source.*` page id，将内容写成 `sources/*.md`，追加 wiki log，然后触发 `compileMemoryWikiVault` 更新索引和 digest。

编译流程在 `extensions/memory-wiki/src/compile.ts`。它读取各类 wiki Markdown 页面，生成或刷新索引、相关页块、报告 dashboard，并输出 `.openclaw-wiki/cache/agent-digest.json` 和 `.openclaw-wiki/cache/claims.jsonl`。这两个 cache 是 agent/runtime 更稳定的机器读取面，Markdown 页面则偏向人类可读视图。

查询流程在 `extensions/memory-wiki/src/query.ts`。它扫描 `entities`、`concepts`、`sources`、`syntheses`、`reports`，解析 Markdown frontmatter 和正文，并支持本地 wiki 搜索、共享 memory 搜索、`wiki`/`memory`/`all` corpus 选择，以及 `find-person`、`route-question`、`source-evidence`、`raw-claim` 等搜索模式。

结构化写入流程在 `extensions/memory-wiki/src/apply.ts`。`wiki_apply` 不鼓励任意 Markdown 手术，而是通过 `create_synthesis` 和 `update_metadata` 两类 mutation 写 synthesis 或更新页面 metadata，并保留 human note block、managed generated block，再触发编译刷新。

bridge 同步流程在 `extensions/memory-wiki/src/bridge.ts` 和 `extensions/memory-wiki/src/source-sync.ts`。`source-sync.ts` 根据 `vaultMode` 分发到 bridge 或 unsafe-local；bridge 通过 memory host 的公开 artifact seam 读取 daily note、dream report、memory root、event log 等，再渲染成 `sources` 下的导入页。

Obsidian 集成在 `extensions/memory-wiki/src/obsidian.ts`，主要是探测 `obsidian` CLI，并执行 `search`、`open`、`command`、`daily`。它不是 wiki 的必需依赖，而是可选的人类 vault 工作流。

## 推荐阅读顺序

第一步读 `extensions/memory-wiki/README.md`，先建立插件目标、vault shape、CLI、agent tools、Gateway RPC 和模式差异的整体印象。

第二步读 `extensions/memory-wiki/openclaw.plugin.json` 和 `extensions/memory-wiki/package.json`，确认插件如何被发现、有哪些 contracts、有哪些配置项、哪些技能会被暴露。

第三步读 `extensions/memory-wiki/index.ts`，把注册链路串起来：配置解析之后，工具、CLI、Gateway、prompt supplement、corpus supplement 分别挂到 OpenClaw 插件 API 上。

第四步读 `extensions/memory-wiki/src/config.ts`、`extensions/memory-wiki/src/vault.ts`、`extensions/memory-wiki/src/compile.ts`。这三处分别回答“配置是什么”“磁盘结构是什么”“最终编译产物是什么”。

第五步按使用场景分支阅读：CLI 用户看 `extensions/memory-wiki/src/cli.ts`；UI/Gateway 调用看 `extensions/memory-wiki/src/gateway.ts`；agent tool 行为看 `extensions/memory-wiki/src/tool.ts`；搜索和召回看 `extensions/memory-wiki/src/query.ts`、`extensions/memory-wiki/src/corpus-supplement.ts`、`extensions/memory-wiki/src/prompt-section.ts`。

第六步再看导入与集成：本地文件导入读 `extensions/memory-wiki/src/ingest.ts`；active memory 公开 artifact 同步读 `extensions/memory-wiki/src/bridge.ts`、`extensions/memory-wiki/src/source-sync.ts`；Obsidian 相关读 `extensions/memory-wiki/src/obsidian.ts`。

## 常见误区

不要把 `memory-wiki` 理解成 active memory plugin 本身。README 明确区分：active memory plugin 仍负责 recall、promotion、dreaming；`memory-wiki` 负责把长期知识编译成可维护的 wiki vault，并提供搜索、读取、lint、apply 和 digest。

不要直接把 Markdown 页面当成唯一机器接口。根据 `README.md`、`src/vault.ts`、`src/compile.ts`，Markdown 是人类视图，稳定机器视图主要是 `.openclaw-wiki/cache/agent-digest.json` 和 `.openclaw-wiki/cache/claims.jsonl`。

不要忽略 managed block 与 human block 的边界。`src/apply.ts`、`src/vault.ts` 和 `src/compile.ts` 都围绕 managed Markdown block、human notes block 做保护，说明插件生成内容和人工笔记有明确边界。

不要把 `bridge` 当成对 memory-core 私有实现的直接依赖。`src/bridge.ts` 使用的是 memory host 公开 artifact 能力；真正读取私有本机路径的是 `unsafe-local`，而 README 已标注它是 experimental、non-portable。

不要只看 `src/cli.ts` 就判断全部能力。CLI、Gateway、agent tools 共用不少底层模块，但暴露面不同；例如 Gateway 还包含 `wiki.importRuns`、`wiki.importInsights`、`wiki.palace` 这类控制面读取方法，agent tools 则更强调模型可调用的搜索、读取和结构化写入。

不要把 `skills` 目录当成运行时代码。它更像插件随包携带的 agent 操作说明；真正的运行注册、磁盘读写、编译和查询逻辑仍在根入口与 `src` 目录。
