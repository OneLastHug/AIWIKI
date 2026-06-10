# 目录：src/commands/context

## 它负责什么
这个目录负责 `/context` 命令，也就是“查看当前上下文占用情况”的那条路径。它的目标不是简单统计 UI 里当前看到的消息，而是尽量还原“模型实际会看到的上下文视图”。因此它会先做和主请求链路一致的预处理，再计算 token 分布、模型余额、记忆文件、MCP 工具、技能、Agent、系统提示词等内容，最后分别输出给交互式界面和非交互式命令行。

从职责上看，这里是一个很典型的“双模式命令目录”：同一个命令名 `context`，在终端交互会话里走富 UI，在非交互会话里走纯文本输出。

## 直接子目录地图
根据当前片段推断，这里没有更深的子目录，只有三个文件，层级很浅，职责也很清楚。

- `src/commands/context/index.ts`：命令门面层，决定当前会话该启用哪个实现。
- `src/commands/context/context.tsx`：交互式实现，负责渲染彩色可视化结果。
- `src/commands/context/context-noninteractive.ts`：非交互式实现，负责输出 markdown 风格的文本表格。

这个目录本身不再继续拆分子模块，真正的“逻辑重心”在这三个文件和它们依赖的公共分析函数上。

## 关键入口
最直接的入口是 `src/commands/context/index.ts`。这里导出了两个同名命令对象：

- `context`
- `contextNonInteractive`

它们都叫 `context`，但通过 `isEnabled()`、`isHidden` 和 `supportsNonInteractive` 区分适用场景。`index.ts` 通过 `getIsNonInteractiveSession()` 判断当前会话类型，再把请求导向 `./context.js` 或 `./context-noninteractive.js`。

另一个关键入口在 `src/commands.ts`。这里把 `context` 和 `contextNonInteractive` 统一注册进全局命令表。也就是说，这个目录并不是自己挂到 CLI 根入口上的，而是先进入命令注册中心，再由主 CLI 解析系统分发。根据当前片段推断，这是整个命令系统的标准接入方式。

## 主流程位置
交互式主流程在 `src/commands/context/context.tsx` 的 `call()`：

1. 取出 `messages`、`getAppState()`、`mainLoopModel` 和 `tools`
2. 通过 `getMessagesAfterCompactBoundary()` 先裁掉压缩边界之后不该算进去的内容
3. 如果启用了 `CONTEXT_COLLAPSE`，再通过 `projectView()` 贴近主请求链路里的上下文折叠视图
4. 调用 `microcompactMessages()`，把消息压到更接近真正发送给 API 的形态
5. 调用 `analyzeContextUsage()` 生成上下文分析数据
6. 用 `ContextVisualization` 生成可视化结果，再通过 `renderToAnsiString()` 转成 ANSI 字符串
7. 最后交给 `onDone()` 输出

非交互式主流程在 `src/commands/context/context-noninteractive.ts`：

1. `collectContextData()` 先复用同样的上下文预处理
2. 再调用 `analyzeContextUsage()` 拿到统一的数据结构
3. `call()` 把结果交给 `formatContextAsMarkdownTable()`，输出为文本表格

两条路径共享同一套数据采集逻辑，但展示层不同。这是这个目录最重要的设计点。

## 推荐阅读顺序
如果你想快速理解这个目录，建议按这个顺序看：

1. `src/commands/context/index.ts`  
   先看它如何按会话类型分流。

2. `src/commands/context/context.tsx`  
   再看交互式路径如何把“上下文”变成可视化结果。

3. `src/commands/context/context-noninteractive.ts`  
   然后看非交互模式如何复用同一分析数据并改成文本输出。

4. `src/commands.ts`  
   最后补上它在全局命令注册中的位置，理解它是怎么被 CLI 接住的。

如果要继续向下追源码，再看 `src/utils/analyzeContext.ts`、`src/services/compact/microCompact.ts`、`src/utils/messages.ts`、`src/services/contextCollapse/operations.js` 会更完整。

## 常见误区
- 不要把它当成“当前 UI 消息数量统计”。它会做边界裁剪、微压缩，必要时还会走 `CONTEXT_COLLAPSE`，所以结果更接近 API 视角。
- 不要把交互式和非交互式输出混为一谈。前者是 ANSI 可视化网格，后者是 markdown 表格，面向的消费场景不同。
- 不要忽略 feature flag。`CONTEXT_COLLAPSE` 开关会改变上下文视图和统计口径。
- 不要假设这个目录自己完成注册。真正的入口分发在 `src/commands.ts`，这里更多是“命令实现 + 分流门面”。
- 不要把 `context.tsx` 理解成纯展示层。它实际上包含了完整的数据采集前置流程，只是最后再渲染出来。
