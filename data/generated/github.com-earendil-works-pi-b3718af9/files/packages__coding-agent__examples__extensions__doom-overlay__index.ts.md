# 文件：packages/coding-agent/examples/extensions/doom-overlay/index.ts

## 一句话定位
这是一个 `coding-agent` 扩展示例的入口文件，负责把 `doom-overlay` 命令挂到宿主 `pi` 上，并在 TUI 里启动一个可复用的 DOOM overlay。根据当前片段推断，它的目标不是实现游戏本体，而是演示扩展如何接入实时渲染、overlay UI 和持久化状态。

## 它暴露/定义了什么
文件默认导出一个接收 `ExtensionAPI` 的函数。这个函数在被扩展宿主加载时执行，内部通过 `pi.registerCommand("doom-overlay", ...)` 注册命令。  
文件顶层还定义了两个模块级状态：`activeEngine` 和 `activeWadPath`，用于在多次调用之间保留同一个 `DoomEngine` 实例和对应 WAD 路径，避免每次都重新初始化。

## 谁调用它
从注释里的用法 `pi --extension ./examples/extensions/doom-overlay` 可以看出，它由 `pi` 的扩展加载器调用，而不是普通业务代码直接调用。宿主会在装载扩展时把 `pi` 注入进默认导出函数，然后由该函数完成命令注册。之后，真正触发执行的是用户在交互环境里输入 `/doom-overlay`，从而进入命令处理器。

## 它调用谁
它主要调用三类对象：宿主 API、游戏资源/引擎层、以及 overlay 组件层。  
宿主侧包括 `pi.registerCommand`、`ctx.ui.notify` 和 `ctx.ui.custom`。  
资源侧包括 `ensureWadFile()`，用于确保 WAD 文件存在，必要时自动下载。  
引擎侧包括 `new DoomEngine(wad)` 和 `activeEngine.init()`。  
渲染侧包括 `new DoomOverlayComponent(...)`，它被交给 `ctx.ui.custom` 以 overlay 形式展示。

## 核心流程
1. 注册 `doom-overlay` 命令。  
2. 命令被触发后先检查 `ctx.mode`，不是 `tui` 就直接报错返回。  
3. 提示“Loading DOOM...”，然后决定 WAD 来源：如果用户传了参数就用参数，否则调用 `ensureWadFile()` 自动获取。  
4. 如果拿不到 WAD，直接通知失败并退出。  
5. 进入创建或复用逻辑：如果 `activeEngine` 已存在且 `activeWadPath` 匹配当前 WAD，就走恢复路径；否则重新创建 `DoomEngine` 并执行 `init()`。  
6. 通过 `ctx.ui.custom` 打开 overlay，把 `DoomOverlayComponent` 交给 TUI 渲染，并用 `done(...)` 作为退出回调。  
7. 任一异常都会进入 `catch`，通知失败并清空引擎状态，避免半初始化对象继续留在模块里。

## 关键函数的高层作用
`default function (pi: ExtensionAPI)`：扩展入口，只负责注册命令，不承担业务执行。  
命令 `handler`：真正的控制流中心，负责模式检查、WAD 解析、引擎生命周期和 UI 打开。  
`ensureWadFile()`：资源准备器，核心意义是把“是否已有 DOOM 数据文件”这件事从命令逻辑里抽出去。  
`DoomEngine.init()`：引擎初始化入口，通常意味着加载资源、建立运行状态，准备进入实时帧循环。  
`ctx.ui.custom(...)`：把业务组件嵌入宿主 UI 框架，是这个示例最关键的集成点。  
`DoomOverlayComponent`：真正承载 overlay 行为的组件，负责把引擎状态变成可交互界面。

## 修改风险
这类文件的风险主要在集成面，不在算法本身。第一，`ctx.mode !== "tui"` 的分支说明它强依赖交互终端环境，改动后很容易在非 TUI 场景下失效。第二，WAD 获取涉及文件系统和网络，`ensureWadFile()` 的失败路径会直接影响可用性。第三，`activeEngine` 是模块级持久状态，复用逻辑写错会导致跨次运行串状态、重复初始化或无法正确恢复。第四，`activeEngine!` 这种非空断言依赖前置分支严格成立，后续如果改动流程顺序，可能引入运行时崩溃。第五，overlay 渲染和实时帧率相关，调整 `ctx.ui.custom` 参数、尺寸或组件生命周期时，容易出现无法关闭、黑屏、资源未释放等问题。
