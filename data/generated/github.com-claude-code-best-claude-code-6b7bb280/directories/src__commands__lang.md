# 目录：src/commands/lang

## 它负责什么

`src/commands/lang` 负责实现内置 slash command `/lang`，用于查看或修改 CLI 的显示语言偏好。它不是一套完整的国际化系统，而是一个很薄的命令入口：接收用户输入的语言参数，校验是否为 `en`、`zh`、`auto`，然后把结果写入全局配置里的 `preferredLanguage` 字段。

从当前片段看，这个目录只处理“语言偏好设置”这一件事，不直接翻译 UI 文案，也不维护多语言资源文件。真正的语言解析逻辑在邻近工具模块 `src/utils/language.ts` 中：`getResolvedLanguage()` 会读取 `getGlobalConfig().preferredLanguage`，如果用户指定 `en` 或 `zh` 就直接返回；如果是 `auto` 或未设置，则读取系统 locale，只把系统语言为 `zh` 的情况解析为中文，其余情况回退为英文。

因此，这个目录可以理解为“`/lang` 命令适配层”：它连接 slash command 系统、全局配置读写、语言解析工具，以及命令执行完成后的系统提示输出。

## 直接子目录地图

`src/commands/lang` 当前没有直接子目录，只有两个文件：

`src/commands/lang/index.ts` 是命令声明文件，导出 `/lang` 的元信息。这里定义了命令名、描述、参数提示、是否立即执行，以及如何懒加载真实实现。

`src/commands/lang/lang.ts` 是命令执行文件，导出 `call()` 函数。这里完成参数解析、合法性校验、配置读写和结果提示。

这个目录结构和仓库里很多简单内置命令一致：`index.ts` 负责让命令注册表识别命令，具体行为放在同目录的实现文件中。对于更复杂的命令，通常会有 `.tsx` UI 面板或更多子模块；但 `/lang` 不需要交互式表单，所以保持为极简的本地命令实现。

## 关键入口

第一个入口是 `src/commands/lang/index.ts`。它默认导出一个满足 `Command` 类型的对象：

`name: 'lang'` 表示用户通过 `/lang` 调用；`description: 'Set display language (en/zh/auto)'` 用于帮助列表或命令补全；`argumentHint: '<en|zh|auto>'` 提示可用参数；`type: 'local-jsx'` 表示它属于本地 JSX 命令体系；`immediate: true` 表示该命令输入后可立即执行，而不是进入普通对话排队；`load: () => import('./lang.js')` 则把真实实现延迟到调用时再加载。

第二个入口是 `src/commands/lang/lang.ts` 的 `call()`。它的签名符合 `LocalJSXCommandCall` 模式，接收 `onDone`、命令上下文和 `args`。虽然类型上带有 `ToolUseContext & LocalJSXCommandContext`，但当前实现没有使用上下文参数，所以参数名写成 `_context`。

第三个入口在命令总表 `src/commands.ts`。该文件通过 `import lang from './commands/lang/index.js'` 引入命令声明，并把 `lang` 放入 `COMMANDS()` 返回的内置命令数组中。随后 `getCommands(cwd)` 会组合内置命令、skills、plugins、workflows 等来源，再经过可用性和启用状态过滤后提供给 REPL、帮助面板和 slash command 处理链路。

## 主流程位置

`/lang` 的主流程集中在 `src/commands/lang/lang.ts`。

当用户只输入 `/lang`，没有附加参数时，`call()` 会执行“查询当前语言状态”的分支：先把 `args.trim().toLowerCase()` 得到的结果判定为空，再读取 `getGlobalConfig().preferredLanguage ?? 'auto'`。随后调用 `getResolvedLanguage()` 计算实际生效语言。如果偏好值是 `auto`，返回文案会带上类似 `Auto (follow system) → 中文` 或 `Auto (follow system) → English` 的后缀；最后通过 `onDone(..., { display: 'system' })` 把结果作为系统消息展示。

