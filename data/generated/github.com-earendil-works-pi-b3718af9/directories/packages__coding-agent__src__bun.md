# 子系统：packages/coding-agent/src/bun

## 解决什么问题

`packages/coding-agent/src/bun` 目标目录在当前可访问的仓库片段中不存在：请求给出的仓库根目录应为 `/data/project/AIWIKI/data/repos/github.com-earendil-works-pi-b3718af9/source`，但当前执行环境实际落在 `/data`，并且未能读取到 `packages/coding-agent`、`packages/coding-agent/src` 或 `packages/coding-agent/src/bun`。因此，下面只能基于目录命名、仓库规则片段和邻近说明做有限推断，不能当作源码级确定结论。

根据当前片段推断，`packages/coding-agent/src/bun` 很可能是 `coding-agent` 包里专门面向 Bun 运行时的适配层。它要解决的问题通常不是核心 agent 推理逻辑，而是让同一套 `coding-agent` 能在 Bun 环境中启动、访问文件系统、处理进程 IO、加载打包产物或提供 Bun binary 入口。仓库说明中多次区分 Node package 和 Bun binary 的发布、烟测与交互启动，说明 Bun 是该项目的一等分发目标之一；因此该目录很可能承担“运行时差异隔离”的职责，使上层 agent 代码不需要到处判断当前是在 Node 还是 Bun。

## 相关目录和文件

证据不足，当前无法列出 `packages/coding-agent/src/bun` 的真实文件。根据仓库说明可确认的相关路径包括：

`packages/coding-agent`：`coding-agent` 包的主体目录，包含 agent 运行逻辑、测试、示例和发布相关配置。

`packages/coding-agent/test/suite/`：用于 `coding-agent` 的套件测试，要求使用 `test/suite/harness.ts` 和 faux provider，避免真实 provider API、密钥或付费调用。若 `src/bun` 改动影响启动、IO 或 provider 调用路径，相关回归测试应放在这里的合适位置。

`packages/coding-agent/test/suite/regressions/`： issue 级回归测试目录，命名格式为 `<issue-number>-<short-slug>.test.ts`。如果 Bun 入口修复的是具体 issue，应在这里补测试。

`packages/coding-agent/npm-shrinkwrap.json`：发布或依赖变更可能影响的 shrinkwrap 文件。仓库规则说明它需要通过 `node scripts/generate-coding-agent-shrinkwrap.mjs` 再生成和校验。

`packages/coding-agent/examples`：受根配置约束的 TypeScript 代码区域之一。若 Bun 入口暴露给示例或 CLI 用法，示例代码也可能体现调用方式。

## 核心对象

由于源码不可读，不能确认真实导出的函数、类或常量名称。根据当前片段推断，这个目录可能围绕以下几类对象组织：

第一类是 Bun 启动入口。它可能负责接收 CLI 参数、初始化运行上下文、绑定 stdin/stdout/stderr，并把控制权交给通用的 `coding-agent` 主流程。这个入口不应包含太多业务逻辑，否则 Node 与 Bun 分发会产生行为漂移。

第二类是 Bun runtime adapter。它可能封装 `Bun.file`、`Bun.write`、进程环境、信号处理、路径解析、可执行文件定位等能力，并向核心 agent 提供统一接口。理想状态下，上层只依赖抽象接口，而不是直接依赖 Bun 全局对象。

第三类是 Bun binary 或 bundle 支撑代码。仓库发布流程中有 `/tmp/pi-local-release/bun/pi --help`、`--version`、`--list-models`、`-p "Say exactly: ok"` 和交互模式烟测，说明 Bun 产物需要独立启动、显示帮助、列模型、发送 prompt 并进入 TUI 或交互循环。`src/bun` 很可能参与这些行为的打包入口或运行时补丁。

第四类是兼容性边界对象。Bun 与 Node 在 streams、TTY、子进程、fetch、文件句柄、module resolution 等方面存在差异，该目录可能集中处理这些差异，避免污染核心 agent 模块。

## 运行流程

根据当前片段推断，Bun 运行流程大致是：

