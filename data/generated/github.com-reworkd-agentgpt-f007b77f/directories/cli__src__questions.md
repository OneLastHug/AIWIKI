# 子系统：cli/src/questions

## 解决什么问题

`cli/src/questions` 是 AgentGPT CLI 的交互式问题配置层，负责把“用户需要选择或填写什么”描述成 `inquirer` 可以执行的 question 对象。它本身不启动服务、不写 `.env` 文件，也不直接决定 Docker 或手动运行的具体动作；它的职责是收集输入并做前置校验，然后把标准化后的答案交给上游入口 `cli/src/index.js` 继续处理。

从当前代码看，这个目录主要覆盖两种初始化场景：已有 `./next/.env` 时，只询问运行方式；没有 `.env` 时，除了运行方式，还会询问 OpenAI、Serper、Replicate 三类 API Key，并对非空输入进行格式校验和远端可用性校验。这样可以把“交互问题定义”从“环境文件生成”和“进程启动”中拆出来，使 CLI 入口保持较薄。

## 相关目录和文件

`cli/src/questions/sharedQuestions.js` 定义共享问题 `RUN_OPTION_QUESTION`，用于询问用户如何运行 AgentGPT。当前选项有 `docker-compose` 和 `manual`，默认值是 `docker-compose`。

`cli/src/questions/newEnvQuestions.js` 定义新环境初始化时的问题列表 `newEnvQuestions`。它复用 `RUN_OPTION_QUESTION`，并追加 `OpenAIApiKey`、`serpApiKey`、`replicateApiKey` 三个输入项。每个 API Key 都允许留空，但如果用户填写，就会先走正则格式检查，再访问对应服务接口验证凭证是否可用。文档中不展开真实外部接口地址，源码里这些地址应按外部依赖处理。

`cli/src/questions/existingEnvQuestions.js` 定义已有环境文件时的问题列表 `existingEnvQuestions`。它只包含 `RUN_OPTION_QUESTION`，因为此时 CLI 会先通过 `cli/src/envGenerator.js` 校验已有 `.env` 的 key 完整性，不再重复询问 API Key。

相邻的关键文件是 `cli/src/index.js`、`cli/src/envGenerator.js`、`cli/src/helpers.js` 和 `cli/package.json`。其中 `index.js` 消费问题列表，`envGenerator.js` 消费 answers 并写入 `../next/.env`、`../platform/.env`，`helpers.js` 提供 key 校验工具和错误文案，`package.json` 声明了 `inquirer`、`node-fetch` 等依赖。

## 核心对象

`RUN_OPTION_QUESTION` 是整个目录最基础的共享对象。它的 `type` 是 `list`，`name` 是 `runOption`，因此 `inquirer.prompt(...)` 返回的 answers 中会包含 `answers.runOption`。这个字段随后被 `cli/src/index.js` 的 `handleRunOption` 使用：值为 `docker-compose` 时执行 `docker-compose up --build`，值为 `manual` 时打印前端、后端和数据库配置的手动启动提示。

`newEnvQuestions` 是一个 question 数组。数组第一项是共享运行方式问题，后续三项都是 `input` 类型。它们的 `name` 分别是 `OpenAIApiKey`、`serpApiKey`、`replicateApiKey`，这些名字不是随意文本，而是下游 `generateEnv(answers)` 读取的字段名。比如 `envGenerator.js` 会把 `envValues.OpenAIApiKey` 写入 `REWORKD_PLATFORM_OPENAI_API_KEY`，把 `envValues.serpApiKey` 写入 `REWORKD_PLATFORM_SERP_API_KEY`，把 `envValues.replicateApiKey` 写入 `REWORKD_PLATFORM_REPLICATE_API_KEY`。

`existingEnvQuestions` 是最小问题集，当前只复用 `RUN_OPTION_QUESTION`。它表达的业务判断是：如果环境文件已经存在且通过完整性校验，就不再收集凭证，只让用户选择启动方式。

各输入项的 `validate` 函数也是核心对象的一部分。它们返回 `true` 表示通过，返回 `validKeyErrorMessage` 表示校验失败。校验逻辑依赖 `helpers.js` 中的 `isValidKey(apikey, pattern)`，并通过 `node-fetch` 请求外部服务确认 key 的实际有效性。

## 运行流程

CLI 从 `cli/src/index.js` 启动后，先调用 `printTitle()` 输出欢迎信息。随后通过 `doesEnvFileExist()` 判断 `../next/.env` 是否存在。

如果 `.env` 已存在，流程进入 `handleExistingEnv()`。它会先调用 `testEnvFile()` 检查已有文件是否缺少必要 key。校验通过后，`inquirer.prompt(existingEnvQuestions)` 开始交互，只收集 `runOption`，最后调用 `handleRunOption(answers.runOption)` 启动 Docker Compose 或打印手动运行指引。

