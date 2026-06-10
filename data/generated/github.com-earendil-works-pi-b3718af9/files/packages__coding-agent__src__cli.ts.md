# 文件：packages/coding-agent/src/cli.ts

## 一句话定位

`packages/coding-agent/src/cli.ts` 是 `coding-agent` 包的命令行进程入口文件：它不承载业务逻辑，而是在真正进入 `main.ts` 之前完成进程级初始化、运行时标识设置和 HTTP 全局调度器预配置。

## 它暴露/定义了什么

这个文件没有显式导出函数、类或类型。它是一个带有 shebang 的可执行入口脚本：

```ts
#!/usr/bin/env node
```

文件顶层直接执行初始化逻辑，包括：

- 从 `config.ts` 读取 `APP_NAME`；
- 从 `core/http-dispatcher.ts` 读取 `configureHttpDispatcher`；
- 从 `main.ts` 读取 `main`；
- 设置 `process.title`；
- 设置环境变量 `PI_CODING_AGENT`；
- 覆盖 `process.emitWarning`；
- 调用 `configureHttpDispatcher()`；
- 最后调用 `main(process.argv.slice(2))`。

因此它定义的是“进程启动协议”，不是可复用 API。

## 谁调用它

根据当前片段推断，它由 Node.js 作为 CLI 可执行文件调用。依据是文件首行 `#!/usr/bin/env node`，以及末尾直接消费 `process.argv.slice(2)`。

更上层的调用来源通常会是 `packages/coding-agent/package.json` 里的 `bin` 字段、构建后的可执行文件、仓库内的启动脚本或发布包中的命令入口。但当前读取到的片段没有包含 `package.json`，所以不能确认具体命令名。可以确定的是：一旦用户在终端执行对应 CLI 命令，运行链路会进入这个文件，然后转交给 `main.ts`。

## 它调用谁

它直接调用两个内部模块：

- `configureHttpDispatcher`，来自 `packages/coding-agent/src/core/http-dispatcher.ts`；
- `main`，来自 `packages/coding-agent/src/main.ts`。

它还直接操作 Node.js 进程对象：

- `process.title = APP_NAME` 用于设置进程标题；
- `process.env.PI_CODING_AGENT = "true"` 用于给当前进程及其子调用链打运行环境标记；
- `process.emitWarning = (() => {}) as typeof process.emitWarning` 用于屏蔽 Node 运行时 warning 输出；
- `process.argv.slice(2)` 用于提取用户传入的 CLI 参数。

## 核心流程

启动流程很短，但顺序重要。

第一步，加载配置和主入口。`APP_NAME` 决定进程标题，`main` 是后续真正的 CLI/agent 主流程，`configureHttpDispatcher` 是网络层准备动作。

第二步，设置进程标识。`process.title` 让系统进程列表中显示应用名；`PI_CODING_AGENT` 让下游代码可以判断当前运行在 coding-agent CLI 环境内。这个环境变量可能会影响日志、埋点、子进程、配置加载或行为分支，具体影响范围需要继续查看调用该环境变量的位置。

第三步，屏蔽 warning。文件把 `process.emitWarning` 替换为空函数，这意味着 Node 或依赖库发出的运行时 warning 不会正常打印。这里明显偏向 CLI 用户体验，避免第三方库 warning 干扰终端界面或输出协议，但也会降低问题可见性。

第四步，配置 HTTP dispatcher。注释说明这是为 `undici` 设置 global dispatcher，且要在 provider SDK 发起请求前完成。这里还有一个关键约束：运行时 settings 会在 `SettingsManager` 加载全局/项目设置后再应用一次。也就是说，这里的调用更像“默认网络调度器预热”，不是最终完整配置。

第五步，调用 `main(process.argv.slice(2))`。`cli.ts` 不解析参数，只把除 `node` 和脚本路径之外的原始参数列表交给 `main.ts`。参数语义、模式选择、错误处理、交互式启动等都应在 `main.ts` 或它调用的模块中完成。

## 关键函数的高层作用

`main` 是真正的应用入口。根据当前片段和注释“Uses main.ts with AgentSession and new mode modules”推断，它负责组织 CLI 的主要生命周期：解析参数、加载设置、创建或恢复 agent session、选择交互模式或一次性执行模式，并处理退出状态。`cli.ts` 对它保持薄封装，只传入参数数组。

`configureHttpDispatcher` 负责配置 HTTP 请求底层调度。注释点名 `undici`，说明项目可能依赖 Node/undici 的全局 dispatcher 行为，也可能让不同 provider SDK 共享代理、超时、证书或连接池策略。它必须早于 provider SDK 网络请求执行，否则部分请求可能绕过统一网络配置。

`APP_NAME` 是进程级显示名称来源。它不是业务逻辑，但影响 CLI 在系统层面的可识别性，例如进程列表、终端工具或调试输出。

`process.emitWarning` 覆盖是一个强副作用初始化。它不是普通辅助函数，而是全局行为修改：所有后续模块通过 `process.emitWarning` 发出的 warning 都会被吞掉。

## 修改风险

这个文件小，但修改风险集中在“启动顺序”和“全局副作用”。

首先，`configureHttpDispatcher()` 的位置不能随意后移。注释明确要求它在 provider SDK 发出请求前执行。如果把它移到 `main` 之后、异步初始化之后，或放进某个只在部分模式执行的分支里，可能导致代理、证书、连接池或网络策略不一致。

其次，`process.env.PI_CODING_AGENT` 是跨模块运行标识。删除或改名可能影响依赖该环境变量判断运行环境的代码。由于当前片段没有展示使用点，修改前应全仓搜索 `PI_CODING_AGENT`。

第三，屏蔽 `process.emitWarning` 会隐藏依赖 warning。保留它有助于终端输出稳定，移除它有助于调试。这里属于产品行为取舍，不能只按“warning 应该显示”或“输出应该干净”单点判断。若要修改，建议确认交互式 TUI、非交互模式、测试快照和 CI 输出是否依赖当前静默行为。

第四，`main(process.argv.slice(2))` 是参数边界。不要在 `cli.ts` 中提前解析、重写或过滤参数，除非这是全局启动协议的一部分。否则会把参数语义分散到多个入口层，增加测试和兼容风险。

第五，这个文件是 CLI 顶层入口，任何抛错、异步等待、导入副作用变化都会影响所有命令模式。适合保持极薄：只做进程级初始化和委派，业务分支应继续放在 `main.ts` 及其下游模块中。
