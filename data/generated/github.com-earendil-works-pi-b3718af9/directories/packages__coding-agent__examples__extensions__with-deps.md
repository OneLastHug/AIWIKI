# 目录：packages/coding-agent/examples/extensions/with-deps

## 它负责什么

`packages/coding-agent/examples/extensions/with-deps` 是一个极小的 `coding-agent` 扩展示例，主题是“扩展可以拥有自己的 npm 依赖”。它不展示复杂业务能力，而是验证扩展加载器在执行 TypeScript 扩展入口时，能够从扩展目录自己的 `node_modules` 中解析第三方包。

这个示例注册了一个工具 `parse_duration`。工具输入类似 `2 days`、`1h`、`5m` 这样的自然语言时长字符串，内部调用 npm 包 `ms` 将其转换为毫秒数，然后把结果以文本形式返回给 agent。目录顶部注释明确说明：该示例需要先在本目录执行 `npm install`，因为它依赖扩展自身目录下的依赖安装结果。

从学习角度看，这个目录的重点不是工具能力本身，而是扩展工程形态：一个独立 `package.json`、一个 `pi.extensions` 声明、一个默认导出的扩展函数，以及一个被扩展函数注册到 `ExtensionAPI` 的工具。

## 直接子目录地图

这个目标目录没有直接子目录。它是一个扁平示例目录，所有关键信息都在根层文件中：

- `index.ts`：扩展入口文件，负责导出默认函数并注册工具。
- `package.json`：声明这是一个独立 npm 包，配置 `pi.extensions` 指向 `./index.ts`，并列出扩展自己的依赖。
- `package-lock.json`：锁定该示例目录的 npm 依赖版本，配合本目录内的 `npm install` 使用。
- `.gitignore`：用于忽略本示例运行或安装依赖时产生的本地文件，通常包括类似 `node_modules` 这样的内容。

由于没有 `src/`、`test/`、`fixtures/` 等分层，这里可以把目录整体理解为“单文件扩展 + 独立依赖清单”的最小样板。

## 关键入口

最关键的入口有两个，分别对应“包级发现”和“运行时注册”。

第一个入口是 `package.json` 中的 `pi.extensions` 字段。该字段声明：

`"./index.ts"`

这表示 pi 的扩展发现逻辑会把 `index.ts` 当作扩展模块加载。学习这个目录时，应先看 `package.json`，因为它回答了“系统怎么知道这个扩展在哪里”的问题。

第二个入口是 `index.ts` 的默认导出函数：

`export default function (pi: ExtensionAPI)`

这个函数接收 `ExtensionAPI` 实例，代表扩展获得了向 coding-agent 注册能力的上下文。函数体中调用 `pi.registerTool(...)`，把 `parse_duration` 注册成可被模型或 agent 调用的工具。

工具定义里包含几个关键字段：

- `name: "parse_duration"`：工具的程序化名称。
- `label: "Parse Duration"`：面向界面的短标签。
- `description`：说明工具把人类可读的时长字符串转换为毫秒。
- `parameters`：用 `Type.Object` 和 `Type.String` 描述参数结构。
- `execute`：工具真正执行的异步函数。

其中 `ms` 是这个示例要验证的独立依赖。`index.ts` 通过顶层导入 `import ms from "ms"` 使用它，说明扩展加载阶段就需要正确解析该包。

## 主流程位置

主流程集中在 `index.ts`，可以按“加载扩展、注册工具、执行工具”三段理解。

第一段是扩展加载。根据 `package.json` 的 `pi.extensions` 配置，扩展系统定位到 `index.ts`，通过 TypeScript 运行时加载机制执行默认导出。文件注释提到该示例用于测试 `jiti` 能否从扩展自身的 `node_modules` 解析模块；因此根据当前片段推断，仓库的扩展运行机制会用类似 `jiti` 的方式加载 `.ts` 扩展文件，而不是要求示例先编译成 JavaScript。

第二段是工具注册。默认导出函数收到 `pi: ExtensionAPI` 后立即调用 `pi.registerTool`。这一步把工具元数据、参数 schema 和执行函数交给 agent 框架。参数 schema 由 `Type.Object({ duration: Type.String(...) })` 定义，说明工具只需要一个字符串参数 `duration`。

第三段是工具执行。`execute` 接收 `_toolCallId` 和 `params`，从 `params.duration` 取出字符串并传给 `ms`。如果 `ms(...)` 返回 `undefined`，说明输入无法解析，代码会抛出 `Invalid duration` 错误；否则返回标准工具结果对象：

`content: [{ type: "text", text: "... milliseconds" }]`

`details: {}`

这说明该工具没有额外结构化详情，只把转换结果放入文本内容中。整体流程很短，但正好覆盖扩展工具的核心生命周期：声明入口、注册能力、校验输入、调用第三方依赖、返回工具消息。

## 推荐阅读顺序

建议先读 `package.json`。它能快速建立目录角色：这是一个 `private` 示例包，`type` 是 `module`，`pi.extensions` 指向 `./index.ts`，并且依赖 `ms`。其中 `scripts` 里的 `clean`、`build`、`check` 都只是输出占位文本，说明该目录不是为了展示构建流程，而是为了展示扩展依赖解析。

第二步读 `index.ts` 顶部注释。注释直接说明该示例的意图：扩展有自己的 npm 依赖，并且要求在此目录执行 `npm install`。这条信息对理解 `package-lock.json` 和 `dependencies` 很关键。

第三步读 `index.ts` 的 import 区域。这里可以看到它同时依赖仓库提供的 `@earendil-works/pi-coding-agent` 类型、第三方包 `ms`，以及 `typebox` 的 `Type`。其中 `ms` 是本目录 `package.json` 明确声明的运行时依赖，`@types/ms` 是开发类型依赖。

第四步读 `pi.registerTool` 调用。重点看工具元数据、参数 schema、`execute` 里的错误处理和返回结构。这个示例足够小，读完这一处就基本理解了它的全部主流程。

## 常见误区

第一个误区是把这个目录当作普通应用示例。它不是一个可独立启动的 CLI 或服务，也没有自己的主函数循环。它的入口由 pi 扩展系统读取 `package.json` 后加载，核心是被动注册能力。

第二个误区是只在仓库根目录安装依赖，然后期望这个示例一定可运行。文件注释强调需要在 `packages/coding-agent/examples/extensions/with-deps` 目录内执行 `npm install`。这个示例的目标正是验证扩展自己的 `node_modules` 解析，所以本地依赖位置是学习重点。

第三个误区是忽略 `pi.extensions`。如果只看 `index.ts`，会知道它注册了工具，但不知道扩展系统如何发现它。`package.json` 中的 `pi.extensions` 才是目录级入口声明。

第四个误区是把 `parse_duration` 理解成复杂的时间解析能力。实际解析能力来自 `ms` 包，本目录只是包装它并演示工具注册。输入不合法时，错误也来自包装层对 `undefined` 的判断，而不是复杂校验逻辑。

第五个误区是认为 `build` 或 `check` 会做真实构建校验。当前 `package.json` 中这些脚本都是 `echo` 占位，根据当前片段推断，它们主要用于让示例包符合仓库脚本接口，而不是提供实际构建过程。
