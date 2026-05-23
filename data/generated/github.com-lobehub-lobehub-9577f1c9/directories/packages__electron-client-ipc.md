# 目录：packages/electron-client-ipc

## 它负责什么

`packages/electron-client-ipc` 是 LobeHub 桌面端里连接 Electron `main process` 与前端 `renderer process` 的共享 IPC 客户端包。根据当前片段推断，它不是业务功能实现目录，而是“通信契约 + renderer 调用入口”的薄层：一边对接 `apps/desktop/src/main/controllers/` 中由 `ControllerModule`、`IpcMethod` 暴露的主进程能力，另一边给 `src/services/electron/`、前端 store 或 feature 层提供类型安全的调用对象。

这个目录的核心价值在于把 Electron IPC 的调用方式从业务代码里收拢出来。业务层不应直接拼接 channel、直接访问 Electron 原生 IPC，也不应感知主进程 controller 的底层注册细节，而是通过类似 `ensureElectronIpc()` 得到的客户端对象调用 `ipc.someGroup.someMethod(params)`。其中 `someGroup` 通常对应主进程 controller 的 `groupName`，`someMethod` 对应被 `@IpcMethod()` 装饰的方法。

从桌面开发说明看，新桌面功能的类型定义会放在 `packages/electron-client-ipc/src/types.ts`，然后主进程 controller 和 renderer service 共同引用这些类型。这说明该包承担的是跨进程边界上的公共协议层：参数、返回值、错误结构、可调用方法形状，以及客户端代理的导出。

需要说明的是，当前可读取片段未能展开目标目录本身，因此以下目录地图对具体文件名的判断以已读取到的 desktop 指南、仓库约定和 Electron IPC 常见分层为依据；涉及未验证文件时会标注“根据当前片段推断”。

## 直接子目录地图

根据当前片段推断，`packages/electron-client-ipc` 应该是一个较小的 package，重点不在复杂子目录树，而在 `src/` 下的协议和客户端入口。

`src/` 是主要源码目录。它大概率承载 IPC client 的创建逻辑、导出入口、共享类型，以及可能存在的工具函数。这个目录应优先被理解为“renderer 侧访问 Electron 主进程能力的 SDK”，而不是 Electron 主进程实现。

`src/types.ts` 是已经在桌面开发说明中明确出现的关键文件，用于定义跨进程传递的数据结构，例如新功能的 `SomeParams`、`SomeResult`。这些类型会被主进程 controller 和前端 service 双方共享，避免 IPC 两侧协议漂移。

根据当前片段推断，包根部还应包含 `package.json`、`tsconfig.json` 或构建配置文件，用来声明包名、入口、类型产物和 monorepo 内部依赖。这些文件的角色是包级工程配置，不是理解业务主流程的重点。

如果目录下存在测试目录，例如 `__tests__/`、`tests/` 或 `vitest` 相关文件，它们更可能验证 IPC client 的代理生成、类型导出或 channel 调用行为，而不是验证具体桌面业务能力。具体功能 controller 的测试通常会落在 `apps/desktop/src/main/controllers/__tests__/`。

## 关键入口

首要入口是 `packages/electron-client-ipc/src/types.ts`。它定义 Electron IPC 边界上可传递的数据模型，是读懂这个包的第一站。新增桌面能力时，若需要 renderer 与 main 共享参数或返回结构，通常先在这里补类型，再分别在主进程 controller 与 renderer service 中使用。

根据当前片段推断，`packages/electron-client-ipc/src/index.ts` 很可能是包的公共导出入口，负责向外暴露 IPC client、类型、工具函数或统一的 client schema。阅读时应关注它导出了什么，而不是只看内部实现。这个文件能回答“业务代码真正能从该包拿到哪些能力”。

另一个关键入口是 renderer 侧使用点，而不是包内文件本身。桌面指南给出的调用方式是 `src/services/electron/` 中通过 `ensureElectronIpc()` 获取 IPC 对象，再调用 `ipc.newFeature.doSomething(params)`。因此 `src/services/electron/` 是理解该包如何被业务层消费的重要邻近上下文。

