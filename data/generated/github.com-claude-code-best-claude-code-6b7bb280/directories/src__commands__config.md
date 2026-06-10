# 目录：src/commands/config

## 它负责什么
`src/commands/config` 是一个很薄的命令适配目录，职责不是“解析配置文件”，而是把用户触发的 `/config` 命令接到统一的设置面板上。根据当前片段推断，它的核心作用是打开 `Settings` UI，并把默认页签固定到 `Config`，因此它更像是“配置入口按钮”，而不是独立的配置逻辑实现。

这个目录还给了命令一个别名：`settings`。也就是说，用户既可以通过 `config`，也可以通过 `settings` 触发同一套入口。

## 直接子目录地图
这个目录下面没有更深的子目录，结构非常简单，只有两个文件：

- `src/commands/config/index.ts`：命令元数据与懒加载入口
- `src/commands/config/config.tsx`：本地 JSX 命令的实际渲染函数

从目录层级看，它属于典型的“命令壳”结构，所有真正的界面内容都委托给上层共享组件。

## 关键入口
真正的入口是 `src/commands/config/index.ts`。它导出一个 `Command` 对象，关键字段有：

- `name: 'config'`
- `aliases: ['settings']`
- `type: 'local-jsx'`
- `description: 'Open config panel'`
- `load: () => import('./config.js')`

这里的 `load()` 表示按需加载，不在启动时把整个面板逻辑都塞进主程序。命令被触发后，才去加载 `config.tsx` 对应模块。

实际渲染逻辑在 `src/commands/config/config.tsx`，它导出 `call`，返回的是：

- `<Settings onClose={onDone} context={context} defaultTab="Config" />`

这说明它并不自己画 UI，而是直接复用 `src/components/Settings/Settings.js` 里的统一设置组件。

## 主流程位置
这个目录的主流程不是单独跑出来的，而是嵌在整个命令系统里。链路大致是：

1. `src/commands.ts` 汇总所有命令定义
2. 用户在 REPL 或相关入口里触发 `/config`
3. 命令系统通过 `findCommand(...)` 找到 `src/commands/config/index.ts` 导出的定义
4. `load()` 懒加载 `config.js`
5. `call(onDone, context, args)` 被执行
6. `Settings` 面板渲染，并打开 `Config` 页签
7. 关闭时通过 `onDone` 返回上一层

从 `src/types/command.ts` 可以看出，这类命令属于 `local-jsx`，其特点就是在本地渲染 Ink/React 风格界面，而不是简单向模型发送文本。也因此，这一目录的主逻辑入口实际上是“命令注册 + 面板复用”，不是复杂业务分支。

## 推荐阅读顺序
1. 先看 `src/commands/config/index.ts`，确认这个命令如何注册、别名是什么、是否懒加载。
2. 再看 `src/commands/config/config.tsx`，确认它实际打开的是哪个 UI、默认页签是什么。
3. 然后看 `src/types/command.ts` 里 `LocalJSXCommandCall` 和 `local-jsx` 相关定义，理解这种命令的执行模型。
4. 最后回到 `src/commands.ts`，看命令是如何被统一收集、查找和分发的。

## 常见误区
- 容易把这个目录误认为“配置中心实现”，其实它只是入口壳，真正的配置界面在 `src/components/Settings/Settings.js`。
- 容易忽略别名 `settings`。这个目录的用户入口不只有 `/config`。
- 容易把 `load()` 当成普通导入。这里是延迟加载，目的是避免启动时就加载整个设置面板及其依赖。
- 容易和其他带“config”字样的模块混淆。仓库里还有很多配置相关路径，例如 `src/utils/config.ts`、`src/services/mcp/config.ts`，但它们处理的是全局设置、MCP 配置或运行时配置，不是这个命令目录本身。
- 容易误判它是非交互命令。实际上它是 `local-jsx`，会拉起本地 UI，而不是纯文本命令。
