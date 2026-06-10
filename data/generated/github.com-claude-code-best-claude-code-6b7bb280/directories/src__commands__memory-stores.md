# 目录：src/commands/memory-stores

## 它负责什么
`src/commands/memory-stores` 是 Claude Code 里处理远程 memory stores 的命令实现目录，面向的是跨设备持久化记忆，而不是本地会话缓存。根据当前片段推断，它承担的是一条完整的 `/memory-stores` 命令链：把用户输入解析成子命令，调用远程 API 执行增删改查，再把结果渲染成终端界面。

这个目录对应的能力比较集中，核心对象有三类：`MemoryStore`、`Memory`、`MemoryVersion`。支持的操作也很直接：列出 store、查看单个 store、创建/归档 store，列出/查看/创建/更新/删除 memory，以及列出版本和 redact 版本。它更像一个远程数据管理面板，而不是记忆检索引擎。

## 直接子目录地图
这个目录本身不大，直接子目录只有一个：

- `__tests__`：放命令行为测试，覆盖参数解析、API 逻辑和启动调度三条主线。

目录下的关键文件可以按职责分成四块理解：

- `index.ts`：命令注册入口
- `launchMemoryStores.tsx`：命令执行与分发主流程
- `parseArgs.ts`：子命令解析
- `memoryStoresApi.ts`：远程 HTTP 客户端
- `MemoryStoresView.tsx`：Ink 终端渲染

## 关键入口
最外层入口不是这个目录内部文件，而是 `src/commands.ts`。这里把 `memoryStoresCommand` 挂进全局命令表，意味着 `/memory-stores` 会被 CLI 主系统识别并进入本目录的加载逻辑。

目录内部真正的对外入口是 `index.ts` 的默认导出。它声明了命令元信息：`type: 'local-jsx'`、名字 `memory-stores`、别名 `mem` 和 `mstore`、描述、参数提示，以及动态加载器 `load()`。这里有一个值得注意的点：`isHidden` 通过 `getGlobalConfig()` 和 `ANTHROPIC_API_KEY` 判断命令是否可见，说明这个命令只在满足 workspace API key 或相关环境条件时才暴露出来。

真正执行命令的是 `launchMemoryStores.tsx` 里导出的 `callMemoryStores`。它把解析、API 调用、事件埋点和视图组装串起来，是这条命令的运行中心。

## 主流程位置
主流程可以按“入口 -> 解析 -> 分发 -> API -> 视图”来读：

1. `src/commands.ts` 注册 `memoryStoresCommand`
2. `src/commands/memory-stores/index.ts` 定义命令元数据，并在 `load()` 时懒加载执行器
3. `src/commands/memory-stores/launchMemoryStores.tsx` 先调用 `parseMemoryStoresArgs`
4. 解析成功后进入 `dispatchMemoryStores()`
5. `dispatchMemoryStores()` 根据 `action` 调用 `memoryStoresApi.ts` 中的函数
6. 返回的数据交给 `MemoryStoresView.tsx` 渲染成终端 UI

其中最核心的判断分支都在 `dispatchMemoryStores()`：`list`、`get`、`create`、`archive`、`memories`、`create-memory`、`get-memory`、`update-memory`、`delete-memory`、`versions`、`redact`。每个分支都带有独立的事件上报和失败兜底，说明这个目录不仅负责功能，也负责可观测性和错误提示。

`memoryStoresApi.ts` 则是另一个关键枢纽。它封装了 `/v1/memory_stores` 及其子资源路径，统一处理：
- workspace 级 API key 构造
- `anthropic-beta` 头
- host guard
- 重试逻辑
- HTTP 错误分类

这里对协议细节有明确约束，比如 `archiveStore` 使用 `POST` 而不是 `DELETE`，`updateMemory` 使用 `PATCH` 而不是 `POST/PUT`，这些都是主流程里不能改错的地方。

## 推荐阅读顺序
建议按这个顺序看：

1. `src/commands/memory-stores/index.ts`：先确认命令在系统里的定位
2. `src/commands/memory-stores/parseArgs.ts`：看子命令如何被切分
3. `src/commands/memory-stores/launchMemoryStores.tsx`：理解整个调度链
4. `src/commands/memory-stores/memoryStoresApi.ts`：看远程调用和协议约束
5. `src/commands/memory-stores/MemoryStoresView.tsx`：看结果如何呈现
6. `src/commands/memory-stores/__tests__`：最后用测试反推边界条件

## 常见误区
一个常见误区是把这里和 `src/commands/local-memory` 混在一起。前者是远程 memory store，后者是本地存储，两者的鉴权、用途和数据边界都不同。

第二个误区是只看 UI，不看 API 约束。这个目录里最容易出错的不是文本渲染，而是 HTTP 方法和头部：`PATCH`、`POST`、beta header、workspace-scoped API key 这些都属于协议硬约束。

第三个误区是忽略 `index.ts` 的懒加载和隐藏逻辑。这个命令不是永远可见的，是否暴露取决于配置和环境变量；如果只看执行文件，很容易误判命令生命周期。

第四个误区是把参数解析想得太简单。`parseArgs.ts` 里很多子命令都允许“内容包含空格”，因此它不是简单按空格全拆，而是保留尾部文本作为 `name` 或 `content`。如果改动解析策略，最容易破坏 `create-memory`、`update-memory` 这类命令。
