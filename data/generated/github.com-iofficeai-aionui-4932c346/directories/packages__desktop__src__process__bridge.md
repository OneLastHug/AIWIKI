# 目录：packages/desktop/src/process/bridge

## 它负责什么

`packages/desktop/src/process/bridge` 从命名和项目架构位置看，属于 Electron 桌面端的主进程侧桥接层。它位于 `packages/desktop/src/process/` 下，因此职责边界应当偏向 main process：连接主进程能力、预加载层暴露的 IPC 通道、以及渲染进程发起的业务请求。根据当前片段推断，这个目录不是 UI 层，也不应直接操作 DOM；它更可能负责把窗口、文件系统、系统能力、应用服务等主进程能力整理成稳定的调用入口。

在项目约束中，`packages/desktop/src/process/` 是主进程区域，不能混入 DOM API；`packages/desktop/src/renderer/` 是渲染进程区域，不能直接使用 Node.js API。跨进程通信必须通过 `packages/desktop/src/preload/` 的 IPC bridge。因此，这里的 `bridge` 可以理解为“主进程服务和跨进程协议之间的适配层”：它不一定是最终业务实现本身，而是把外部请求转发到正确的主进程模块，并统一处理注册、参数、返回值和错误边界。

需要说明的是，当前读取目标目录时未能获得实际文件列表，因此下面关于结构和流程的判断属于“根据当前片段推断”。依据主要来自目标路径命名、项目的 Electron 分层约束、以及 `process`、`preload`、`renderer` 三类目录的职责说明。

## 直接子目录地图

由于当前片段无法确认 `packages/desktop/src/process/bridge` 的真实子目录列表，这里只给出地图式理解，而不逐项解释叶子文件。

如果该目录存在子目录，常见角色通常会按桥接对象或业务域拆分，例如窗口相关 bridge、应用配置 bridge、文件或会话相关 bridge、AI 服务相关 bridge、系统能力 bridge 等。每个子目录通常承担一类 IPC 通道或一组相近的主进程调用，避免把所有 handler 注册逻辑堆在一个入口文件里。

如果该目录没有子目录，而是以少量文件组织，则它更可能是一个集中式 bridge 层：一个入口文件负责注册所有通道，其他文件按常量、类型、handler、工具函数拆开。无论是哪种形式，阅读时都不应把它当成普通业务目录，而应把它看成“跨进程调用面”的组织位置。

## 关键入口

关键入口应优先寻找 `index.ts`、`register.ts`、`handlers.ts`、`ipc.ts`、`main.ts` 这类文件名，或者导出 `registerBridge`、`registerIpcHandlers`、`setupBridge`、`initBridge` 一类函数的位置。根据当前片段推断，这些入口会在主进程启动链路中被调用，负责把 Electron 的 `ipcMain.handle`、`ipcMain.on` 或项目封装后的 IPC 注册 API 绑定起来。

另一个关键入口在相邻层：`packages/desktop/src/preload/`。预加载层通常会通过 `contextBridge` 暴露受控 API 给渲染进程，而这里的 `process/bridge` 负责接住这些 API 背后的主进程请求。也就是说，学习这个目录不能只看它自己，还要顺着同名 channel、方法名或类型定义去找 `preload` 里的暴露接口，以及 `renderer` 侧调用这些接口的地方。

还应关注通道名称常量和类型定义。如果目录里存在 `types.ts`、`constants.ts`、`channels.ts` 或类似文件，它们通常比具体实现更适合作为入口，因为它们定义了 bridge 对外承诺的接口形状。

## 主流程位置

主流程大致可以按四段理解。

第一段是渲染进程触发。用户在 `packages/desktop/src/renderer/` 中操作界面，组件或 service 调用预加载层暴露的 API。由于渲染进程不能直接使用 Node.js API，这一步应该只调用安全暴露的方法，而不是直接访问文件系统、进程、系统窗口等能力。

第二段是 `packages/desktop/src/preload/` 转译。预加载脚本通过 `contextBridge` 或项目封装的 bridge API，把渲染侧方法映射成 IPC 消息。这里通常会定义渲染进程可见的 API 名称、参数结构和返回 Promise 的方式。

第三段就是 `packages/desktop/src/process/bridge` 的核心位置。它在主进程启动时注册 IPC handler，接收来自 preload 的 channel 请求，然后进行参数检查、上下文组装、错误处理和业务分发。这里应当是“协议到服务”的边界，而不是任意业务逻辑都塞入的地方。

第四段是主进程业务模块执行。bridge handler 最终会调用 `packages/desktop/src/process/` 下其他模块，例如窗口管理、配置管理、数据库、文件访问、应用生命周期、AI 服务或系统集成。执行结果再通过 IPC 返回给 preload，最后回到 renderer。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/process/bridge` 下最像入口的文件，例如 `index.ts` 或注册函数所在文件，确认它向主进程启动链路暴露了什么。

2. 再读通道常量和类型文件，例如 `channels.ts`、`types.ts`、`constants.ts`。这一步的目标不是看实现，而是弄清楚 bridge 对外提供哪些能力、哪些调用是异步的、哪些返回值会跨进程传递。

3. 顺着每个 handler 调用的 service 或 manager，进入 `packages/desktop/src/process/` 的相邻模块。这里要区分“bridge 只是转发”还是“bridge 自己包含业务判断”。

4. 回到 `packages/desktop/src/preload/`，查找同名 API 或 channel，理解它如何暴露给渲染进程。

5. 最后在 `packages/desktop/src/renderer/` 中搜索这些 API 的使用点，确认真实用户路径从哪个界面触发。

这个顺序的好处是先建立调用面，再追业务实现，最后回看 UI 使用场景。对于 overview 级别学习，不建议一开始逐文件阅读所有 handler。

## 常见误区

第一个误区是把 `bridge` 当作普通业务层。它更像边界层，重点是跨进程通信、能力暴露和调用分发。复杂业务如果长期堆在这里，会让 IPC 层和业务层耦合过重。

第二个误区是只看主进程 handler，不看 `preload`。在 Electron 架构中，真正的公开 API 往往由 preload 决定；主进程 bridge 只是实现这些 API 的一端。只看一侧，很容易误判哪些能力真的能被 renderer 使用。

第三个误区是忽略进程边界。`packages/desktop/src/process/bridge` 处在主进程侧，可以使用主进程能力，但不能引入 DOM 依赖；渲染侧则相反，不能绕过 preload 直接碰 Node.js 或 Electron main API。

第四个误区是把 IPC channel 当作内部函数随意改名。channel 名称、参数结构和返回值往往同时影响 `process`、`preload`、`renderer` 三层，修改时需要同步检查调用链和类型定义。

第五个误区是忽略安全边界。bridge 层如果接收来自 renderer 的路径、命令、配置或外部输入，应进行校验和收敛，不能把主进程能力无条件透传给界面层。
