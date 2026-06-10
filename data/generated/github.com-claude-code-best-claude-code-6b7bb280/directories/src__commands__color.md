# 目录：src/commands/color

## 它负责什么

`src/commands/color` 负责处理 `/color` 命令，也就是在当前会话里设置提示栏或代理会话颜色。这个目录的职责非常单一：接收用户输入的颜色参数，校验是否允许设置，随后把颜色写入会话持久化存储，并同步更新当前 AppState，让界面立刻生效。

从代码形态看，这不是一个“大功能目录”，而是一个典型的局部命令实现目录。它既承担命令元数据的导出，也承担真正的命令执行逻辑。根据当前片段推断，它主要服务于 REPL 里的本地状态切换，不依赖 shell、文件系统或 MCP 之类的外部上下文。

## 直接子目录地图

这个目录下没有子目录。`src/commands/color` 里只有两个文件：

- `src/commands/color/index.ts`
- `src/commands/color/color.ts`

所以这里的“目录地图”其实就是“两层结构”：

- `index.ts` 负责命令描述和懒加载入口
- `color.ts` 负责实际执行逻辑

这种拆法很常见，目的是让主命令注册阶段尽量轻量，真正的实现延后加载，减少启动时的模块成本。

## 关键入口

真正的目录入口是 `src/commands/color/index.ts`。它导出一个 `Command` 对象，核心字段包括：

- `name: 'color'`
- `description: 'Set the prompt bar color for this session'`
- `immediate: true`
- `argumentHint: '<color|default>'`
- `load: () => import('./color.js')`

这里最关键的是 `load()`。它说明 `/color` 命令是懒加载的，只有真正触发时才会导入 `src/commands/color/color.ts`。

第二个关键入口是 `src/commands/color/color.ts` 里的 `call()`。这才是命令执行主体，接受三个参数：

- `onDone`：把系统消息回写给界面
- `context`：包含 `setAppState` 等运行时上下文
- `args`：用户输入的参数字符串

## 主流程位置

主流程主要集中在 `src/commands/color/color.ts` 的 `call()` 内部，可以按顺序理解为四段：

1. 先判断是否是 swarm teammate。  
   如果 `isTeammate()` 为真，直接拒绝修改颜色，并提示颜色由 team leader 分配。

2. 再检查参数是否为空。  
   如果用户没有输入颜色，就返回可选颜色列表。这里颜色列表来自 `AGENT_COLORS`，说明这个命令没有自己维护颜色字典，而是复用了工具层定义。

3. 然后处理重置分支。  
   当输入命中 `RESET_ALIASES`，也就是 `default`、`reset`、`none`、`gray`、`grey` 之一时，会把颜色恢复到默认状态。这里会：
   - 读取当前 session id
   - 读取 transcript 路径
   - 调用 `saveAgentColor(sessionId, 'default', fullPath)` 持久化
   - 通过 `setAppState` 把 `standaloneAgentContext.color` 清空
   - 回传“已重置”为系统消息

4. 最后处理普通颜色设置。  
   如果参数不在 `AGENT_COLORS` 内，就报“无效颜色”；如果合法，就：
   - 调用 `saveAgentColor(...)` 持久化到 transcript
   - 更新 `AppState` 中的 `standaloneAgentContext.color`
   - 通过 `onDone()` 反馈“Session color set to ...”

从主链路看，`saveAgentColor()` 是持久化中心，`setAppState()` 是即时生效中心，`onDone()` 是 UI 回执中心。三者组合起来，构成这个命令完整的“写入-刷新-反馈”流程。

在目录外的挂载点上，`src/commands.ts` 把 `color` 注册进命令表，并放入 `REMOTE_SAFE_COMMANDS`。这说明它被视作远程模式下也安全的本地状态命令，属于只影响 TUI 状态的那一类。

## 推荐阅读顺序

1. 先看 `src/commands/color/index.ts`，理解它作为命令元数据入口是怎么被懒加载挂起来的。
2. 再看 `src/commands/color/color.ts`，按参数校验、重置分支、普通设置分支三段读。
3. 然后回到 `src/commands.ts`，看 `color` 是如何被纳入全局命令表，以及为什么它属于 `REMOTE_SAFE_COMMANDS`。
4. 最后补看 `src/utils/sessionStorage.ts`、`src/utils/teammate.ts`、`src/bootstrap/state.ts`，把持久化、队友判断和 session id 的来源串起来。

## 常见误区

1. 把 `index.ts` 当成业务实现。  
   这里真正干活的是 `color.ts`，`index.ts` 只是命令描述和懒加载壳。

2. 以为颜色只是临时 UI 状态。  
   实际上它会写入 transcript 相关存储，目的是跨会话保留，重启后仍能恢复。

3. 只看 `AGENT_COLORS`，忽略重置别名。  
   `default`、`reset`、`none`、`gray`、`grey` 都会走“恢复默认”逻辑，不是非法输入。

4. 忽略 teammate 限制。  
   在 swarm 场景下，这个命令不是所有人都能改，普通会话和团队协作会走不同规则。

5. 只看界面更新，不看持久化。  
   这里的正确理解是“双写”：一份写到会话存储，一份写到当前 AppState，缺一层就会出现重启后状态不一致的问题。

6. 把它误认为需要命令行解析器单独处理。  
   这个目录本身只提供命令对象和执行函数，真正的路由和注册在 `src/commands.ts`。
