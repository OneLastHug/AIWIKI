# 目录：packages/coding-agent/examples/extensions/custom-provider-gitlab-duo

## 它负责什么

`packages/coding-agent/examples/extensions/custom-provider-gitlab-duo` 是 `packages/coding-agent` 下的一个扩展示例目录，目标名称表明它用于演示如何通过 extension 机制接入一个自定义 provider，并且该 provider 面向 `GitLab Duo`。根据当前片段推断，它不是核心运行时代码，而是示例性质的集成样板：把外部模型服务、认证信息、请求格式转换、响应解析等能力包装成 coding agent 能识别的 provider 形态。

这个目录的学习重点不是“GitLab Duo 本身如何实现”，而是“coding-agent 如何允许第三方或私有 AI 服务作为模型后端”。它大概率展示了三个层次：扩展包如何被声明，provider 如何注册到 agent，运行时如何把统一的聊天或补全请求转译为 GitLab Duo 接口请求。由于当前可读证据只确认了仓库根和目标路径存在，未能展开该目录的实际文件内容，下面涉及 `src`、入口文件、配置文件等位置的描述均为根据路径命名和仓库约定做出的地图式推断。

## 直接子目录地图

当前片段没有提供该目录的实际子目录清单，因此不能精确确认每个直接子目录名称。按 `examples/extensions/custom-provider-*` 这类示例的常见结构推断，目录通常会围绕以下角色组织：

`src`：最可能承载 TypeScript 实现的位置。自定义 provider 的注册逻辑、GitLab Duo 请求适配、响应流处理、错误映射、模型元数据声明等主代码通常会放在这里。

`dist` 或构建输出目录：如果示例支持本地构建，可能存在编译产物目录。学习时应把它视为生成结果，而不是理解主流程的入口。

配置或元数据目录：如果 coding-agent 的 extension 系统要求 manifest、extension descriptor 或插件声明，可能会有专门目录或顶层配置文件用于描述扩展名称、入口模块、可暴露的 provider、运行时权限和环境变量需求。

文档或示例运行材料：可能包含 README、示例配置片段或环境变量说明，用于说明如何启用 GitLab Duo provider。这里的内容通常服务于运行示例，不是 provider 适配逻辑本身。

如果后续能读取该目录，建议优先确认实际是否存在 `src`、`package.json`、README、manifest 类文件，再把上述推断替换为确切地图。

## 关键入口

从目录角色看，关键入口应分为“包入口”和“扩展入口”两类。

包入口通常由 `package.json` 决定，例如 `main`、`exports`、`bin`、`scripts` 或构建命令会指向真正被加载的文件。对于扩展示例，`package.json` 还可能声明依赖、开发命令，以及示例如何在 monorepo 中被引用。

扩展入口通常是一个导出函数或默认导出，用来向 coding-agent 注册能力。它可能位于 `src/index.ts`、`src/extension.ts` 或类似文件中。这个入口的职责一般不是直接发起模型请求，而是把 provider 对象、模型列表、鉴权配置读取方式、请求处理函数挂到 extension API 上。

provider 入口则更靠近业务适配层，可能是 `createGitLabDuoProvider`、`GitLabDuoProvider`、`registerProvider` 一类函数或类。它负责把 coding-agent 内部的统一模型调用协议转换为 GitLab Duo 可接受的请求，并把返回结果转成 agent 上层能消费的消息、流式 chunk、tool call 或错误。

## 主流程位置

主流程可以按“加载扩展、创建 provider、发起请求、解析响应”四步理解。

第一步是扩展加载。coding-agent 在启动或读取配置时发现该示例扩展，根据 manifest 或 package 入口加载模块。这个阶段关注的是扩展如何暴露 provider，而不是具体网络请求。

第二步是 provider 创建。扩展入口读取用户配置，通常包括 GitLab 相关 token、endpoint、项目上下文或模型标识。根据当前片段推断，这一层会把 GitLab Duo 的私有配置封装成 provider 实例，避免上层 agent 直接感知 GitLab Duo 的认证细节。

第三步是请求适配。coding-agent 上层传入统一的对话消息、系统提示、工具定义、采样参数或上下文信息，provider 把这些结构映射为 GitLab Duo 接口需要的 payload。这里是学习该目录最有价值的位置，因为它体现“自定义 provider”与核心 agent 协议之间的边界。

第四步是响应解析。GitLab Duo 返回普通响应或流式响应后，provider 需要把它转换为 coding-agent 的内部事件或最终 assistant message。错误处理、取消信号、超时、限流、认证失败等也通常在这一层处理。若目录中存在单独的 client 文件，它很可能就是主流程的网络边界；若存在 provider 文件，则它很可能是协议边界。

## 推荐阅读顺序

1. 先读顶层 README 或示例说明，确认这个示例期望解决的问题：是只演示 provider 注册，还是包含完整 GitLab Duo 调用链。

2. 再读 `package.json`，确认构建方式、入口字段、依赖和运行脚本。这里能判断它是独立 npm 包、monorepo 内部示例，还是仅供本地加载的 extension。

3. 接着读 manifest 或扩展声明文件。重点看 extension 名称、入口模块、声明的 provider id、配置项名称，以及是否需要用户显式启用。

4. 然后读 `src/index.ts` 或类似入口文件。关注它如何注册 provider，不要一开始陷入底层 HTTP 细节。

5. 最后读 provider/client 实现。按调用方向看：配置读取、请求构造、网络调用、响应转换、错误映射。这样能把 GitLab Duo 专属逻辑和 coding-agent 通用 provider 接口分清楚。

## 常见误区

不要把这个目录当成 GitLab Duo 的完整 SDK。它更可能只是 coding-agent 的自定义 provider 示例，GitLab Duo 只是被接入的后端服务。

不要直接从文件名推断核心逻辑一定在 `index.ts`。在 extension 示例中，`index.ts` 可能只是注册壳，真正的请求适配可能拆在 provider、client、types 或 config 文件里。

不要把示例配置当成生产默认配置。示例往往为了便于运行而简化认证、endpoint、错误处理或模型列表；生产接入需要重新审视 token 管理、网络错误、重试策略和权限边界。

不要混淆 extension 与 provider。extension 是被 coding-agent 加载的扩展单元，provider 是扩展提供的一种模型后端能力。一个 extension 理论上可以注册多个 provider 或其他能力。

不要优先研究构建产物。如果目录里有 `dist`、编译后的 `.js` 或生成文件，应回到 TypeScript 源码和 manifest 入口理解主流程。

不要假设 GitLab Duo 的接口形态与 OpenAI 兼容。自定义 provider 的意义正是在统一 agent 协议和外部服务协议之间做转换；消息格式、流式事件、认证头、错误结构都可能不同。
