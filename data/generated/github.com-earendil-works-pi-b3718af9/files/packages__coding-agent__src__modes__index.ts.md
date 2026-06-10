# 文件：packages/coding-agent/src/modes/index.ts
## 一句话定位
这是 `coding-agent` 的模式入口汇总文件，作用不是实现业务逻辑，而是把交互模式、打印模式、RPC 模式及其相关类型统一从一个位置导出，给上层提供稳定、简洁的导入面。

## 它暴露/定义了什么
这个文件本身几乎不定义新逻辑，核心是一个 barrel export。它对外暴露了 `InteractiveMode`、`InteractiveModeOptions`、`runPrintMode`、`PrintModeOptions`、`RpcClient`、`RpcClientOptions`、`RpcEventListener`、`ModelInfo`、`runRpcMode`，以及一组 RPC 协议类型：`RpcCommand`、`RpcExtensionUIRequest`、`RpcExtensionUIResponse`、`RpcResponse`、`RpcSessionState`。

从结构上看，它把不同运行形态分成三类：交互式终端模式、一次性打印模式、以及面向 RPC/扩展集成的模式与协议类型。

## 谁调用它
根据当前片段推断，调用方主要是 `packages/coding-agent` 内部的上层入口、命令分发层或其他需要统一拿到“模式能力”的模块。因为这里做的是聚合导出，所以最常见的消费方式是上层只 import `modes/index.ts`，而不直接依赖更深的子目录路径。  
当前片段里没有看到直接引用者，所以这部分是基于文件职责的推断，依据是它只做导出汇总，不含独立行为。

## 它调用谁
它不执行运行时调用，但会在编译层面把符号转出到这些模块：`./interactive/interactive-mode.ts`、`./print-mode.ts`、`./rpc/rpc-client.ts`、`./rpc/rpc-mode.ts`、`./rpc/rpc-types.ts`。  
也就是说，真正的实现都在这些子模块里，这个文件只是把它们拼成统一入口。

## 核心流程
核心流程非常简单：先按照模式类别把实现和类型拆到各自文件里，再由 `index.ts` 统一重导出。这样上层代码只需要记住一个入口，就能拿到全部模式能力。  
这种结构通常服务两个目标：一是降低 import 路径的复杂度，二是把对外 API 收口，方便后续调整内部目录结构而不影响调用方。

## 关键函数的高层作用
`runPrintMode` 负责一次性输出/批处理式的运行路径，适合非交互场景。`runRpcMode` 负责 RPC 驱动的执行路径，通常用于外部宿主或扩展系统。`InteractiveMode` 则对应持续交互的终端模式，强调会话状态和用户输入循环。  
`RpcClient` 不是“模式”本身，而是 RPC 通信和事件分发的基础设施；`RpcCommand`、`RpcResponse`、`RpcSessionState` 等类型则定义了模式之间交换数据时的协议边界。

## 修改风险
这个文件看起来简单，但它是对外入口，风险不在逻辑复杂，而在 API 稳定性。改动导出名称、删减导出项、或者把某个类型/函数挪走，都可能直接破坏大量上层 import。  
另一个风险是类型导出和运行时导出的分离问题：如果改动时只顾实现文件，不同步更新这里，调用方会出现“路径存在但符号缺失”或类型不匹配。对这种聚合入口，最稳妥的做法是把它当作公共边界处理，任何导出调整都要同步检查所有消费点。