如果 `.env` 不存在，流程进入 `handleNewEnv()`。此时 `inquirer.prompt(newEnvQuestions)` 会依次询问运行方式、OpenAI API Key、Serper API Key 和 Replicate API Key。每个 API Key 都可以留空；留空表示使用默认占位值或禁用对应能力。填写时，validate 会执行本地格式校验和远端请求校验。所有问题完成后，`generateEnv(answers)` 根据答案生成统一 env 内容，并保存到前端和后端两个 `.env` 文件，最后再调用 `handleRunOption`。

根据当前片段推断，这个 CLI 的设计目标偏向开发环境快速启动，而不是生产级配置管理。依据是生成内容固定包含 `NODE_ENV=development`、本地前后端地址、Docker Compose 数据库主机名，以及手动运行提示。

## 上下游依赖

上游入口是 `cli/src/index.js`。它导入 `newEnvQuestions` 和 `existingEnvQuestions`，并把它们直接传给 `inquirer.prompt`。因此 questions 目录导出的必须是符合 `inquirer` 约定的对象数组或对象，字段名、类型和值域都要和入口逻辑匹配。

下游消费主要在 `cli/src/envGenerator.js` 和 `cli/src/index.js`。`runOption` 决定运行方式；`OpenAIApiKey`、`serpApiKey`、`replicateApiKey` 决定生成到环境文件中的后端配置值。字段名一旦改动，下游不会自动感知，可能导致生成的 `.env` 继续落入默认值。

横向依赖包括 `cli/src/helpers.js` 的 `isValidKey` 和 `validKeyErrorMessage`，以及 `node-fetch`。`newEnvQuestions.js` 还依赖外部服务的认证接口可访问，网络失败、服务变更或 API Key 格式变更都会让交互校验失败。

包层面的依赖在 `cli/package.json` 中体现。该 CLI 使用 ESM，`type` 为 `module`，Node 版本限制为 `>=18.0.0 <19.0.0`，问题交互依赖 `inquirer`，远程校验依赖 `node-fetch`。

## 修改时最容易踩的坑

最容易出问题的是 question 的 `name` 字段。`runOption`、`OpenAIApiKey`、`serpApiKey`、`replicateApiKey` 都被下游按字符串读取，改名后如果没有同步修改 `cli/src/index.js` 或 `cli/src/envGenerator.js`，CLI 不一定会报错，但生成的环境变量会丢值或回退到默认占位。

第二个坑是 `choices.value`。`RUN_OPTION_QUESTION` 中的 `docker-compose` 和 `manual` 与 `handleRunOption` 的条件判断强绑定。如果新增选项，例如 `npm` 或 `pnpm`，只改 choices 不改 `handleRunOption`，用户选择后不会有实际动作。

第三个坑是远程 validate 带来的交互阻塞。`newEnvQuestions.js` 在输入 API Key 后会访问外部服务做验证。网络不可用、代理缺失、服务接口调整、限流或服务端异常，都会让用户误以为 key 无效。修改时要区分“格式校验失败”和“远程请求失败”的用户体验。

第四个坑是正则规则过硬。OpenAI、Serper、Replicate 的 key 格式如果发生变化，当前正则会先于远程请求拦截输入。比如 OpenAI key 当前只接受 `sk-` 加固定长度字母数字的形式；如果平台引入新前缀或不同长度，旧 CLI 会拒绝合法 key。涉及现代外部 API Key 格式时，应以官方最新规则为准。

第五个坑是空值语义不一致。三个 API Key 都允许空字符串，但下游处理不同：OpenAI 空值会写入 `"<change me>"`，Serper 和 Replicate 空值会写入空字符串字面量。修改问题文案或默认值时，应同步检查生成的 env 语义是否仍然符合后端读取逻辑。

## 推荐阅读顺序

建议先读 `cli/src/index.js`，理解 CLI 如何区分已有环境和新环境，以及 `inquirer.prompt(...)` 的返回值如何进入后续流程。

然后读 `cli/src/questions/sharedQuestions.js`，确认共享的 `runOption` 问题和值域，这是整个目录与启动逻辑的连接点。

接着读 `cli/src/questions/newEnvQuestions.js`，重点看三个 API Key 的 `name`、`message`、`validate`，理解新环境初始化时收集哪些输入，以及这些输入为什么必须提前校验。

再读 `cli/src/questions/existingEnvQuestions.js`，它很短，但能说明已有 `.env` 场景下为什么只需要运行方式。

最后读 `cli/src/envGenerator.js` 和 `cli/src/helpers.js`。前者说明 answers 如何被写成具体环境变量，后者说明本目录 validate 依赖的通用校验函数和错误文案。这样阅读能从入口流程到问题定义，再到下游消费，形成完整闭环。