当用户输入 `/lang en`、`/lang zh` 或 `/lang auto` 时，流程进入设置分支。代码先用 `VALID_LANGS` 校验参数，只接受 `['en', 'zh', 'auto']`。非法值不会抛异常，而是通过系统消息提示 `Invalid language "xxx". Use: en, zh, or auto`，然后返回 `null`。

合法值会被断言为 `PreferredLanguage`，再通过 `saveGlobalConfig(current => ({ ...current, preferredLanguage: lang }))` 写入全局配置。写入后再次调用 `getResolvedLanguage()`，用于在 `auto` 场景下展示当前实际解析到的语言。最后 `onDone()` 输出 `Language set to ...`，同样以 `display: 'system'` 展示。

语言解析主流程不在本目录，而在 `src/utils/language.ts`。其中 `PreferredLanguage` 是 `'auto' | 'en' | 'zh'`，`ResolvedLanguage` 是 `'en' | 'zh'`。`getResolvedLanguage()` 的优先级注释写得很直接：`GlobalConfig.preferredLanguage → system locale → default 'en'`。系统 locale 的读取在 `src/utils/intl.ts` 的 `getSystemLocaleLanguage()`，它通过 `Intl.DateTimeFormat().resolvedOptions().locale` 和 `Intl.Locale(locale).language` 得到语言子标签，并做了进程级缓存。

全局配置字段定义在 `src/utils/config.ts` 的 `GlobalConfig` 类型中，字段为 `preferredLanguage?: 'auto' | 'en' | 'zh'`。这说明 `/lang` 的设置是持久化配置，而不是只影响当前命令调用。

## 推荐阅读顺序

建议先读 `src/commands/lang/index.ts`，用它理解 `/lang` 在命令系统中的声明方式：命令名、类型、参数提示、立即执行和懒加载入口都在这里。

然后读 `src/commands/lang/lang.ts`，这是本目录的核心。重点看三个分支：无参数查询、非法参数提示、合法参数写入。这个文件足够短，可以一次读完。

接着读 `src/utils/language.ts`，理解 `/lang auto` 的真实含义。这里会看到语言偏好和实际生效语言是两个概念：`PreferredLanguage` 可以是 `auto`，但 `ResolvedLanguage` 只能是 `en` 或 `zh`。

再读 `src/utils/intl.ts` 中的 `getSystemLocaleLanguage()`，了解系统语言从哪里来，以及为什么 locale 结果会被缓存。这个函数不是 `/lang` 专属，但它决定了 auto 模式的判断依据。

最后读 `src/commands.ts` 中 `lang` 的 import 和 `COMMANDS()` 数组位置，理解它如何进入全局 slash command 列表。想继续追踪执行链时，可以再看 `src/types/command.ts` 里的 `Command`、`LocalJSXCommandOnDone`、`LocalJSXCommandCall` 类型。

## 常见误区

第一个误区是把 `src/commands/lang` 当成完整 i18n 目录。根据当前片段推断，它只负责 `/lang` 命令，不包含翻译表、文案选择器或 UI 国际化框架。依据是目录下只有 `index.ts` 和 `lang.ts`，并且实现只读写 `preferredLanguage`。

第二个误区是认为 `/lang auto` 会支持任意系统语言。当前 `getResolvedLanguage()` 只把系统语言子标签等于 `zh` 的情况解析为中文，其余都返回英文。因此日文、韩文、法文等系统 locale 在这里都会落到 `en`。

第三个误区是认为 `lang.ts` 会立即刷新所有已渲染 UI。它只是保存全局配置并输出一条系统消息。至于其他组件是否实时读取 `getResolvedLanguage()`、是否需要重新渲染，要看各自调用点；本目录本身没有广播事件或全局状态同步逻辑。

第四个误区是忽略 `immediate: true`。这个标记说明 `/lang` 属于即时本地操作，适合做设置切换，不应该被理解为一个会发给模型生成回复的 prompt command。

第五个误区是把 `type: 'local-jsx'` 理解为一定会渲染 React UI。`local-jsx` 的 `call()` 可以返回 `React.ReactNode`，但 `/lang` 当前返回的是 `null`，只通过 `onDone()` 结束命令并显示系统文本。
