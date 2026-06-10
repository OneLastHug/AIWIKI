# 文件：src/entrypoints/cli.tsx

## 一句话定位
这是整个 CLI 的**最外层启动入口**。它先处理最轻量、最早期的启动分支，再决定是直接进入某个专用子模式，还是加载完整的 `main.jsx` 进入常规交互式 CLI。

## 它暴露/定义了什么
文件本身**不导出公共 API**，只定义了一个顶层 `async function main()` 并在末尾直接 `await main()`。它还在启动早期做了几件全局级别的事：加载 `performanceShim`、补 `globalThis.MACRO`、处理 `CLAUDE_CODE_FORCE_INTERACTIVE`、关闭 `COREPACK_ENABLE_AUTO_PIN`、以及在远程环境下调整 `NODE_OPTIONS`。

## 谁调用它
根据当前片段推断，它主要由两类入口调用：

1. `build.ts` 把它作为 `Bun.build({ entrypoints: ['src/entrypoints/cli.tsx'] })` 的构建入口。
2. `scripts/dev.ts` 直接以 `bun run ... src/entrypoints/cli.tsx` 启动开发模式，并注入 `-d` define 和 `--feature` 标志。

从运行角度看，用户直接执行 CLI、安装后的可执行文件、以及构建产物 `dist/cli.js`，最终都会落到这里。

## 它调用谁
它是一个典型的“分流器”，会按命令行参数动态导入很多模块，避免不必要的初始化。核心被调用者包括：

- `../utils/startupProfiler.js`
- `../utils/config.js`
- `../main.jsx`
- `../bridge/bridgeMain.js`
- `../daemon/main.js`
- `../daemon/workerRegistry.js`
- `../cli/bg.js`
- `../cli/handlers/templateJobs.js`
- `../environment-runner/main.js`
- `../self-hosted-runner/main.js`
- `../services/acp/entry.js`
- `../utils/earlyInput.js`

另外它还会调用一批辅助模块做权限、政策、工作树、Weixin、Chrome MCP、系统 prompt 等专用路径的初始化。

## 核心流程
它的流程很清晰：先看参数，再决定是否“早退”。

1. 先拦截 `--version`，这是最轻路径，只打印 `MACRO.VERSION`。
2. 对其他参数，先启动 profiling，再处理若干专用入口，比如 `--dump-system-prompt`、`--claude-in-chrome-mcp`、`--chrome-native-host`、`--computer-use-mcp`、`--acp`。
3. 接着处理更高层的业务模式：`weixin`、`--daemon-worker`、`remote-control/rc/remote/sync/bridge`、`daemon`、`autonomy`、`--bg`/`--background`、`ps/logs/attach/kill`、`job/new/list/reply`、`environment-runner`、`self-hosted-runner`、`--tmux + --worktree`。
4. 如果没有命中特殊路径，就修正一些常见参数误用，比如 `--update`/`--upgrade`，并在 `--bare` 时提前设 `CLAUDE_CODE_SIMPLE=1`。
5. 最后才加载 `../main.jsx`，启动完整 Commander CLI 和交互式主流程。

## 关键函数的高层作用
`main()` 是整个文件唯一的核心函数，作用不是“处理业务”，而是**决定业务入口**。它做的是路径分发、启动约束、早期环境准备和性能优化。

几个关键分支可以这样理解：

- `--version`：零依赖快速返回。
- `--dump-system-prompt`：用于导出渲染后的系统提示词，偏评测/实验用途。
- `bridge` 分支：先校验登录、版本、政策，再进入远程控制主逻辑。
- `daemon` / `--bg`：把长驻和后台会话管理集中到统一 daemon 层。
- `autonomy`：只输出状态文本，避免进入完整 CLI。
- 最后进入 `main.jsx`：这是常规交互模式的真正入口。

## 修改风险
这个文件是**高风险入口层**，改动会影响整条启动链。

1. **顺序风险很高**：顶部 import 和环境变量设置有明确先后关系，尤其是 `performanceShim`、`MACRO`、`COREPACK_ENABLE_AUTO_PIN`、`NODE_OPTIONS`。顺序错了会影响后续模块初始化。
2. **分支回退风险**：这里大量使用动态导入和早退，新增分支如果放错位置，可能抢走已有命令，或者让原本应进 `main.jsx` 的请求提前退出。
3. **特性门控风险**：很多路径依赖 `feature()`，改错会导致 build/dev 行为不一致，甚至让某些功能在外部构建中意外暴露。
4. **兼容性风险**：像 `daemon`、`bridge`、`bg`、`job` 这些分支都有历史兼容别名，调整参数匹配规则很容易破坏旧命令。
5. **启动性能风险**：这里的核心目标之一是“尽量晚加载”。不必要的静态 import 会直接拉慢 `--version` 之外的所有启动路径。
