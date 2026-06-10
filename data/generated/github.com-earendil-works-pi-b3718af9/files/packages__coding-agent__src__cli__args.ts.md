# 文件：packages/coding-agent/src/cli/args.ts

## 一句话定位

`packages/coding-agent/src/cli/args.ts` 是 `coding-agent` 命令行入口的参数层：负责把原始 `argv` 解析成结构化 `Args`，并集中维护用户可见的 `--help` 帮助文本。

## 它暴露/定义了什么

这个文件主要定义并导出四类内容：

`Mode`：输出/运行模式联合类型，取值为 `"text"`、`"json"`、`"rpc"`。

`Args`：CLI 解析后的核心数据结构，覆盖模型、Provider、API Key、系统提示词、会话控制、工具开关、扩展、技能、主题、文件参数、普通消息、诊断信息等字段。它是后续启动流程理解用户意图的统一输入对象。

`isValidThinkingLevel(level)`：校验 `--thinking` 是否属于允许的推理强度值，包括 `off`、`minimal`、`low`、`medium`、`high`、`xhigh`。

`parseArgs(args)`：核心解析函数，将字符串数组转换成 `Args`。

`printHelp(extensionFlags?)`：打印 CLI 帮助信息，并可把扩展注册的额外 CLI flag 追加到帮助页中。

## 谁调用它

主要调用方是 `packages/coding-agent/src/main.ts`。该文件从 `./cli/args.ts` 导入 `Args`、`Mode`、`parseArgs`、`printHelp`，并在主启动流程中调用 `parseArgs(args)`。解析结果随后被 `main.ts` 用来决定是否显示版本/帮助、是否进入 `rpc`、交互或非交互模式、如何恢复会话、加载哪些扩展和资源、选择模型与工具等。

`packages/coding-agent/src/cli/initial-message.ts` 也导入了 `Args` 类型，用于根据解析后的 `messages`、`fileArgs` 等构造初始消息。根据当前片段推断，它不负责解析，只消费类型化后的参数对象。

## 它调用谁

这个文件依赖很少，职责相对独立。它从 `@earendil-works/pi-agent-core` 引入 `ThinkingLevel` 类型，从 `chalk` 引入终端样式能力，从 `../config.ts` 引入 `APP_NAME`、`CONFIG_DIR_NAME`、`ENV_AGENT_DIR`、`ENV_SESSION_DIR` 生成帮助文本，从 `../core/extensions/types.ts` 引入 `ExtensionFlag` 类型以展示扩展参数。

运行期主要调用的是 `chalk.bold`、`chalk` 的格式化能力，以及 `console.log`。它不直接启动 Agent、不读取配置文件、不做文件 IO、不连接模型服务。

## 核心流程

`parseArgs` 是一个线性扫描器，从左到右遍历 `args`。遇到布尔开关时直接写入 `result`，例如 `--help`、`--continue`、`--no-tools`、`--offline`。遇到需要值的参数时检查下一个元素并消费它，例如 `--provider`、`--model`、`--api-key`、`--session`、`--export`。多值类参数采用追加或逗号拆分，例如 `--append-system-prompt`、`--extension`、`--skill`、`--tools`、`--exclude-tools`。

普通非 flag 参数进入 `messages`，以 `@` 开头的参数去掉前缀后进入 `fileArgs`。这使 CLI 支持 `pi @file.md "prompt"` 这样的组合输入。`--print` 还有特殊行为：它会开启非交互模式，并在下一个参数不是文件引用、不是普通 flag 时，把该参数直接作为 prompt 收进 `messages`；这里允许以 `---` 开头的文本被视为消息，避免把所有短横线开头内容都误判为选项。

未知的长选项 `--xxx` 不立即报错，而是进入 `unknownFlags`。这明显是为扩展系统预留的：主流程之后可以把这些未知参数传给扩展解析。未知短选项则写入 `diagnostics` 错误，因为短选项命名空间更容易与内建 CLI 冲突。

`printHelp` 负责输出完整帮助页。它不仅列出基础选项，也列出 install/remove/update/list/config 等命令、示例、环境变量、内建工具名。若传入 `extensionFlags`，它会动态生成 “Extension CLI Flags” 段落。

## 关键函数的高层作用

`parseArgs` 是这个文件的核心。它把命令行语法映射为应用启动契约，后续所有模式分支都依赖它的字段语义。它不做深层业务校验，只做轻量语法识别和少量诊断，例如 `--name` 缺值、`--thinking` 值非法、未知短选项。

`printHelp` 是用户文档的运行时版本。新增 CLI 参数时，如果只改 `parseArgs` 不改这里，功能可用但帮助页会过期。扩展 flag 的展示也在这里完成，所以它是内建 CLI 与扩展 CLI 之间的用户可见汇合点。

`isValidThinkingLevel` 是 `--thinking` 的类型守卫，保证写入 `Args.thinking` 的值符合 `ThinkingLevel`。辅助常量 `VALID_THINKING_LEVELS` 是它的唯一依据。

## 修改风险

最高风险是参数语义漂移。`main.ts`、`initial-message.ts`、扩展加载、会话恢复、模型选择、工具过滤都消费 `Args` 字段；改字段名、默认值或消费规则，可能让启动路径在交互、`--print`、`--mode rpc` 中表现不一致。

第二个风险是未知长参数处理。`unknownFlags` 不是无用兜底，而是扩展参数通道。把未知 `--flag` 改成直接报错，会破坏扩展 CLI；反过来，如果让短选项也静默进入扩展，可能掩盖用户拼写错误。

第三个风险是“带值参数”的边界。当前许多参数只在 `i + 1 < args.length` 时消费值，缺值时大多静默跳过，只有 `--name` 明确报错。新增参数时要决定是否延续这种宽松策略，否则 CLI 错误体验会不一致。

第四个风险是帮助文本同步。`printHelp` 中的选项、示例、环境变量、工具说明需要与真实解析和其他模块保持一致。例如新增 `Args` 字段、扩展资源类型或环境变量时，应同步更新帮助页，否则用户会依赖错误文档。

第五个风险是 `--print`、`@file`、负号开头消息之间的判定规则。这里的分支直接影响非交互调用和脚本化使用，尤其是 prompt 文本本身以 `-` 开头的场景，修改前应补充针对 `parseArgs` 的回归测试或至少覆盖常见 CLI 组合。
