# 文件：src/index.ts

## 一句话定位

`src/index.ts` 是 OpenClaw 包根入口的“分流器”：当它作为命令行主模块运行时，启动 legacy CLI；当它被外部以库形式导入时，转而暴露 `src/library.ts` 中整理过的公共能力。

## 它暴露/定义了什么

这个文件主要定义三类内容。

第一类是面向库消费者的导出绑定，例如 `applyTemplate`、`createDefaultDeps`、`loadConfig`、`ensurePortAvailable`、`monitorWebChannel`、`runExec`、`waitForever` 等。它们的真实实现不在本文件，而是在非主模块路径下通过 `await import("./library.js")` 一次性赋值。`src/library.ts` 再继续从配置、会话、端口、进程执行、web channel runtime 等模块聚合或懒加载实现。

第二类是 CLI 兼容入口 `runLegacyCliEntry(argv, deps?)`。它接受 argv 和可注入的 `runCli` 依赖，默认动态加载 `src/cli/run-main.ts` 的 `runCli`，再把控制权交给完整 CLI 框架。

第三类是主进程错误处理逻辑：安装未处理 rejection 处理器，监听 `uncaughtException`，格式化 CLI 失败输出，运行 fatal hooks，恢复终端状态，并以明确 exit code 退出。

## 谁调用它

根据当前片段推断，它有两个主要调用场景，依据是 `package.json` 中 `"main": "dist/index.js"`、`exports["."]` 指向 `dist/index.js`，以及脚本/测试中大量引用 `dist/index.js`、`openclaw.mjs`。

库调用者通过包根 `openclaw` 导入时，会落到编译后的 `dist/index.js`，也就是此文件的产物。此时 `isMainModule` 判断为 false，本文件只装载并暴露 `library.ts` 的 API。

命令行或部署脚本可能直接执行 `node dist/index.js ...`，容器脚本和若干测试也把 `dist/index.js` 当作 CLI 入口。正常 npm bin 则先进入 `openclaw.mjs`，它负责 Node 版本、compile cache、源码/发布环境启动选择等包装逻辑；最终命令执行链会进入构建后的 CLI 入口。根据当前片段推断，`openclaw.mjs` 与 `dist/index.js` 是并列入口关系：前者是发布 bin wrapper，后者是包根/直接 node 入口。

测试层面，`src/index.test.ts` 直接导入 `applyTemplate` 和 `runLegacyCliEntry`，验证包根导出和 legacy CLI 注入调用。

## 它调用谁

CLI 主路径调用 `src/infra/is-main.ts` 判断当前模块是否为主模块；调用 `src/terminal/restore.ts` 恢复终端；调用 `src/infra/unhandled-rejections.ts` 安装和判定全局异常；调用 `src/cli/failure-output.ts`、`src/infra/errors.ts` 生成用户可读错误；调用 `src/infra/fatal-error-hooks.ts` 追加崩溃后清理或诊断信息；最后动态导入 `src/cli/run-main.ts` 执行 `runCli`。

库路径调用 `src/library.ts`。`library.ts` 自身再聚合 `src/config/config.ts`、`src/config/sessions/*`、`src/infra/ports.ts`、`src/process/exec.ts`、`src/plugins/runtime/runtime-web-channel-plugin.ts` 等模块，并对较重 runtime 采用懒加载。

## 核心流程

文件启动后先计算 `isMain`。如果不是主模块，说明它被当成包根库导入，于是动态导入 `./library.js`，把一组 `export let` 绑定赋值为库 API。这里的设计让 CLI 主路径保持轻量，避免运行命令时提前加载库侧较重依赖。

如果是主模块，文件动态导入终端恢复模块，安装未处理 promise rejection 的全局处理器，然后注册 `uncaughtException`。异常若已被内部机制处理，直接返回；若属于可忽略的 benign 异常，只输出 warning 并继续；否则用统一 CLI failure formatter 打印错误、运行 fatal hooks、恢复终端并退出。

最后调用 `runLegacyCliEntry(process.argv)`。如果 CLI promise reject，catch 分支同样走统一失败输出、fatal hooks、终端恢复和 `process.exit(1)`。因此本文件本身不解析命令、不注册子命令，只负责入口分流和顶层失败兜底。

## 关键函数的高层作用

`loadLegacyCliDeps()` 是很薄的动态导入辅助函数，只负责从 `src/cli/run-main.ts` 取出 `runCli`，避免包根入口静态绑定完整 CLI。

`runLegacyCliEntry()` 是可测试、可注入的 CLI 入口包装。默认情况下它加载真实 `runCli`；测试或特殊调用可以传入 deps 替换实现，从而验证 argv 传递和入口行为，而不必启动完整命令系统。

`isMainModule(...)` 的结果是全文件的关键分叉点。它决定本文件是“库导出聚合器”还是“CLI 进程入口”。这对启动性能和副作用隔离都很重要：库导入不应安装全局错误处理器，CLI 启动不应提前加载库消费者才需要的 API。

`uncaughtException` handler 是主路径的安全网。它把未知异常转成一致的 CLI 失败输出，并确保终端状态恢复，避免 TUI、stdin 或 ANSI 状态残留。

## 修改风险

最大风险是破坏 CLI 启动路径。`src/index.ts` 位于包根导出和直接执行入口交界处，静态新增重量级导入可能影响启动性能、内存预算，甚至触发构建脚本中的 CLI bootstrap 检查。若修改导入方式，需要同时关注 `scripts/check-cli-bootstrap-imports.mjs`、启动基准和发布包检查。

第二个风险是库导出兼容性。`package.json` 把包根导出指向 `dist/index.js`，外部代码可能依赖这些命名导出。删除、改名或把 `export let` 改成行为不同的导出形式，可能影响现有消费者；新增公共导出也属于 API 表面变化，应确认是否需要文档和类型输出同步。

第三个风险是全局错误处理副作用。错误处理器只应在 `isMain` 为 true 时安装；如果误放到库路径，会让导入 OpenClaw 的宿主进程被 OpenClaw 接管异常和退出行为。反过来，如果 CLI 路径漏装处理器，崩溃输出、fatal hooks、终端恢复都会退化。

第四个风险是入口判定。`openclaw.mjs`、`dist/index.js`、源码测试、容器脚本都可能以不同 argv 形态运行。改动 `isMain` 相关调用时，需要验证直接 `node dist/index.js ...`、包根 import、测试注入 `runLegacyCliEntry`、以及发布 bin wrapper 场景不会互相串扰。
