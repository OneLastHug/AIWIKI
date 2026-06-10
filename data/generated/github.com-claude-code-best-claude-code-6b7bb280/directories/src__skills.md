# 目录：src/skills

## 它负责什么

`src/skills` 是这个仓库里“技能系统”的中枢目录，负责把不同来源的 skill 统一成可执行的 `Command`，再交给命令系统、MCP 系统和启动流程使用。它同时覆盖三类来源：本地磁盘上的 skills、编译进 CLI 的 bundled skills，以及通过 MCP `skill://` 资源发现的远端 skills。

根据当前片段推断，这个目录不是按业务大模块继续细分的那种结构，而是一个偏“编排层”的目录：真正做解析、注册、拉取、缓存和安全处理的逻辑，都集中在少数几个入口文件里。

## 直接子目录地图

`src/skills` 下当前可见的直接子目录只有 `bundled/`，其余大多是顶层协调文件。

- `src/skills/bundled/`：内置技能定义目录，放的是随 CLI 一起发布的技能实现。这里有 `verify`、`batch`、`debug`、`loop`、`remember`、`simplify`、`stuck`、`dream`、`keybindings`、`updateConfig`、`claudeInChrome`、`claudeApi` 等技能文件。
- `src/skills/bundled/verify/examples/`：`verify` 技能附带的示例材料目录，用来给技能提示词提供参考内容。
- 顶层文件虽然不是子目录，但和目录角色强相关：`bundledSkills.ts`、`loadSkillsDir.ts`、`mcpSkills.ts`、`mcpSkillBuilders.ts`、`bundled/index.ts`。

## 关键入口

- `src/skills/bundled/index.ts`：内置技能的总注册入口。`initBundledSkills()` 会按顺序调用各个 `registerXXXSkill()`，把 bundled skill 放进内存注册表。
- `src/skills/bundledSkills.ts`：bundled skill 的注册表和抽取逻辑。`registerBundledSkill()`、`getBundledSkills()`、`clearBundledSkills()` 都在这里。
- `src/skills/loadSkillsDir.ts`：文件型 skill 的主加载器。这里负责解析 frontmatter、生成 `Command`、处理路径与 hooks、统计 token、清理动态 skill 等。
- `src/skills/mcpSkills.ts`：MCP skill 的发现入口。它从 `skill://` 资源读取内容，再转换成 `Command`。
- `src/skills/mcpSkillBuilders.ts`：一个很轻的桥接层，只负责在 `loadSkillsDir.ts` 和 `mcpSkills.ts` 之间传递构造函数，避免循环依赖。

## 主流程位置

主流程可以按“启动时注册”和“运行时聚合”两段看：

1. 启动阶段在 `src/main.tsx` 调 `initBundledSkills()`，把 bundled skills 先注册进内存。
2. 命令构建阶段在 `src/commands.ts` 的 `getSkills()` 中并行拉取多来源 skills：磁盘目录 skills、plugin skills、bundled skills、builtin plugin skills。
3. `src/skills/loadSkillsDir.ts` 负责把磁盘里的 markdown skill 文件变成统一的 `Command`，它是技能系统里最重的解析层。
4. `src/skills/mcpSkills.ts` 则在 MCP 连接存在时补充远端 skills，最终和本地 skill 一起进入同一条命令链。

从代码关系看，`src/skills` 的核心不是“实现某个单一技能”，而是“把各种 skill 来源收束成同一种命令模型”。

## 推荐阅读顺序

1. 先看 `src/skills/bundled/index.ts`，理解 bundled skill 是怎么被一次性注册的。
2. 再看 `src/skills/bundledSkills.ts`，看注册表、懒抽取和安全写盘的机制。
3. 然后看 `src/skills/loadSkillsDir.ts`，这是文件型 skill 的主解析器，也是最接近业务真实流转的地方。
4. 接着看 `src/skills/mcpSkillBuilders.ts` 和 `src/skills/mcpSkills.ts`，理解 MCP skill 为什么要单独走一条发现链。
5. 最后回到 `src/main.tsx`、`src/commands.ts`，把这些入口拼回整个 CLI 启动路径。

## 常见误区

- 容易把 `bundled/` 误以为是“所有 skills 的实现目录”。实际上它只是编译进二进制的一部分，真实的 skill 来源还有磁盘目录和 MCP 资源。
- 容易把 `loadSkillsDir.ts` 只当作“读目录”的工具。它其实承担了 frontmatter 解析、命令构造、路径校验、hooks 校验、去重和动态清理等主流程工作。
- 容易忽略 `mcpSkillBuilders.ts`。它本身几乎不做业务，但它是为了打断依赖环而存在的关键胶水层。
- 容易认为 bundled skills 也是“按需扫描文件加载”。实际上 `initBundledSkills()` 是启动时的同步注册，后续只是从内存注册表读取；只有带 `files` 的 bundled skill 才会在首次调用时懒抽取参考文件。
- 容易把 `src/skills` 和 `src/components/skills` 混在一起。前者是后端/命令层的技能编排，后者更偏 UI 展示。
