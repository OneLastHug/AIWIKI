# 文件：packages/desktop/src/process/index.ts
## 一句话定位
这是 `desktop` 主进程的初始化入口文件，负责在 Electron 主程序真正启动业务前，先把进程级环境、存储、桥接和 i18n 这些基础设施准备好。根据当前片段推断，它更像一个“开机引导器”，本身不承载业务逻辑。

## 它暴露/定义了什么
文件对外主要暴露一个函数：`initializeProcess()`。此外，文件顶部还包含一组必须尽早执行的副作用导入：`register-electron`、`configureChromium`、`initBridge`、`i18n`。  
其中 `initializeProcess()` 目前只显式做了一件事：调用 `initStorage()`，并用 `performance.now()` 打点记录初始化耗时。

## 谁调用它
明确的调用方是 `packages/desktop/src/index.ts`。在那里，`initializeProcess()` 在应用完成基础准备后、启动后端 `aioncore` 之前被调用。  
也就是说，它处在主进程启动链路的中段，前面已经做过单实例锁、路径修正、日志/Sentry 等准备，后面才进入后端启动和窗口/协议处理。

## 它调用谁
这个文件直接调用或触发的对象主要有三类：
1. `electron` 的 `app`：用于判断 `app.isPackaged`。
2. `./utils/initStorage`：核心初始化动作，负责把持久化存储准备好。
3. 副作用模块：`@/common/platform/register-electron`、`@process/utils/configureChromium`、`./utils/initBridge`、`./services/i18n`。这些不是显式函数调用，但会在 import 阶段执行注册、配置或初始化。

## 核心流程
启动时先执行最前面的副作用导入，确保 Electron 平台适配、Chromium 参数、IPC 桥接和主进程国际化尽早生效。接着读取 `app.isPackaged`，如果是打包后的正式环境，就设置 `process.env.PREBUILDS_ONLY = '1'`，避免 `node-gyp-build` 误用开发环境里的 `build/Release/` 二进制。  
之后对外导出 `initializeProcess()`：它先记录一个起始时间，再调用 `initStorage()` 完成本地存储初始化，最后打印耗时标记 `initStorage`。从 `src/index.ts` 的调用顺序看，这一步完成后才允许继续启动后端服务。

## 关键函数的高层作用
`initializeProcess()` 是这里唯一有行为的公开函数，作用是“完成主进程的早期基础设施初始化，并提供一个可观测的耗时点”。  
`initStorage()` 虽然不在本文件实现，但从命名和调用位置看，它是这里最关键的依赖，负责把后续主进程和后端都要用的数据目录、配置文件或兼容迁移准备好。  
`PREBUILDS_ONLY` 的设置也是关键逻辑，它不是业务功能，而是环境隔离策略，避免发布环境加载错架构原生模块。

## 修改风险
这个文件的风险主要不在代码量，而在初始化顺序。任何 import 顺序变动，都可能让 `app.getPath('userData')`、IPC 注册、日志配置或 i18n 提前/滞后执行，导致 Electron 行为异常。  
第二个风险是环境分支：`app.isPackaged` 下设置 `PREBUILDS_ONLY` 会直接影响原生模块加载，改错会让正式包在不同平台上启动失败。  
第三个风险是 `initializeProcess()` 与 `src/index.ts` 的耦合很强；如果这里新增耗时步骤，可能推迟后端启动，甚至影响首次启动、迁移、单实例处理和恢复逻辑。