用户执行 Bun 分发产物，例如 `bun/pi`。Bun 入口读取命令行参数，识别 `--help`、`--version`、`--list-models`、`-p` 和无参数交互模式等调用形式。随后它初始化运行时环境，包括 provider 配置、工作目录、终端能力、日志或诊断输出。对于一次性 prompt 模式，入口把 prompt 交给核心 agent 流程，等待模型响应并把结果写到 stdout；对于交互模式，入口启动 TUI 或 REPL 风格循环，持续处理用户输入、agent 状态和输出渲染。

在这个过程中，`src/bun` 预计不会直接实现模型选择、工具调用策略、代码编辑策略或测试 harness。它更可能把 Bun 的进程、文件、网络和终端能力转换成核心层可消费的接口。核心层完成 agent 的主要决策，Bun 层只保证同样的命令在 Bun binary 下可运行、可退出、可被发布脚本烟测。

## 上下游依赖

上游依赖方面，`src/bun` 很可能直接依赖 Bun runtime 提供的全局 API、CLI 参数、环境变量和文件系统能力。它也可能依赖包内通用入口、配置解析、模型注册、provider 抽象、日志系统和交互 UI 模块。因为仓库规则强调不要猜外部 API 类型，真实修改时应先检查 `node_modules` 与包内类型定义。

下游依赖方面，Bun 发布产物和 release smoke test 会依赖该目录的行为。仓库 release 流程明确要求同时烟测 Node package 和 Bun binary，包括 help、version、model listing、一次性 prompt 和交互启动。也就是说，`src/bun` 的变更不仅影响开发时运行，还直接影响发布是否可用。若它改变 CLI 参数解析或 stdout/stderr 行为，下游脚本、测试和用户自动化都可能受影响。

测试依赖方面，非 e2e 测试应优先使用仓库规定的测试入口，避免直接运行完整 vitest 套件。对 `coding-agent` 的 issue 回归应走 `packages/coding-agent/test/suite/` 的 harness 和 faux provider，不能引入真实 API 调用。

## 修改时最容易踩的坑

最容易踩的坑是把 Bun 适配层写成业务层。Bun 目录应该隔离运行时差异，而不是复制一套 agent 主逻辑；否则 Node 与 Bun 的行为会逐渐不一致，发布烟测也只能覆盖一部分问题。

第二个坑是依赖 Bun 与 Node streams 行为完全一致。TTY、stdin backpressure、退出码、信号处理和交互渲染都可能不同。尤其是交互模式需要在 tmux 或真实终端里验证，而不是只看一次性命令输出。

第三个坑是引入 TypeScript 非 erasable 语法。仓库规则要求 `packages/*/src` 等区域只能使用 Node strip-only mode 可擦除语法，不能用 `enum`、parameter properties、`namespace`、`import =` 等需要 JS emit 的语法。

第四个坑是动态导入或 inline imports。仓库规则明确禁止 `await import()`、`import("pkg").Type` 和动态类型导入，应使用顶层 imports。

第五个坑是发布相关文件处理不完整。若修改依赖、lockfile 或 shrinkwrap，需要按仓库规则用 `npm install --ignore-scripts`、`npm install --package-lock-only --ignore-scripts` 或 `node scripts/generate-coding-agent-shrinkwrap.mjs`，不能手工改元数据。

第六个坑是误用真实 provider。`packages/coding-agent/test/suite/` 的测试应使用 faux provider，不能因为 Bun 启动路径需要“真实跑通”就接入真实模型服务。

## 推荐阅读顺序

建议先读 `packages/coding-agent/package.json`，确认 Bun 入口、bin 字段、scripts、依赖和打包命令。然后读 `packages/coding-agent/src/bun` 的入口文件，找到它如何把 Bun runtime 接入通用 agent 主流程。接着读它调用的相邻核心入口，例如通用 CLI、agent runner、配置加载和 provider 选择模块，理解 Bun 层与核心层的边界。

之后阅读 `packages/coding-agent/test/suite/harness.ts` 和相关 suite 测试，确认项目期望如何模拟 provider、文件系统和交互行为。若改动与具体 issue 有关，再读 `packages/coding-agent/test/suite/regressions/` 中相近的回归用例。最后阅读发布脚本和 changelog 规则，尤其是 Bun binary smoke test 的要求，因为这个目录的最终质量通常要通过发布产物启动来验证。
