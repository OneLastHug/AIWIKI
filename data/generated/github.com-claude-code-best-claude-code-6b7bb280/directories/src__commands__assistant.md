# 目录：src/commands/assistant

## 它负责什么

`src/commands/assistant` 是这套 CLI 里“assistant / KAIROS”相关命令的入口目录，负责把 `claude assistant` 这条命令接入到命令系统里，并处理它的可见性、安装引导和基础交互逻辑。根据当前片段推断，这个目录并不是一个“大功能树”，而是一个很薄的命令包装层，真正的会话发现、远程接入和 REPL 启动流程主要落在 `src/main.tsx`。

它的职责可以概括成三层：

1. 命令注册层：把 `assistant` 作为本地 JSX 命令导出。
2. 可用性控制层：通过 build-time feature 和运行时 GrowthBook 开关决定是否显示。
3. 交互层：提供安装向导，以及“首次启用 / 再次切换面板”的基础行为。

## 直接子目录地图

这个目录下**没有直接子目录**，只有 3 个文件：

- `src/commands/assistant/index.ts`：命令定义与导出。
- `src/commands/assistant/gate.ts`：运行时可见性门控。
- `src/commands/assistant/assistant.tsx`：安装向导与命令主体实现。

如果只看目录结构，这里更像一个小型命令模块，而不是一个包含多级子系统的功能区。

## 关键入口

最关键的入口是 `src/commands/assistant/index.ts`。它导出一个 `Command` 对象，名字就是 `assistant`，描述为 “Open the Kairos assistant panel”，并通过 `load: () => import('./assistant.js')` 延迟加载主体实现。这个文件的作用是把命令挂到 CLI 的命令表里，同时保持首屏加载轻量。

第二个入口是 `src/commands/assistant/gate.ts`。这里的 `isAssistantEnabled()` 决定 `/assistant` 是否对用户可见：先检查 `feature('KAIROS')`，再检查 `getFeatureValue_CACHED_MAY_BE_STALE('tengu_kairos_assistant', false)`。也就是说，这个命令同时受构建期开关和远程 kill switch 控制。

第三个入口是 `src/commands/assistant/assistant.tsx`。它导出了三个直接可用的能力：

- `computeDefaultInstallDir()`：计算 assistant daemon 的默认安装目录，优先用 git root，否则回退到当前目录。
- `NewInstallWizard()`：当没有可用会话时，给用户一个启动 daemon 的向导。
- `call()`：真正的 `/assistant` 命令处理函数，控制首次激活和后续的面板显隐切换。

## 主流程位置

主流程并不只在这个目录里，核心分发主要在 `src/main.tsx`。

从当前片段看，`main.tsx` 做了几件关键事：

1. 预加载 assistant 相关模块  
   顶部通过条件导入拿到 `assistantModule` 和 `kairosGate`，避免不必要的加载。

2. 解析 `claude assistant [sessionId]`  
   在早期 argv 处理里，如果检测到 `assistant`，会把它缓存到 `_pendingAssistantChat`，再从原始参数中剥离。

3. 进入远程会话附着流程  
   当 `feature('KAIROS')` 开启且存在 `_pendingAssistantChat` 时，会动态导入 `sessionDiscovery`，查找可用 bridge session。  
   - 没有 session：打开安装向导 `launchAssistantInstallWizard(root)`  
   - 只有一个 session：直接附着  
   - 多个 session：走 `launchAssistantSessionChooser(root, ...)`

4. 进入 viewer-only REPL  
   选定 session 后，会刷新 OAuth、构造 remote session config，并把 REPL 作为只读 viewer client 启动。这里还会设置 `kairosActive`、`userMsgOptIn`、`isRemoteMode`，确保 brief / 远程模式的行为一致。

5. 命令注册兜底  
   `program.command('assistant [sessionId]')` 只是一个兜底 stub。注释里明确说明，真正的 argv 重写应该已经在前面消费掉参数；如果这里还能到达，通常意味着 root flag 先出现了，CLI 会打印用法而不是继续执行。

另外，`src/commands/assistant/assistant.tsx` 里的 `call()` 也很重要：第一次执行会把 KAIROS 激活，并把 `assistantPanelVisible` 设为 true；后续执行则在“隐藏 / 打开面板”之间切换。这说明本目录既管命令，也管一个轻量的 UI 状态开关。

## 推荐阅读顺序

1. 先看 `src/commands/assistant/index.ts`，确认这个命令是怎么注册进系统的。
2. 再看 `src/commands/assistant/gate.ts`，理解它为什么有时会消失。
3. 接着看 `src/commands/assistant/assistant.tsx`，把安装向导和 `call()` 的行为串起来。
4. 最后回到 `src/main.tsx` 中的 `assistant` 分支，理解它如何从命令入口进入远程会话附着、安装引导和 REPL 启动。

## 常见误区

1. 把 `src/commands/assistant` 当成完整的 assistant 子系统。  
   实际上它更像命令适配层，真正的大流程在 `src/main.tsx`。

2. 以为 `/assistant` 只是本地 UI 面板。  
   从主流程看，它还承担了远程 bridge session 的发现、附着和 viewer 模式启动。

3. 忽略双重门控。  
   这里不是只看 `KAIROS` feature，还要看 `tengu_kairos_assistant` 的运行时开关。

4. 把首次激活和后续切换混为一谈。  
   `call()` 里第一次会启用 KAIROS，之后才是面板显隐切换。

5. 漏掉安装向导的角色。  
   当没有可用 session 时，`NewInstallWizard()` 会引导用户启动 daemon，而不是直接报错退出。

6. 误以为目录里一定有 `sessionDiscovery.ts`。  
   当前目录扫描只看到 3 个文件，但 `main.tsx` 里确实动态导入了 `./assistant/sessionDiscovery.js`。根据当前片段推断，这个模块可能在别处生成、裁剪后未纳入本次扫描，或者属于未展开的伴随文件。
