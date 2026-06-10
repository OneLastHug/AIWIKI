# 子系统：src/agents/skills

## 解决什么问题

`src/agents/skills` 负责把分散在工作区、用户目录、OpenClaw 托管目录、内置包和插件清单里的 `SKILL.md` 统一发现、校验、过滤，并转换成 agent 运行时可消费的技能快照。这里的“技能”不是工具本身，而是一段带 frontmatter 的 Markdown 能力说明，可能附带调用策略、依赖要求、环境变量、安装提示和命令入口。它解决的核心问题是：不同来源的技能如何以确定顺序进入 prompt，如何按配置和 agent 范围收敛可见性，如何在文件变化后刷新快照，以及如何把插件声明的技能安全发布到统一目录。

根据当前片段推断，这个目录是 agent prompt 和技能命令系统之间的中间层：它不负责执行模型，也不负责具体插件业务逻辑，而是提供“技能目录解析、运行资格判断、快照构建、刷新通知、命令规格生成”等基础能力。依据是 `src/agents/agent-command.ts`、`src/auto-reply/reply/commands-system-prompt.ts`、`src/agents/pi-embedded-runner/skills-runtime.ts` 都通过 `buildWorkspaceSkillSnapshot`、`loadWorkspaceSkillEntries` 或 `SkillSnapshot` 消费这里的结果。

## 相关目录和文件

入口聚合位于 `src/agents/skills.ts`，它向外暴露 `src/agents/skills/workspace.ts`、`src/agents/skills/types.ts` 等模块的主要能力。真正的子系统核心在 `src/agents/skills/workspace.ts`，负责加载各来源技能、合并、过滤并生成 `SkillSnapshot`。`src/agents/skills/local-loader.ts` 只处理本地目录中的 `SKILL.md` 读取和 frontmatter 解析，使用 `src/infra/boundary-file-read.js` 做根目录边界保护。`src/agents/skills/config.ts` 处理配置开关、内置技能 allowlist、运行时依赖和平台资格判断。

刷新和热更新由 `src/agents/skills/refresh.ts`、`src/agents/skills/refresh-state.ts` 管理，底层用 `chokidar` 监听技能根目录，并用版本号通知快照重建。插件技能由 `src/agents/skills/plugin-skills.ts` 解析，它读取插件元数据快照、插件激活状态和 slot 决策，再把合法技能目录发布到用户配置目录下的 plugin-skills 区域。`src/agents/skills/filter.ts`、`src/agents/skills/agent-filter.ts` 负责 agent 级技能过滤；`src/agents/skills/snapshot-hydration.ts` 负责把持久化会话中的轻量快照重新补回运行时 `resolvedSkills`；`src/agents/skills/env-overrides.ts` 和 `env-overrides.runtime.ts` 处理技能相关环境变量覆盖。

邻近上游包括 `src/config/types.openclaw.js`、`src/config/types.skills.js`、`src/plugins/plugin-metadata-snapshot.js`、`src/plugins/config-policy.js`、`src/shared/config-eval.js`。下游主要是 `src/agents/agent-command.ts`、`src/agents/pi-embedded-runner/*`、`src/auto-reply/*`、`src/commands/doctor-skills.ts`、`ui/src/ui/controllers/skills.ts`。

## 核心对象

`Skill` 定义在 `src/agents/skills/skill-contract.ts`，它扩展上游包 `@earendil-works/pi-coding-agent` 的 canonical skill，并保留 legacy `source` 字段。`createSyntheticSourceInfo` 用来给本地加载的技能补齐 `sourceInfo`，包含路径、来源、作用域和 baseDir。

`SkillEntry` 是子系统内部最常用的聚合对象，包含 `skill`、`frontmatter`、可选 `metadata`、`invocation`、`exposure`、同步来源目录等信息。`OpenClawSkillMetadata` 表示 frontmatter 或配置中与 OpenClaw 相关的扩展字段，例如 `always`、`skillKey`、`primaryEnv`、`requires`、`install`。`SkillInvocationPolicy` 描述技能是否允许用户调用、是否禁用模型调用。`SkillExposure` 则区分是否进入运行时注册表、是否进入 available skills prompt、是否可由用户调用。

`SkillSnapshot` 是传给 agent 运行时和会话系统的结果对象，包含最终 prompt、技能摘要列表、可选 `skillFilter`、运行时 `resolvedSkills` 和版本号。注释显示 `resolvedSkills` 是运行时字段，持久化会话会剥离它，恢复时通过 `hydrateResolvedSkills` 重新扫描工作区补齐。

## 运行流程

典型流程从下游调用 `buildWorkspaceSkillSnapshot(workspaceDir, opts)` 开始。它先通过 `loadSkillEntries` 汇总技能来源：工作区 `skills`、项目 `.agents/skills`、个人 `~/.agents/skills`、OpenClaw 配置目录下的托管技能、内置 bundled skills、配置 `skills.load.extraDirs`，以及 `resolvePluginSkillDirs` 返回的插件技能目录。不同来源会带上 source 标记，用于诊断、优先级和遥测。

