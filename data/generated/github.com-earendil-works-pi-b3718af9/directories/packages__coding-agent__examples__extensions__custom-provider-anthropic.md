# 目录：packages/coding-agent/examples/extensions/custom-provider-anthropic

## 它负责什么

`packages/coding-agent/examples/extensions/custom-provider-anthropic` 是一个示例型目录，目标是展示 `packages/coding-agent` 如何通过 extension 机制接入一个自定义模型提供方，并以 Anthropic 风格的接口作为样例。根据目录名和仓库约定推断，它不是核心运行时代码，而是给开发者参考的“最小可用扩展示例”：说明一个 provider 扩展需要暴露哪些入口、如何声明模型、如何把用户请求转换成上游 Anthropic API 请求，以及如何把上游返回结果再转回 coding-agent 内部使用的消息或流式事件格式。

这个目录的学习重点不是 Anthropic 本身，而是 custom provider 的接入边界。也就是说，阅读它时应关注“扩展怎样被发现、怎样注册 provider、怎样实现调用适配层”，而不是把它当成生产级 Anthropic SDK 封装。真正的生产能力通常还会涉及错误分类、重试、速率限制、凭据管理、模型能力声明、工具调用兼容、流式事件恢复等，这类内容在 example 目录里往往只保留演示所需的骨架。

需要说明：当前可读取片段只确认了仓库根目录存在，目标目录内容没有被成功展开；以下结构说明主要根据目标路径命名、`examples/extensions` 的语义以及 coding-agent 扩展目录的常见组织方式推断。

## 直接子目录地图

根据当前片段推断，这个目录大概率是一个较小的独立示例包，直接子目录不会很多，常见形态如下：

`src`：示例扩展的主要源码目录。通常会放置 provider 注册入口、Anthropic 请求适配代码、响应转换代码，以及少量类型或配置辅助逻辑。阅读时应把这里看成主战场。

`dist` 或构建输出目录：如果存在，通常是 TypeScript 编译产物，不是学习源码的首选入口。overview 阶段可以跳过。

`node_modules`：如果示例被单独安装过依赖，可能出现本地依赖目录。它不属于仓库设计内容，应忽略。

如果目标目录实际没有子目录，而是直接放置 `index.ts`、`package.json`、`README.md` 等文件，也符合“最小扩展示例”的风格。此时可以把目录本身理解为一个扁平的 example package：配置文件负责声明示例包，入口文件负责导出 extension，README 负责说明运行方式。

## 关键入口

最值得优先寻找的入口通常有三类。

第一类是包入口，例如 `package.json`。它会告诉你这个示例是否是独立 npm package、主入口指向哪里、是否依赖 `@anthropic-ai/sdk` 或仓库内的 coding-agent 包。它还可能通过 `scripts` 暴露构建、检查或运行示例的命令。对于学习扩展机制，`package.json` 的价值在于确认“这个目录如何被加载”。

第二类是扩展导出入口，例如 `src/index.ts`、`index.ts` 或类似文件。这里通常会导出一个 extension 对象、注册函数，或符合 coding-agent 扩展协议的 factory。它是从“目录”进入“运行时”的桥梁：coding-agent 不会关心示例内部怎么分文件，它只需要从入口拿到可注册的 provider 能力。

第三类是 provider 实现入口，例如 `src/provider.ts`、`src/anthropic-provider.ts`、`src/client.ts` 这类文件。这里通常负责把 coding-agent 的统一请求结构转换成 Anthropic 接口需要的参数，包括 model、messages、system prompt、temperature、max tokens、tool definitions、stream 选项等。反向转换也会在这里或邻近文件完成，例如把 Anthropic 的 content block、tool use、stop reason、usage 信息映射回内部消息结构。

## 主流程位置

主流程可以按“注册、配置、调用、转换”四步理解。

注册阶段发生在扩展入口。coding-agent 加载 extension 后，入口代码会声明一个自定义 provider，并把它挂到扩展系统认识的位置。这里的核心不是网络调用，而是 provider id、显示名称、可用模型、能力标记等元信息。若代码里出现类似 `provider`、`models`、`extension`、`register`、`createProvider` 的命名，应优先阅读。

配置阶段负责读取 Anthropic 凭据和运行参数。常见来源是环境变量，例如 API key、base URL、默认模型等。示例目录通常会保持简单，只演示必要配置。需要注意，凭据读取逻辑一般不应该散落在每次请求中，而应集中在 provider 初始化或 client 创建位置。

调用阶段是主流程的中段。coding-agent 收到一次模型请求后，会把内部消息、工具定义和生成参数交给 custom provider。provider 再构造 Anthropic 请求，并调用 SDK 或 `fetch`。如果示例支持 streaming，主流程会从“一次性返回文本”变成“消费上游事件流并逐步产出内部事件”。

转换阶段是最容易出错、也最值得学习的位置。Anthropic 的消息格式通常包含多种 content block，内部 agent 也可能需要区分普通文本、工具调用、工具结果、完成原因和 token usage。这个目录的价值就在于展示这些边界如何对齐。overview 阶段不必逐行看每个 case，但要明确：provider 的职责不是只把 prompt 发出去，而是维护两个协议之间的语义一致性。

## 推荐阅读顺序

1. 先看 `README.md` 或示例说明文件，确认这个目录演示的目标、运行前置条件和环境变量名称。不要一开始就陷入 SDK 调用细节。

2. 再看 `package.json`，确认入口文件、依赖包、构建方式，以及它是否作为 workspace package、local extension 或独立 example 被引用。

3. 接着看入口文件，通常是 `src/index.ts` 或根目录 `index.ts`。重点找 extension 的导出形态、provider id、模型列表和注册函数。

4. 然后看 provider/client 实现文件。重点跟踪一次请求从 coding-agent 内部结构进入 Anthropic API 的路径，再跟踪响应如何返回。

5. 最后看类型、schema、工具调用或流式转换相关文件。只有在理解主流程后，这些辅助代码才容易读懂。

## 常见误区

第一个误区是把这个目录当成 Anthropic 官方集成。它更可能是 custom provider 示例，重点是扩展协议，不是完整厂商适配层。生产环境接入还需要补足更严格的错误处理、兼容性测试和配置策略。

第二个误区是只看请求发送代码。provider 的关键复杂度通常在格式转换，尤其是 messages、system prompt、tool calls、stream chunks 和 usage 信息的双向映射。只看到 API key 和 `messages.create` 之类调用，并不代表已经理解扩展主流程。

第三个误区是忽略模型能力声明。coding-agent 需要知道 provider 支持哪些模型、是否支持工具调用、是否支持流式输出、上下文窗口或输出限制是什么。模型列表如果只是示例硬编码，就不应推断为完整模型注册中心。

第四个误区是把 example 的简化逻辑照搬到核心包。示例目录通常为了可读性牺牲覆盖面；如果要进入生产代码，应回到 `packages/coding-agent/src` 下寻找正式 provider、extension loader、模型请求类型和测试套件，对照确认哪些行为是框架要求，哪些只是这个示例的最小实现。

第五个误区是从构建产物或依赖目录开始读。如果存在 `dist`、`node_modules` 或生成文件，应优先跳过。学习顺序应围绕源码入口、provider 实现和协议转换，而不是编译后的 JavaScript。
