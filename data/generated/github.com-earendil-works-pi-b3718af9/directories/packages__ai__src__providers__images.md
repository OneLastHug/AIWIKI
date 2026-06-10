# 子系统：packages/ai/src/providers/images

## 解决什么问题

`packages/ai/src/providers/images` 是 `packages/ai` 中面向“图像生成能力”的 provider 子系统。它的职责不是保存图片资源，也不是前端图片渲染，而是把上层统一的 AI 调用抽象转换成具体模型厂商的图像 API 请求，并把厂商响应再转换回项目内部可消费的统一结果。

根据当前片段推断，这个目录承担的是“文本提示词到图片输出”的适配层：上游只关心传入 prompt、模型、尺寸、输出格式等参数，下游则需要处理不同厂商的请求字段、鉴权方式、响应结构、错误格式和模型能力差异。这个目录的存在意义，就是避免调用方直接依赖某个厂商 SDK 或 HTTP 协议细节，使图像生成能力可以像文本模型、工具调用、embedding 等能力一样被统一注册、选择和调用。

由于本次可读取证据不足，以下说明基于目录命名、仓库分层和 `packages/ai/src/providers/*` 这类 provider 结构的常见职责推断；具体函数名和文件名应以本地源码为准。

## 相关目录和文件

这个目录通常位于 `packages/ai/src/providers` 之下，和其他 provider 子目录并列。它和这些邻近模块关系最密切：

- `packages/ai/src/providers/images`：图像 provider 的实现目录，通常包含 provider 注册入口、具体厂商适配器、请求/响应转换逻辑。
- `packages/ai/src/providers`：更高一层的 provider 组织目录，负责把不同能力或不同厂商的实现统一暴露给 `packages/ai`。
- `packages/ai/src/models.generated.ts`：模型元数据来源之一。图像模型如果也纳入统一模型清单，通常会在这里体现，但仓库规则明确禁止直接修改该文件，应改生成脚本后重新生成。
- `packages/ai/scripts/generate-models.ts`：模型清单生成入口。新增或调整图像模型元数据时，应优先检查这里，而不是手改生成物。
- `packages/ai/src` 下的公共类型文件：根据当前片段推断，图像 provider 会依赖统一的 model、provider、request、response、usage 或 error 类型。
- 上层调用方所在包，例如 `packages/coding-agent`、`packages/agent` 或 CLI/TUI 入口：这些模块可能通过 `packages/ai` 的统一接口发起图像生成请求，而不是直接依赖 `providers/images` 内部文件。

这个目录不应被理解为“所有图片相关逻辑”的归宿。图片上传、文件系统保存、终端展示、Markdown 渲染、前端预览等如果存在，通常属于调用方或 UI 层，不应该塞进 provider 适配层。

## 核心对象

图像 provider 子系统的核心对象可以按职责分成几类。

第一类是 provider 定义对象。它描述某个图像服务如何被识别、初始化和调用，通常包含 provider id、显示名称、支持的模型、鉴权配置、base URL 或客户端创建逻辑。上层模型选择逻辑依赖这些元数据判断“某个模型应该走哪个 provider”。

第二类是图像生成请求对象。它承载上游传入的参数，例如 `prompt`、`model`、`size`、`quality`、`style`、`responseFormat`、`n` 等。内部统一请求对象的价值在于把“业务想要什么”与“厂商 API 字段叫什么”分离。比如一个厂商可能叫 `size`，另一个厂商可能需要拆成 `width` 和 `height`；一个厂商返回 base64，另一个返回临时 URL。

第三类是响应归一化对象。图像 API 的返回一般有二进制、base64、URL、mime type、metadata、revised prompt 等多种形态。provider 目录需要把这些差异转换成统一结构，供上游保存、展示或继续传递给多模态模型。

第四类是错误和能力约束。图像生成常见失败点包括模型不支持指定尺寸、账号无权限、内容安全拒绝、速率限制、返回格式不支持、网络超时。这个目录应尽量把厂商错误转成项目内统一错误，而不是把原始 HTTP 异常泄露到 CLI 或 agent 层。