本地加载走 `loadSkillsFromDirSafe`：先判断根目录自己是否就是一个技能目录，即存在直接的 `SKILL.md`；否则扫描一级子目录，每个子目录如果有 `SKILL.md` 就作为一个技能。读取时会解析 frontmatter，要求至少有 `name` 和 `description`，并建立 `filePath`、`baseDir`、`sourceInfo`。解析失败、文件越界、缺少必要字段时返回空结果，而不是抛出给上游。

合并后进入过滤阶段。`shouldIncludeSkill` 会检查 `config.skills.entries[skillKey].enabled`、`skills.allowBundled`、平台要求、二进制依赖、环境变量、配置路径开关等。agent 维度再由 `resolveEffectiveAgentSkillFilter` 处理：具体 agent 的 `skills` 明确存在时优先，否则退回 `agents.defaults.skills`。最后快照构建会生成 prompt 和技能摘要，并可按 `skillsLimits.maxSkillsPromptChars` 等限制控制 prompt 规模。

文件变化由 `ensureSkillsWatcher` 建立监听。它为每个真实技能根目录维护共享 watcher，同一目录可被多个 workspace 订阅，避免 agent 数量增加时文件描述符线性膨胀。监听只关注 `SKILL.md` 和目录变化，忽略 `.git`、`node_modules`、`dist`、缓存和虚拟环境。变更经过 debounce 后调用 `bumpSkillsSnapshotVersion`，下游通过版本号判断是否需要重建。

## 上下游依赖

上游配置来自 `OpenClawConfig`，其中 `skills.load` 控制额外目录、watch 开关、debounce 和符号链接策略；`skills.entries` 控制单个技能启停、环境变量和 API key；`agents.list` 与 `agents.defaults` 控制 agent 级技能过滤。运行资格判断依赖 `src/shared/config-eval.js` 的 `evaluateRuntimeEligibility`、`hasBinary`、`resolveRuntimePlatform` 等函数。

插件路径依赖 `src/plugins/plugin-metadata-snapshot.js` 生成的 manifest registry，也依赖 `src/plugins/config-policy.js` 判断插件是否激活、memory slot 是否选中，以及 `src/acp/runtime/availability.js` 判断 `acpx` 技能是否能挂载。安全边界依赖 `src/security/scan-paths.js`，插件声明的技能路径必须在插件 root 内，且真实路径存在。

下游消费分三类。第一类是 agent 运行时，如 `src/agents/agent-command.ts` 和 `src/agents/pi-embedded-runner/skills-runtime.ts`，它们用快照给模型注入技能说明。第二类是命令和自动回复，如 `src/auto-reply/skill-commands.ts`、`src/auto-reply/reply/commands-system-prompt.ts`，它们使用技能命令规格生成可调用命令。第三类是状态和管理界面，如 `src/commands/doctor-skills.ts`、`src/commands/status-all/report-data.ts`、`ui/src/ui/controllers/skills.ts`，它们展示技能安装、可用性和诊断信息。

## 修改时最容易踩的坑

最容易出错的是来源优先级和过滤语义。`workspace.ts` 不是简单文件扫描器，它同时承载多个来源的合并规则、内置技能 allowlist、agent 默认技能过滤和插件技能生成；调整加载顺序可能改变用户实际看到的 prompt。

第二个风险是运行时热路径。`src/agents/AGENTS.md` 明确提醒 agent 测试常被导入成本拖慢，技能相关逻辑如果引入插件运行时、channel runtime 或 provider bootstrap，会让测试和请求路径变重。修改时应优先使用轻量元数据、纯函数和注入点。

第三个风险是安全边界。`local-loader.ts` 使用根目录 realpath 和 `openRootFileSync` 防止越界读取；`plugin-skills.ts` 要求插件技能路径不能逃出插件 root。不要为了兼容奇怪路径绕过这些检查。

第四个风险是会话持久化。`resolvedSkills` 不应被当作长期存储字段；如果改 `SkillSnapshot`，要同时检查 `src/config/sessions/store.skills-stripping.test.ts` 和 `snapshot-hydration.ts` 的约定。

第五个风险是 watcher 扩散。`refresh.ts` 特意按目录共享 watcher，并用 workspace 订阅集合分发版本变化。如果新增监听目标，要保持稳定排序、去重和 teardown，否则容易造成重复刷新或文件描述符泄漏。

## 推荐阅读顺序

1. 先读 `src/agents/skills/types.ts` 和 `src/agents/skills/skill-contract.ts`，理解 `Skill`、`SkillEntry`、`SkillSnapshot` 的数据形状。
2. 再读 `src/agents/skills/workspace.ts`，把加载来源、合并顺序、过滤和快照构建串起来。
3. 接着读 `src/agents/skills/local-loader.ts`、`src/agents/skills/frontmatter.ts`，理解一个 `SKILL.md` 如何变成内存对象。
4. 然后读 `src/agents/skills/config.ts`、`src/agents/skills/agent-filter.ts`、`src/agents/skills/filter.ts`，掌握配置和 agent 范围如何限制技能。
5. 再读 `src/agents/skills/plugin-skills.ts`，理解插件 manifest 如何进入技能系统，以及路径安全如何保证。
6. 最后读 `src/agents/skills/refresh.ts`、`src/agents/skills/snapshot-hydration.ts`，补齐热更新和会话恢复流程；下游可选择 `src/agents/agent-command.ts` 或 `src/auto-reply/reply/commands-system-prompt.ts` 看实际消费点。
