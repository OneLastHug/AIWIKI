# 目录：src/skills/bundled

## 它负责什么
`src/skills/bundled` 存放的是“随 CLI 一起打包、启动时直接注册”的内置 skill。它和用户放在工作区里的 skill 目录不同，不依赖磁盘扫描，也不走插件加载流程，而是在进程启动时通过代码显式注册到全局命令/skill 注册表里。根据当前片段推断，这个目录的定位是：给模型和 CLI 提供一组稳定、预置、可控的能力入口，比如 `verify`、`debug`、`batch`、`loop`、`remember` 这类内部工作流。

这里最重要的不是“文件很多”，而是“加载方式固定”。它把 skill 当成编译期/启动期内置资源处理，所以后续在 `commands.ts` 里获取时，是同步从内存 registry 里取，而不是每次重新读目录。

## 直接子目录地图
这个目录几乎全部是单文件 skill，没有大层级展开。直接子目录只有一个：

- `verify/`
  - `verify/SKILL.md`
  - `verify/examples/`

从结构上看，`verify/` 是少数带有补充文本资源的 bundled skill。其他内容都集中在目录根部的 `.ts` 文件里，说明大多数 bundled skill 更像“注册器 + prompt 生成器”，而不是复杂模块树。

目录根部的主要文件可以粗分为几类：
- 纯注册型 skill：`batch.ts`、`debug.ts`、`loop.ts`、`remember.ts`、`simplify.ts`、`stuck.ts`、`skillify.ts`、`updateConfig.ts`
- 带条件启用的 skill：`claudeApi.ts`、`claudeInChrome.ts`、`cronManage.ts`、`scheduleRemoteAgents.ts`
- 带内容拆分的 skill：`claudeApiContent.ts`、`verifyContent.ts`
- 聚合入口：`index.ts`

## 关键入口
最核心的入口是 `src/skills/bundled/index.ts`。它定义了 `initBundledSkills()`，负责把这个目录下的 skill 逐个注册进去。这里能直接看出这个目录的装配方式：先注册固定能力，再按 feature flag 或环境条件追加特殊能力。

第二个核心点是 `src/skills/bundledSkills.ts`。这个文件不是某个具体 skill，而是 bundled skill 的基础设施：
- 定义 `BundledSkillDefinition`
- 把 skill 转成通用 `Command`
- 维护内存里的 `bundledSkills` registry
- 处理带 `files` 的 skill 的懒提取逻辑
- 提供 `getBundledSkills()` 给上层读取

第三个关键入口是 `src/main.tsx`。它在启动早期调用 `initBundledSkills()`，而且注释已经明确说明要在 `getCommands()` 之前执行，否则并发加载时会因为 registry 还是空的而漏掉 bundled skills。

## 主流程位置
主流程可以按下面这条链路理解：

1. `src/main.tsx` 启动时调用 `initBundledSkills()`
2. `src/skills/bundled/index.ts` 逐个执行各个 `register...Skill()`
3. 每个 skill 文件调用 `registerBundledSkill()`
4. `src/skills/bundledSkills.ts` 把定义转换成 `Command` 并推入内存数组
5. `src/commands.ts` 的 `getSkills()` 再通过 `getBundledSkills()` 取出这些命令，和技能目录、插件技能、builtin plugin skills 一起汇总
6. 后续命令可见性、模型调用权限、UI 展示都基于这个统一的 `Command` 形态继续处理

对带额外引用文件的 skill，流程还会多一步：
- 首次调用时触发 `extractBundledSkillFiles()`
- 把 `files` 写到 `getBundledSkillsRoot()` 下
- 给 prompt 前面补一行 `Base directory for this skill: ...`
- 让模型可以像读普通技能目录一样去 `Read` / `Grep` 这些文件

## 推荐阅读顺序
1. `src/skills/bundled/index.ts`，先看有哪些内置 skill 以及启用条件
2. `src/skills/bundledSkills.ts`，理解注册器、registry、文件提取机制
3. `src/main.tsx` 中 `initBundledSkills()` 的调用位置，确认启动时机
4. `src/commands.ts` 中 `getSkills()` 和 `loadAllCommands()`，看 bundled skills 如何进入最终命令集
5. `src/skills/bundled/verify.ts`、`src/skills/bundled/claudeApi.ts` 这类代表性文件，理解单个 skill 的写法
6. `src/skills/bundled/verify/SKILL.md`，看少数带外部文本资源的 bundled skill 如何组织补充材料

## 常见误区
- 误以为它是“用户可编辑 skill 目录”。不是，这里是编译进 CLI 的内置能力。
- 误以为会被 `getSkillDirCommands()` 自动扫描。不会，bundled skills 走的是内存注册，不是目录扫描。
- 误以为可以在 `getCommands()` 之后再初始化。`main.tsx` 里的注释已经说明，顺序错了会导致并发时拿到空 registry。
- 误以为所有 bundled skill 都有子目录。实际上这里大多是单文件 skill，只有 `verify/` 这类少数例外。
- 误以为 `files` 是静态随包读取的。它们是首次调用时才懒提取到磁盘，属于运行时行为，不是纯静态资源加载。
- 误以为所有 skill 都固定可见。实际上有些 skill 会受 `feature()`、环境检测或 `shouldAutoEnableClaudeInChrome()` 影响，属于条件启用。
