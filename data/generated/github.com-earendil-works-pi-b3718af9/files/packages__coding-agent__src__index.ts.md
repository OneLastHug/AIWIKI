# 文件：packages/coding-agent/src/index.ts
## 一句话定位
这是 `coding-agent` 包的总入口文件，职责不是实现业务，而是把分散在 `cli/`、`core/`、`modes/`、`utils/` 等目录里的能力统一重新导出，供外部以一个稳定入口消费。

## 它暴露/定义了什么
它几乎不定义新逻辑，主要做“聚合导出”。从当前片段看，它对外暴露了四类内容：命令行解析与启动入口，如 `parseArgs`、`main`；会话、配置、认证、压缩、模型与技能管理等核心基础设施，如 `AgentSession`、`SessionManager`、`SettingsManager`、`AuthStorage`、`compact`、`loadSkills`；工具和扩展系统，如 `createBashToolDefinition`、`discoverAndLoadExtensions`、`wrapRegisteredTools`；以及一批交互模式与 UI 组件、图片处理、剪贴板、shell 配置等辅助能力。

## 谁调用它
根据当前片段推断，它主要被两类调用方使用：一类是包外部的上层代码，把 `index.ts` 当成 `coding-agent` 的统一 API 入口来 import；另一类是仓库内部的消费方，尤其是需要跨模块能力的地方，倾向于从这里拿标准导出，而不是直接深入具体实现文件。由于它同时导出了 `main`、`InteractiveMode`、`runPrintMode`、`runRpcMode` 这类启动相关能力，CLI 启动链路和运行模式封装也会间接受益于这个入口。

## 它调用谁
它本身几乎不“调用”业务逻辑，只做 re-export。真正的实现都在它导出的目标模块里，例如 `./main.ts`、`./core/agent-session.ts`、`./core/extensions/index.ts`、`./modes/index.ts`、`./utils/image-resize.ts`。所以这里更准确地说，是它把这些模块编织成一个公共 API 面。

## 核心流程
核心流程可以理解成三层：

1. 外部先从 `packages/coding-agent/src/index.ts` 进入，得到整个包的统一接口。
2. 按功能域分组拿到需要的能力，比如命令行、会话管理、扩展、工具、模式、资源加载。
3. 真正执行时再落到具体实现模块，`index.ts` 只负责让这些能力“可见且可被组合”。

这类文件的价值在于降低使用门槛，并稳定包的公共边界。对上层来说，它让 `coding-agent` 看起来像一个单一模块；对内部来说，它把分散实现统一成一套约定好的出口。

## 关键函数的高层作用
- `parseArgs`：解析 CLI 参数，把命令行输入转成结构化配置。
- `main`：程序主入口，通常负责串起启动、模式选择和执行流程。
- `createAgentSession` / `createAgentSessionRuntime`：构建可运行的会话上下文，是 agent 执行链路的核心装配点。
- `compact` / `shouldCompact` / `generateSummary`：处理上下文压缩，控制会话长度和摘要生成。
- `discoverAndLoadExtensions` / `wrapRegisteredTools`：发现并接入扩展系统，把外部能力挂入运行时。
- `SessionManager` / `SettingsManager` / `ModelRegistry`：分别负责会话、设置、模型目录管理，是整个包的状态中枢。
- `loadSkills` / `formatSkillsForPrompt`：加载和格式化技能，服务提示词构造。
- `createBashToolDefinition`、`createEditToolDefinition`、`createReadToolDefinition` 等：为具体工具提供可注入的定义。
- `InteractiveMode`、`runPrintMode`、`runRpcMode`：不同运行模式的入口封装。
- `convertToPng`、`resizeImage`、`copyToClipboard`：面向交互体验的辅助功能。

## 修改风险
这个文件是公共 API 面，改动风险比普通实现文件更高。最主要的风险有三类：一是导出删改会直接破坏外部依赖，属于兼容性风险；二是重复导出或命名冲突会扩大到整个包的类型与运行时可见面；三是这里虽然不写逻辑，但它决定了哪些模块算“官方入口”，一旦把内部实现不慎暴露出去，后续重构成本会明显上升。对于它的修改，通常要先确认是否真的需要公开，再检查下游是否依赖这些符号。
