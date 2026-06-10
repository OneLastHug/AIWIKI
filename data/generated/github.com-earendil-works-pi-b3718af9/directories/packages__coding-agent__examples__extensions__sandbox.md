# 目录：packages/coding-agent/examples/extensions/sandbox

## 它负责什么

`packages/coding-agent/examples/extensions/sandbox` 从路径命名看，属于 `packages/coding-agent` 包下面的示例代码区域，用来展示 coding agent 的 extension 机制如何接入或演示 “sandbox” 能力。这里的重点应当不是生产运行时代码，而是给开发者提供一个最小或接近最小的扩展示例：如何定义扩展、如何把扩展挂到 coding agent 的示例运行环境里，以及 sandbox 相关能力如何通过 extension 边界暴露出来。

根据当前片段推断，`examples/extensions` 这一层通常用于放置多个可独立阅读或运行的 extension 示例；`sandbox` 则应当是其中一个面向隔离执行、受限文件系统、命令执行环境或工具权限模型的示例目录。它的学习价值主要在于理解扩展与 agent 主流程之间的连接点，而不是理解整个 sandbox 实现本身。真正的 sandbox 核心实现大概率位于 `packages/coding-agent/src`、共享 runtime 层，或其他包的内部模块中；本目录更可能只是示例装配层。

需要说明的是：在当前可读片段中，目标路径没有被成功定位到，因此下面关于目录角色、入口和流程的说明以路径命名和仓库结构约定为依据，属于“根据当前片段推断”。如果实际仓库内容存在该目录，应以该目录下的 `package.json`、`README.md`、入口 `.ts` 文件和相邻 `examples/extensions` 示例为准。

## 直接子目录地图

当前片段无法确认 `packages/coding-agent/examples/extensions/sandbox` 下实际有哪些直接子目录，因此不能逐一给出确定的子目录说明。按这类示例目录的常见组织方式，它可能包含以下几类路径角色：

`src`：如果存在，通常放置 extension 的 TypeScript 源码，包括扩展注册函数、工具定义、sandbox 调用封装、示例 provider 或 mock 环境。

`test` 或 `tests`：如果存在，通常用于验证示例扩展的行为，尤其是 sandbox 工具是否以预期参数被调用、权限或错误路径是否被正确处理。

`fixtures`：如果存在，通常放置示例运行所需的输入文件、临时项目结构、mock 配置或被 sandbox 读取和修改的样例文件。

`dist`、`build`、`node_modules`：如果出现，一般属于构建产物或依赖目录，不是学习主线，阅读时应优先跳过。

如果实际目录没有子目录，而只有少量入口文件，则它更可能是一个平铺的最小 extension 示例：入口文件直接完成扩展声明、注册和示例执行。

## 关键入口

优先寻找 `packages/coding-agent/examples/extensions/sandbox/README.md`。示例目录如果带说明文档，README 通常会解释运行命令、示例目标、期望输出和依赖前置条件，是判断该目录边界的第一入口。

其次寻找 `packages/coding-agent/examples/extensions/sandbox/package.json`。它可以说明这个示例是否能独立运行、有哪些脚本命令、依赖哪些 workspace 包，以及入口文件名称。对于 examples 目录，`package.json` 里的 `scripts` 比源码文件名更可靠，因为示例可能通过 `tsx`、`node --experimental-strip-types` 或仓库自定义 runner 启动。

然后寻找常见源码入口，例如 `index.ts`、`main.ts`、`extension.ts`、`sandbox.ts`、`run.ts`。如果存在 `extension.ts`，它大概率是扩展声明或注册点；如果存在 `run.ts` 或 `main.ts`，它更可能是演示执行入口；如果存在 `sandbox.ts`，它可能只是对 sandbox API 的示例封装。

还应对照相邻目录 `packages/coding-agent/examples/extensions` 下其他示例。扩展示例通常共享同一套骨架：导入 coding-agent 的 extension API，声明若干工具或 hooks，再由一个 runner 启动。理解相邻示例的共同结构，有助于避免把 sandbox 示例里的通用模板误认为 sandbox 专属逻辑。

## 主流程位置

这个目录的主流程可以按“示例启动、扩展注册、agent 调用、sandbox 执行、结果回传”来阅读。

第一步是示例启动。入口通常由 `package.json` 的脚本或 `index.ts`、`main.ts` 触发，负责构造示例 agent、加载 extension，并准备一段演示 prompt 或任务。

第二步是扩展注册。这里会把 sandbox 相关能力注册到 coding agent 可见的工具、命令、hook 或 extension manifest 中。关键点是确认扩展暴露给 agent 的接口名称、参数 schema、返回值结构，以及是否声明权限。

第三步是 agent 调用扩展能力。主流程会从 agent 的任务循环进入工具选择或 extension 调度逻辑。示例目录里可能只包含调用侧的薄封装，真正的调度逻辑通常在 `packages/coding-agent/src` 内部。

第四步是 sandbox 执行。根据路径名推断，这一段会触发某种隔离环境中的命令、文件操作或代码执行。阅读时要区分“示例如何调用 sandbox”和“sandbox 如何实现隔离”。前者属于本目录主线，后者通常不在 examples 目录内。

第五步是结果回传。sandbox 的 stdout、stderr、退出码、文件变更摘要或错误信息会被包装成 extension/tool result，再回到 agent 的消息流中。这个返回结构是学习该示例时最值得关注的部分之一，因为它体现了扩展能力如何被 agent 消费。

## 推荐阅读顺序

1. 先读 `packages/coding-agent/examples/extensions/sandbox/README.md`，确认示例目的、运行方式和预期行为。如果没有 README，就从 `package.json` 的 `scripts` 和依赖开始。

2. 再读示例入口文件，优先级为 `index.ts`、`main.ts`、`run.ts`。目标是找到程序从哪里启动、如何创建 agent、如何加载 sandbox extension。

3. 接着读扩展定义文件，通常可能叫 `extension.ts`、`sandbox.ts` 或位于 `src` 下。重点看导出的注册函数、工具定义、参数类型和返回类型。

4. 然后对照相邻的 `packages/coding-agent/examples/extensions/*` 示例，分离通用 extension 模板和 sandbox 示例的特有逻辑。

5. 最后再追到 `packages/coding-agent/src` 中的 extension 调度、tool execution 或 sandbox runtime 相关实现。不要一开始就深入底层，否则容易忽略示例目录本身想表达的最小接入方式。

## 常见误区

第一个误区是把 examples 目录当成生产实现。`packages/coding-agent/examples/extensions/sandbox` 更可能是教学和验证入口，不应直接等同于 coding agent 的 sandbox 核心模块。真正的隔离策略、权限控制、进程管理和文件系统边界通常在 runtime 或 agent 内部实现。

第二个误区是只看文件名中的 `sandbox`，就假设这里包含完整安全模型。根据当前片段推断，这里更可能展示“如何调用 sandbox 能力”，而不是定义完整的安全边界。安全相关结论必须追到实际执行层后才能确认。

第三个误区是忽略相邻示例。extension 示例往往共享一套注册方式和运行骨架；只有先看清共同结构，才能知道 sandbox 示例新增了什么。

第四个误区是把构建产物或依赖目录纳入主线。若目录下存在 `dist`、`build`、`node_modules`，阅读时应优先跳过，除非源码缺失或需要核对发布后的入口。

第五个误区是过早逐文件展开。这个目录的学习目标应是建立地图：入口在哪里、扩展在哪里注册、sandbox 调用在哪里发生、结果在哪里返回。等这些主干清楚后，再根据具体问题深入单个文件。
