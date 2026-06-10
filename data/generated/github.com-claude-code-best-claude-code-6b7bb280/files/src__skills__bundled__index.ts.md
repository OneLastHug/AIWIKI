# 文件：src/skills/bundled/index.ts

## 一句话定位
这是 CLI 内置技能的总入口，负责在启动阶段把一批“随程序一起发布”的 bundled skills 逐个注册到全局技能表里，让后续命令解析、模型调用和技能触发都能看见它们。

## 它暴露/定义了什么
这个文件对外只暴露一个核心函数：`initBundledSkills(): void`。它本身不定义技能内容，也不保存业务状态，职责只是做初始化编排。  
从实现看，它静态导入了一组具体技能模块的注册函数，如 `registerUpdateConfigSkill`、`registerKeybindingsSkill`、`registerVerifySkill`、`registerDebugSkill`、`registerBatchSkill`、`registerCronListSkill` 等；另外还通过 `feature()` 和 `shouldAutoEnableClaudeInChrome()` 按条件加载可选技能。

## 谁调用它
根据当前片段可确认，`src/main.tsx` 在启动流程中会调用 `initBundledSkills()`，位置在主 CLI 初始化阶段，属于应用启动而不是某个子命令的临时执行。  
也就是说，这个文件不是给外部直接手动调用的业务 API，而是 `src/main.tsx` 组织整体运行环境时的一环。

## 它调用谁
它主要调用两类东西：

1. 各技能模块的注册入口：例如 `./batch.js`、`./debug.js`、`./loop.js`、`./verify.js`、`./updateConfig.js` 等导出的 `register...Skill()`。
2. 条件加载的技能模块：在 `feature('REVIEW_ARTIFACT')`、`feature('AGENT_TRIGGERS_REMOTE')`、`feature('BUILDING_CLAUDE_APPS')`、`feature('RUN_SKILL_GENERATOR')` 为真时，用 `require()` 再拉入对应模块并执行注册函数；另外 `shouldAutoEnableClaudeInChrome()` 为真时会注册 Claude in Chrome 相关技能。

这些被调用的注册函数最终都会走到 `src/skills/bundledSkills.ts` 里的 `registerBundledSkill()`，把技能定义写入全局 bundled skills registry。根据当前片段推断，这一层结构是“总入口 -> 各技能入口 -> 统一注册器”。

## 核心流程
它的流程很直接：

先无条件注册基础技能，保证核心能力始终可用；再根据 feature flag 决定是否加载某些可选技能；最后再看环境/配置是否自动启用 Claude in Chrome。  
这个顺序很重要，因为它决定了哪些技能在进程启动后一定存在，哪些只在特定构建或运行条件下出现。文件里使用 `require()` 而不是静态 import，也说明这些模块是刻意做成条件加载，以减少默认路径的耦合和启动期负担。

## 关键函数的高层作用
`initBundledSkills()` 是唯一核心函数，作用就是“批量注册 bundled skills”。它不是技能执行器，也不是路由器，而是一个启动编排器。  
其余 `register...Skill()` 函数都只是具体技能的入口包装，每个函数只负责把自己的技能描述、提示词生成逻辑、可用工具集和元数据交给 `registerBundledSkill()`。  
如果看 `src/skills/bundledSkills.ts`，可以更清楚地看到注册器会把技能包装成统一的 `Command` 结构，并放进内部 registry。

## 修改风险
改这个文件的风险主要有四类：

1. 启动可用性风险：删错、改错某个注册调用，会导致对应技能从全局消失，甚至让主流程启动时报错。
2. 构建/运行差异风险：这里混用了静态 import 和条件 `require()`，如果改成不兼容 Bun 构建语义的写法，可能影响打包或 tree shaking。
3. 功能开关风险：`feature()` 控制的技能只在特定构建/环境下出现，错误的 flag 可能让功能误开或误关。
4. 语义回归风险：某些技能注册顺序和自动启用逻辑可能依赖外部环境，特别是 `shouldAutoEnableClaudeInChrome()` 这类条件，一旦改动，用户看到的技能集合会发生变化。

如果要扩展这里，最稳妥的方式是新增一个独立的 `registerXXXSkill()` 文件，再在 `initBundledSkills()` 里显式接入，并同步检查 `src/skills/bundledSkills.ts` 的注册结构是否需要对应字段。