主进程侧入口在 `apps/desktop/src/main/controllers/` 和 `apps/desktop/src/main/controllers/registry.ts`。controller 通过 `static override readonly groupName = 'newFeature'` 定义分组名，通过 `@IpcMethod()` 暴露方法。`packages/electron-client-ipc` 的客户端形状需要与这些分组和方法保持一致。

## 主流程位置

新增或理解一条 IPC 主流程时，可以按“renderer 调用、client 转发、main controller 执行、结果返回”的链路看。

第一步在前端业务层或 service 层。页面、store 或 feature 不直接调用 Electron 原生 API，而是进入 `src/services/electron/`。service 通过 `ensureElectronIpc()` 拿到 Electron IPC client，并调用类似 `ipc.groupName.methodName(params)` 的方法。

第二步进入 `packages/electron-client-ipc`。这里负责把类型安全的对象方法调用转换成 Electron IPC 请求。根据当前片段推断，这个包可能隐藏了 channel 命名、参数序列化、invoke 调用和返回值类型约束。对业务代码来说，它表现为一个普通异步 TypeScript API。

第三步到主进程 controller。`apps/desktop/src/main/controllers/` 下的 controller 类继承 `ControllerModule`，通过 `groupName` 建立 IPC 分组，通过 `@IpcMethod()` 标记可被 renderer 调用的方法。`registry.ts` 负责注册这些 controller，让主进程知道哪些 IPC 方法可用。

第四步返回 renderer。controller 方法执行完主进程能力，例如文件系统、窗口、菜单、系统能力或本地资源访问后，结果按 `packages/electron-client-ipc/src/types.ts` 中定义的返回结构传回前端。前端 service 再把结果交给 store 或 UI 处理。

因此，`packages/electron-client-ipc` 的主流程位置在链路中间：它不拥有 UI，也不拥有 Electron 原生业务实现，而是保证 renderer 与 main 的协议可发现、可复用、可类型检查。

## 推荐阅读顺序

1. 先读 `packages/electron-client-ipc/src/types.ts`，确认这个包定义了哪些跨进程参数和返回值。读类型时重点关注命名是否按功能域分组，以及哪些类型明显被多个模块共享。

2. 再读 `packages/electron-client-ipc/src/index.ts` 或包的公开导出入口。目标是弄清这个 package 对外暴露了什么：是只导出类型，还是同时导出 IPC client 创建函数、接口声明或常量。

3. 接着看 `src/services/electron/`。这里能看到 renderer 业务层如何消费 IPC client，也能帮助判断某个类型或方法真正服务于哪条用户流程。

4. 然后看 `apps/desktop/src/main/controllers/registry.ts`。这个文件能建立“客户端分组名”与“主进程 controller”之间的整体地图。

5. 最后按需进入 `apps/desktop/src/main/controllers/` 的具体 controller。只有当你要理解某个 IPC 方法背后的真实行为时，才需要展开 controller 内部逻辑；做概览时不需要逐个 controller 细读。

## 常见误区

第一个误区是把 `packages/electron-client-ipc` 当成桌面功能实现目录。它更像 IPC 协议和客户端调用层，真实的系统能力通常在 `apps/desktop/src/main/controllers/` 中实现，前端业务编排通常在 `src/services/electron/`、`src/store/` 或 `src/features/` 中。

第二个误区是只改主进程 controller，不更新共享类型。跨进程调用一旦参数或返回值变化，`packages/electron-client-ipc/src/types.ts` 需要同步表达这个变化，否则 renderer 和 main 之间会形成隐性协议，后续维护成本很高。

第三个误区是绕过 `ensureElectronIpc()` 或包内 client，直接在业务组件里访问 Electron IPC。这样会把 channel 细节泄漏到 UI 层，也削弱类型检查和测试替换能力。

第四个误区是认为 `groupName` 只是 controller 内部命名。它通常会影响 renderer 侧的访问路径，例如 `ipc.newFeature.doSomething()` 中的 `newFeature`，因此命名变化可能是跨层破坏性变更。

第五个误区是把所有桌面相关类型都堆进这个包。只有跨 renderer/main 边界共享的协议类型适合放在这里；纯 UI 状态、纯 controller 内部实现类型、数据库模型或服务内部临时结构，应尽量留在各自模块内。