## 运行流程

典型运行流程如下。

1. 上层调用方从用户命令、agent 任务或工具调用中得到图像生成需求，构造统一的 image generation 请求。
2. `packages/ai` 的模型或 provider 选择逻辑根据 `model`、provider 配置和账号信息，定位到 `packages/ai/src/providers/images` 下的具体实现。
3. 图像 provider 校验请求参数。这里通常会检查模型是否支持图像生成、尺寸是否合法、输出数量是否在范围内、输出格式是否受支持。
4. provider 将统一请求转换为厂商 API 请求。这个阶段会处理字段映射、默认值、鉴权 header、endpoint、超时和可选参数。
5. provider 发起网络请求或调用厂商 SDK。响应回来后，将厂商格式转换为内部统一结果。
6. 上层拿到统一结果后，决定如何落盘、返回给用户、作为后续多模态输入，或在 UI 中展示。

根据当前片段推断，这个目录自身不应该负责复杂的交互编排。它更像一个纯适配层：输入是统一请求，输出是统一响应，中间隔离外部服务差异。

## 上下游依赖

上游依赖主要来自 `packages/ai` 的公共导出和模型选择机制。调用方不应跨层直接 import 某个具体厂商文件，而应通过统一接口请求图像能力。这样新增 provider 或调整厂商实现时，影响范围可以限制在 `packages/ai` 内部。

下游依赖是外部图像生成服务。可能包括 OpenAI 或其他模型供应商的 HTTP API / SDK。下游依赖的特点是变化快、能力差异大、错误结构不稳定，因此 provider 层要承担兼容和归一化压力。

横向依赖包括模型元数据、鉴权配置、通用 HTTP 客户端、日志/调试设施、错误类型和测试工具。若图像模型被纳入统一模型列表，修改时还要关注 `packages/ai/scripts/generate-models.ts` 与生成后的 `packages/ai/src/models.generated.ts` 差异。

## 修改时最容易踩的坑

最常见的坑是把厂商字段直接暴露给上层。这样短期实现快，但会导致调用方绑定某个 provider，后续新增模型或迁移 API 时成本很高。应优先维护统一请求/响应模型，在 provider 内部做字段转换。

第二个坑是忽略模型能力差异。图像模型对尺寸、质量、透明背景、编辑、变体、批量数量、返回 URL 或 base64 的支持往往不同。新增模型时不能只加一个模型名，还要确认能力矩阵和默认参数。

第三个坑是直接修改 `packages/ai/src/models.generated.ts`。仓库规则明确要求不要直接改这个生成文件；要更新 `packages/ai/scripts/generate-models.ts`，再生成结果。

第四个坑是错误处理过于粗糙。内容安全拒绝、参数非法、鉴权失败、额度不足和网络错误对用户的处理方式不同。provider 应保留足够语义，让上层能给出准确反馈。

第五个坑是测试只覆盖成功路径。图像生成通常涉及外部 API，测试应避免真实付费调用，优先用 faux provider、mock fetch 或固定响应样例覆盖参数映射、错误转换和响应归一化。

## 推荐阅读顺序

1. 先读 `packages/ai/src/providers/images` 的入口文件，理解该目录向外暴露哪些 provider、函数或类型。
2. 再读同目录下的具体 provider 实现，重点看统一请求如何映射到外部 API，以及响应如何归一化。
3. 接着读 `packages/ai/src/providers` 的汇总或注册逻辑，确认 image provider 如何接入整个 `packages/ai`。
4. 然后读 `packages/ai/src` 中与模型、provider、错误、请求响应相关的公共类型，建立边界感。
5. 如果涉及新增模型，再读 `packages/ai/scripts/generate-models.ts` 和生成后的 `packages/ai/src/models.generated.ts`，确认模型元数据来源。
6. 最后阅读调用方中使用图像能力的代码，例如 agent、CLI 或 TUI 层，理解 provider 输出如何被用户实际消费。
