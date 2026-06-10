# 目录：extensions/open-prose

## 它负责什么

`extensions/open-prose` 是 OpenClaw 内置的 bundled plugin，用来把 OpenProse 作为“插件携带的 skill 包”交给 OpenClaw 发现和加载。它本身不是一个复杂运行时代码插件：`package.json` 描述为 `@openclaw/open-prose`，入口是 `./index.ts`，`openclaw.plugin.json` 声明插件 id 为 `open-prose`，并通过 `skills: ["./skills"]` 暴露技能目录。根据当前片段推断，真正的能力主体不在 TypeScript 逻辑里，而在 `skills/prose` 下的一组 Markdown 规范、状态后端说明、编译器说明、示例 `.prose` 程序和写作指导中。

这个目录对 OpenClaw 的意义是：让用户启用 `open-prose` 后获得 `/prose` slash command 和 OpenProse VM 语义。OpenProse 把 `.prose` 文件视为一种面向 AI session 的工作流语言，核心执行方式是让模型按 `prose.md` 中定义的虚拟机规则去解析程序、管理状态、派发 session、汇总输出。插件 README 也说明 bundled plugins 默认关闭，需要在 OpenClaw 配置里启用 `open-prose` 并重启 Gateway。

从边界看，它遵循 `extensions/AGENTS.md` 的插件规则：生产代码只通过 `openclaw/plugin-sdk/*` 暴露入口，不深 import core 内部。这里的 TypeScript 代码非常薄，主要职责是注册插件元数据和 re-export SDK 类型；OpenProse 的“产品内容”主要由技能文件承载。

## 直接子目录地图

`skills` 是唯一直接子目录，是插件向 OpenClaw 暴露技能包的根。`openclaw.plugin.json` 中的 `skills: ["./skills"]` 指向这里，所以 OpenClaw 的技能发现会从这个目录进入。

`skills/prose` 是实际的 OpenProse skill。它包含 `SKILL.md`、`prose.md`、`compiler.md`、`help.md`、`LICENSE`、`alt-borges.md`，以及若干子目录。`SKILL.md` 是技能激活、命令路由和文件位置说明；`prose.md` 是 VM / interpreter 语义；`compiler.md` 是语法验证和编译说明；`help.md` 面向 `prose help` 一类用法。

`skills/prose/examples` 是示例程序集合，包含从基础 hello world、代码审查、调试、重构，到并行执行、pipeline、错误处理、递归语言模型和插件发布工作流等大量 `.prose` 示例。这里还有 `examples/README.md` 和 `examples/roadmap`，用于说明示例分类与路线图。

`skills/prose/guidance` 放写 `.prose` 时的指导资料，包括 `patterns.md`、`antipatterns.md`、`system-prompt.md`。这些文件不是执行必读文档，而是在创作新 `.prose` 工作流时用于约束风格和避免常见问题。

`skills/prose/state` 放状态后端说明，包括 `filesystem.md`、`in-context.md`、`sqlite.md`、`postgres.md`。默认执行模式依赖 filesystem state；其他模式按用户请求加载。

`skills/prose/lib` 放可复用 `.prose` 库程序和说明，例如 profiler、inspector、memory、cost analyzer、program improver 等，角色更像 OpenProse 工作流的标准库或工具箱。

`skills/prose/primitives` 放更底层的执行原语说明，目前看到 `session.md`，用于补充 session 上下文和压缩等执行细节。

`skills/prose/alts` 放替代风格或变体文档，如 `borges.md`、`kafka.md`、`homer.md` 等。根据当前片段推断，它们更偏提示风格、语言实验或可选附录，不是主执行路径。

## 关键入口

插件入口是 `index.ts`。它从 `runtime-api.ts` 导入 `definePluginEntry` 和 `OpenClawPluginApi`，然后导出默认插件定义：`id: "open-prose"`、`name: "OpenProse"`、`description: "Plugin-shipped prose skills bundle"`。`register(_api)` 中没有注册运行时代码，只保留注释说明 OpenProse 通过 plugin-shipped skills 交付。这说明入口主要是让插件系统识别这个包，而不是在启动时执行复杂初始化。

SDK 边界入口是 `runtime-api.ts`。它 re-export `openclaw/plugin-sdk/plugin-entry` 的 `definePluginEntry`，以及 `openclaw/plugin-sdk/core` 的 `OpenClawPluginApi` 类型。这个文件让本插件遵循 extensions 边界规则，不直接依赖 core 内部路径。

插件清单入口是 `openclaw.plugin.json`。它声明 `activation.onStartup: false`，表示不要求启动时激活；声明 `skills: ["./skills"]`，这是 OpenProse 能被加载为 skill pack 的关键；`configSchema` 为空对象且 `additionalProperties: false`，说明目前插件没有自身配置项。

技能入口是 `skills/prose/SKILL.md`。它的 frontmatter 定义 `name: prose`，描述会在用户使用 `prose` command、`.prose` 文件、OpenProse 提及时激活。它还明确“只有一个 skill”，不存在 `prose-run`、`prose-compile` 等拆分技能，所有 `prose <command>` 都经由这个单一入口路由。

