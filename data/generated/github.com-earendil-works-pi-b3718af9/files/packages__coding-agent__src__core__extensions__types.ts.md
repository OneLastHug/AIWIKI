# 文件：packages/coding-agent/src/core/extensions/types.ts

## 一句话定位
这是 coding-agent 扩展系统的“总契约”文件：它不承载具体业务逻辑，而是集中定义扩展能看到什么上下文、能订阅什么事件、能注册什么能力，以及运行时如何把这些能力接到 `loader.ts`、`runner.ts`、`wrapper.ts` 上。

## 它暴露/定义了什么
它定义了三层东西。第一层是扩展面向用户界面的上下文能力 `ExtensionUIContext`、`ExtensionContext`、`ExtensionCommandContext`，包括弹窗、状态栏、编辑器、主题、会话控制等。第二层是事件和结果类型，覆盖项目信任、资源发现、会话生命周期、模型选择、输入、工具调用与工具结果等。第三层是扩展注册与运行时结构，例如 `ExtensionAPI`、`ExtensionFactory`、`ExtensionRuntime`、`ExtensionRuntimeState`、`ExtensionActions`、`LoadExtensionsResult`，以及工具定义 `ToolDefinition`、命令 `RegisteredCommand`、消息渲染器 `MessageRenderer`、provider 配置 `ProviderConfig`。

文件里真正有少量实现的只有 `defineTool()` 和一组类型守卫，比如 `isToolCallEventType()`、`isBashToolResult()` 等，其余基本都是数据结构和接口。

## 谁调用它
根据当前片段推断，直接调用者主要是 `loader.ts`、`runner.ts`、`wrapper.ts`、`index.ts`：`index.ts` 负责把这些类型重新导出给外部扩展入口；`loader.ts` 依赖 `ExtensionAPI`、`ExtensionRuntime`、`ToolDefinition` 等来构造和装载扩展；`runner.ts` 需要这些事件和 action 接口来把运行时绑定到真正的会话/模型/工具执行流程；`wrapper.ts` 则利用工具定义和结果类型包裹已有工具。除此之外，扩展作者在编写外部模块时也会直接依赖这些类型来实现 `pi.registerTool()`、`pi.on()`、`ctx.ui.*` 之类的能力。

## 它调用谁
这个文件几乎不“调用”别的模块，反而是反向依赖的汇聚点。唯一明显的运行时代码是 `defineTool()` 直接返回传入对象，`isToolCallEventType()` 和各类 `isXxxToolResult()` 只做字段判断。其余都是从 `pi-agent-core`、`pi-ai`、`pi-tui`、`typebox` 以及仓库内部的 `event-bus.ts`、`session-manager.ts`、`system-prompt.ts`、`tools/index.ts`、`compaction/index.ts` 等处导入类型，作为扩展系统的公共边界。

## 核心流程
整个扩展流程可以理解为四步：先由 `loader.ts` 发现并加载扩展，生成带注册表的 `Extension` 和 `ExtensionRuntime`；再由 `runner.ts` 把 runtime 绑定到真实上下文，把 `sendMessage`、`setModel`、`registerProvider` 等 action 变成可执行操作；随后扩展通过 `ExtensionAPI` 订阅事件、注册工具/命令/快捷键/flag/渲染器，并通过 `ExtensionContext` 或 `ExtensionCommandContext` 在事件回调和命令处理中操作应用；最后，`index.ts` 将这些契约统一导出，形成外部扩展的稳定入口。

事件流也很清晰：会话、输入、工具调用、模型切换、用户 bash 等先被包装成 `ExtensionEvent`，再分发给对应 handler，handler 可返回结果类型去修改、阻断或补充系统状态。

## 关键函数的高层作用
`defineTool()` 的作用不是增强功能，而是保住 TypeScript 推导：当工具定义被单独赋值或穿过数组时，它避免参数类型被宽化成 `unknown`。  
`isToolCallEventType()` 是工具调用事件的通用类型守卫，解决 `CustomToolCallEvent.toolName: string` 与内建工具字面量冲突的问题。  
`isBashToolResult()`、`isReadToolResult()` 这类守卫用于在 `ToolResultEvent` 联合类型上快速收窄分支，方便后续渲染或处理不同工具结果。

## 修改风险
这里的风险主要是“契约漂移”。一旦改动事件字段、返回结构或 `ExtensionAPI` 方法签名，`loader.ts`、`runner.ts`、`wrapper.ts` 以及所有外部扩展都会同步受影响，且常常是编译期报错和运行期行为变化同时出现。另一个风险是新增事件或工具类型时，只补了类型没补分发和处理链，导致看似可用、实际没人消费。还有一个隐性风险是 `ExtensionRuntimeState` 与 `ExtensionActions` 的职责边界，改错位置会让加载期和运行期的行为互相耦合，破坏“先注册、后绑定”的设计。
