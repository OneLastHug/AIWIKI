# 目录：apps/cli

## 它负责什么

`apps/cli` 是 LobeHub 的命令行客户端目录，核心职责是把终端命令映射到后端服务能力，形成一套可直接在 shell 中使用的操作界面。根据当前片段推断，它不仅提供登录、退出、补全、帮助文档、状态查询这类基础命令，还覆盖了更偏业务的能力，例如 agent、bot、generate、file、kb、memory、message、model、plugin、provider、search、skill、task、topic、user、migrate 等。

这个目录的特点是“命令壳 + 本地状态 + 远端调用”三层合一：命令层负责参数解析和输出格式，本地层负责 settings、认证、daemon 进程和日志，远端层通过 `tRPC` / HTTP 客户端访问服务接口。它不是单纯的脚本集合，而是一个完整可发布的 CLI 包。

## 直接子目录地图

`apps/cli` 下从目录角色看，主要是这几块：

- `src/`：主源码目录，CLI 的逻辑主体都在这里。
- `e2e/`：端到端测试，覆盖 agent、doc、file、generate、kb、memory、message、model、plugin、provider、search、skill、topic 等命令行为。
- `man/`：已生成的手册页资源，发布时随包一起带上。
- `src/commands/`：命令注册中心，按功能拆成多个命令模块。
- `src/commands/generate/`、`src/commands/task/`、`src/commands/migrate/`：这几个子目录是命令的第二层拆分，说明这些命令内部还有明显的子流程。
- `src/api/`：对外服务访问层，承接 CLI 到后端的请求。
- `src/auth/`：登录态、凭证、token 解析与刷新。
- `src/daemon/`：守护进程的 pid、状态、日志和启动停止管理。
- `src/settings/`：本地配置文件读写与 URL 解析。
- `src/tools/`、`src/utils/`、`src/constants/`、`src/man/`：公共能力、格式化输出、常量和 man 页生成相关逻辑。

## 关键入口

这个目录的对外入口非常集中：

- `src/index.ts` 是真正的启动点，直接调用 `createProgram().parseAsync(...)`，并统一处理异常退出。
- `src/program.ts` 是命令注册总线，创建 `commander` 的 `Command` 实例，设置 `name('lh')`、描述和版本，然后逐个挂载各类命令。
- `package.json` 里的 `bin` 把 `lh`、`lobe`、`lobehub` 都指向同一个产物 `./dist/index.js`，说明三个命令名共享同一套实现。
- `src/man/generate.ts` 负责生成手册页，对应 `man/man1/lh.1`、`man/man1/lobe.1`、`man/man1/lobehub.1`。
- `src/commands/completion.ts` 是 shell 补全入口，用户在安装后会依赖它获得上下文感知补全。

## 主流程位置

如果要看“CLI 怎么跑起来”，主流程基本按这个顺序理解：

1. `src/index.ts` 进入程序并执行 `parseAsync`。
2. `src/program.ts` 构建顶层命令树，注册所有命令。
3. 各命令模块在 `src/commands/*` 中完成实际动作，大多数命令会通过 `src/api/client.ts` 获取 tRPC 客户端，再去调用后端。
4. 需要登录态时，走 `src/auth/*`；需要读写本地配置时，走 `src/settings/index.ts`。
5. 需要后台常驻能力时，走 `src/daemon/manager.ts`，它负责 PID 文件、状态文件、日志轮转和守护进程启动/停止。
6. 输出层统一使用 `src/utils/format.ts`、`src/utils/logger.ts` 之类工具，保证表格、JSON、时间、人类可读文本的风格一致。

从结构上看，真正的“业务主干”集中在 `src/commands/`。其中 `task/` 和 `generate/` 是两个最明显的复合命令目录：前者继续拆成 `checkpoint`、`dep`、`doc`、`lifecycle`、`review`、`topic` 等任务子命令，后者拆成 `text`、`image`、`video`、`tts`、`asr` 等生成类型。根据当前片段推断，这两个目录代表 CLI 里最复杂、最常被扩展的流程。

## 推荐阅读顺序

1. 先看 `src/index.ts`，确认启动和错误退出方式。
2. 再看 `src/program.ts`，把顶层命令树在脑子里建立起来。
3. 接着看 `src/settings/index.ts` 和 `src/auth/*`，理解本地配置与登录态如何影响后续命令。
4. 再看 `src/api/client.ts`、`src/api/http.ts`，了解所有命令最终如何访问服务。
5. 然后挑一个复合命令入口看，比如 `src/commands/task/index.ts` 或 `src/commands/generate/index.ts`，理解“命令壳 + 子命令拆分”的写法。
6. 最后看 `src/daemon/manager.ts`、`src/tools/*`、`src/utils/*`，补齐后台运行、工具适配和输出格式化这几块共用底座。

## 常见误区

- 把 `lh`、`lobe`、`lobehub` 当成三个不同程序。实际上它们共享同一个入口和实现。
- 只改了某个命令文件，却忘了它必须在 `src/program.ts` 中完成注册，新命令不会自动出现在 CLI 中。
- 把 `src/commands/generate/index.ts` 里的 `generationId` 和 `asyncTaskId` 混为一谈。这里的状态查询和下载流程依赖两个不同标识，传错参数会直接报错。
- 忽略 `src/settings/index.ts` 的优先级规则。根据当前片段推断，环境变量会覆盖本地 settings，默认值再排在最后。
- 以为 `src/daemon/manager.ts` 只是简单进程启动。实际上它还维护 `~/.lobehub` 下的 pid、status 和 log 文件，属于 CLI 的运行时基础设施。
- 把 `man/` 当作手写源码。它更像发布产物，真正应维护的是 `src/man/generate.ts` 和相关命令定义。
- 只看 `src/commands/*` 不看 `src/utils/*`。这个 CLI 的输出体验很依赖格式化和日志工具，很多用户可见行为其实在工具层统一处理。
