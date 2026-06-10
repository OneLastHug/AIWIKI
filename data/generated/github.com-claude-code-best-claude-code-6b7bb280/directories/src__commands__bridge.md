# 目录：src/commands/bridge

## 它负责什么

`src/commands/bridge` 是 Remote Control / Bridge 命令的本地入口目录，负责把用户在 CLI 里触发的 `remote-control` / `rc` 命令接到桥接模式上。根据当前片段推断，这个目录本身不承载桥接协议实现，而是做两件事：一是把命令注册进命令系统，二是提供命令执行时的交互界面与前置校验。

它的职责可以概括为“开关 + 门面”：
1. 在功能允许时暴露 `remote-control` 命令。
2. 在命令执行时检查桥接前置条件。
3. 把状态写入 `AppState`，让后续的 REPL 桥接流程继续接管。
4. 在已连接时给出断开、展示二维码、继续等交互选项。

## 直接子目录地图

根据当前片段推断，这个目录下没有直接子目录，只有两个文件：

- `src/commands/bridge/index.ts`
  - 命令元数据与启用条件。
  - 对外暴露 `remote-control` 命令定义，并提供别名 `rc`。
- `src/commands/bridge/bridge.tsx`
  - 真正的本地 JSX 命令实现。
  - 处理连接、断开、提示、二维码展示和前置检查。

也就是说，这里是一个很小的命令目录，结构清晰，没有拆出更细的子模块。

## 关键入口

这里最重要的入口有两个。

首先是 `src/commands/bridge/index.ts`。它定义了命令对象 `bridge`，其中最关键的是：

- `type: 'local-jsx'`：说明这是一个本地 JSX/交互式命令。
- `name: 'remote-control'`，`aliases: ['rc']`：用户可通过主命令名或别名进入。
- `immediate: true`：说明它需要尽快执行，不走普通延迟流程。
- `load: () => import('./bridge.js')`：真正逻辑是延迟加载到 `src/commands/bridge/bridge.tsx` 对应的模块。

其次是 `src/commands/bridge/bridge.tsx` 里的 `export async function call(...)`。这是命令执行的实际入口，它读取参数里的名称，然后渲染 `BridgeToggle` 组件。后面的所有流程都从这里展开。

## 主流程位置

主流程基本都集中在 `src/commands/bridge/bridge.tsx`。

第一段主流程在 `BridgeToggle` 中。它在挂载后立即判断当前是否已经处于桥接连接状态：

- 如果已经连上，或者已经启用了双向桥接，就进入断开确认对话框。
- 如果还没连上，就先走 `checkBridgePrerequisites()`。
- 前置检查通过后，再判断是否需要显示首次远程调用提示。
- 如果不需要提示，就把 `replBridgeEnabled`、`replBridgeExplicit`、`replBridgeOutboundOnly`、`replBridgeInitialName` 写进 `AppState`，把后续桥接初始化交给 `REPL.tsx` 中的 `useReplBridge`。

第二段主流程在 `BridgeDisconnectDialog` 中。这里负责已连接场景下的交互：

- 展示当前会话 URL。
- 可选生成二维码。
- 允许用户选择断开、显示/隐藏二维码、继续。
- 通过 `useKeybindings` 处理上下选择与确认。

第三段主流程是 `checkBridgePrerequisites()`。它是这个目录里最像“守门员”的函数，按顺序检查：

- 组织策略是否允许 `allow_remote_control`。
- 当前桥接功能是否被禁用。
- 版本是否满足要求，且会根据 `isEnvLessBridgeEnabled()`、`KAIROS`、assistant mode 分支决定走 v1 还是 v2 的版本检查。
- 是否已有桥接访问令牌。
- 全部通过后才允许继续。

## 推荐阅读顺序

建议按这个顺序读，最省力：

1. 先看 `src/commands/bridge/index.ts`  
   先确认这个命令在系统里怎么被挂载、什么时候可见、怎么懒加载。

2. 再看 `src/commands/bridge/bridge.tsx` 顶部注释和 `call()`  
   先建立整体认识：这是一个把用户动作转成桥接状态切换的命令。

3. 接着看 `BridgeToggle`  
   这里能看出“首次开启”“已连接时重复执行”“状态写入 AppState”三种路径。

4. 然后看 `checkBridgePrerequisites()`  
   这是桥接能否启动的关键门槛，很多异常都在这里被提前拦掉。

5. 最后看 `BridgeDisconnectDialog`  
   这部分是已连接状态下的补充交互，理解成本低，但能补全用户体验。

## 常见误区

1. 容易把这个目录当成桥接协议实现目录。  
   其实它更像命令层入口，真正的桥接生命周期是在 `REPL.tsx`、`src/bridge/*` 等位置继续推进的。

2. 容易忽略 `index.ts` 的作用。  
   它虽然短，但决定了命令是否可见、是否启用、以及 `remote-control` 和 `rc` 这两个入口是否都成立。

3. 容易把“命令执行”误认为“立即完成连接”。  
   这里的命令多数只是改状态、触发提示，真正连桥接、建会话、开 WebSocket 不是在这个目录里完成的。

4. 容易漏掉前置检查的分支差异。  
   `checkBridgePrerequisites()` 不只是一个版本号判断，它还会受策略、token、环境型桥接开关和 assistant mode 影响。

5. 容易误解已连接时的行为。  
   再次执行 `remote-control` 并不总是“重新连接”，很多时候会进入断开确认对话框，用户可以选择继续而不是切换状态。