执行语义入口是 `skills/prose/prose.md`。当用户要 `prose run <file>` 或运行远程 / 本地 `.prose` 程序时，技能说明要求加载 `prose.md`，并默认同时加载 `state/filesystem.md`。

## 主流程位置

启用流程从配置和插件发现开始：用户在 OpenClaw 配置里启用 `open-prose`，Gateway 重启后，插件系统读取 `openclaw.plugin.json`，根据 `skills` 字段发现 `skills/prose/SKILL.md`。`index.ts` 的注册函数本身不做额外 runtime 注册，因此主流程不是“插件启动时装配功能”，而是“技能发现后由 skill 文档驱动模型行为”。

命令路由主流程在 `skills/prose/SKILL.md` 的 `Command Routing`。`prose help` 加载 `help.md`；`prose run <file>` 加载 VM 文档和状态后端后执行；`prose run handle/slug` 先按规则解析为远程程序再执行；`prose compile <file>` 加载 `compiler.md` 做验证；`prose examples` 展示或运行 `examples/` 中的示例。这里还定义了远程程序解析规则，但文档中出现的实际外部地址在学习时只应理解为“可从 URL 或 registry shorthand 获取程序”，不需要记真实地址。

执行主流程在 `skills/prose/prose.md`。它把传统 VM 的 instruction、program counter、working memory、persistent storage、call stack、bindings、I/O 映射到 `.prose` 语句、执行位置、会话上下文、`.prose/` 状态目录、block 调用链、变量绑定和工具调用。核心概念是：模型读取 VM 规范后按程序结构真实派发 subagent session，并把输出写入状态或上下文。

状态主流程在 `skills/prose/state`。默认是 `state/filesystem.md`，适合复杂程序、恢复和调试；`state/in-context.md` 只在用户要求 in-context state 时使用；`state/sqlite.md` 和 `state/postgres.md` 标记为实验性，需要对应 CLI 或数据库条件。根据当前片段推断，状态文件不是插件自身 TypeScript 管理的，而是由执行 OpenProse VM 的 agent 按文档协议维护。

示例学习主流程在 `skills/prose/examples/README.md`。它把示例按 Basics、Agents & Skills、Variables & Composition、Parallel Execution、Loops、Pipelines、Error Handling、Advanced Features、Production Workflows、Architecture Patterns、Recursive Language Models、Meta / Self-Hosting 分类，是理解语言能力边界的地图。

## 推荐阅读顺序

先读 `extensions/open-prose/openclaw.plugin.json`，确认这是一个通过 `skills` 字段交付能力、无额外配置项、非 startup 激活的插件。

再读 `extensions/open-prose/index.ts` 和 `extensions/open-prose/runtime-api.ts`，理解 TypeScript 层只是薄入口和 SDK facade，不要误以为这里藏着完整 interpreter。

第三读 `extensions/open-prose/README.md`，建立用户视角：如何启用插件、启用后获得 `/prose`、`.prose` 程序和 telemetry 支持。

第四读 `extensions/open-prose/skills/prose/SKILL.md`，这是最重要的路由文件。重点看激活条件、`prose run` / `prose compile` / `prose help` 的分流、文件位置约定、状态模式选择，以及“不要到用户工作区搜索核心文档”的约束。

第五读 `extensions/open-prose/skills/prose/prose.md`，把 OpenProse 当作 VM 语言理解：session 是函数调用，context 是内存，bindings 是变量，parallel / block / resume / use 等语句由 VM 执行。

第六按目的选择阅读：要写程序读 `guidance/patterns.md` 和 `guidance/antipatterns.md`；要验证语法读 `compiler.md`；要理解状态读 `state/filesystem.md`；要找范式读 `examples/README.md`，再挑几个 `.prose` 示例看，不需要逐个展开所有示例。

## 常见误区

第一个误区是把 `extensions/open-prose` 当成传统 TypeScript interpreter。当前入口代码没有实现解析器或执行器，真正的“执行规范”在 `skills/prose/prose.md`，由 OpenClaw 的 skill 机制和 agent 工具调用共同完成。

第二个误区是寻找多个 prose 子技能。`SKILL.md` 明确说明只有一个 skill：`prose`。`prose run`、`prose compile`、`prose help` 都是这个 skill 内部的命令路由，不是多个独立插件或多个独立 skill。

第三个误区是默认加载所有文档。执行程序通常需要 `prose.md` 和默认状态后端；编译才加载 `compiler.md`；创作新 `.prose` 才加载 guidance；示例只在用户要求 examples 或需要参考时读取。过度加载会把上下文占满。

第四个误区是把 `examples` 当成运行时依赖。示例目录是学习和模板库，主流程入口仍是 `SKILL.md`、`prose.md`、`state/*`。大多数示例只用于展示语言能力，不代表插件启动时会执行。

第五个误区是忽略插件边界。这个目录位于 `extensions/`，按仓库规则应像第三方插件一样只依赖 `openclaw/plugin-sdk/*` 和自身本地文件。若未来扩展 OpenProse 功能，优先通过插件 SDK seam 或本插件公开入口实现，而不是从这里 deep import core 内部。
