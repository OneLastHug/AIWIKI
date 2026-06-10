# 目录：src/commands/doctor

## 它负责什么

`src/commands/doctor` 是 Claude Code 的“诊断/体检”命令目录，职责很单一：把 `claude doctor` 这条命令接到 CLI 上，并打开一个终端界面的诊断页，用来检查安装状态、配置健康度、自动更新相关信息、MCP/agent/插件带来的上下文告警，以及一些环境变量是否合法。根据当前片段推断，这个目录不是通用业务模块，而是一个面向运维和自检的命令入口，更多是在“把诊断流程挂到命令系统里”和“把诊断结果渲染出来”这两件事之间做桥接。

## 直接子目录地图

这个目录下**没有直接子目录**，当前能看到的只有两个文件：

- `src/commands/doctor/index.ts`：命令注册层，定义 `doctor` 这个 command 的元数据，以及如何懒加载实际实现。
- `src/commands/doctor/doctor.tsx`：命令执行层，导出 `call`，把 CLI 命令转成 React/Ink 的 `Doctor` 界面。

也就是说，这里不是层级很深的功能树，而是一个很薄的命令包装目录，主逻辑实际上散落在 `src/screens/Doctor.tsx` 和若干诊断工具函数里。

## 关键入口

最直接的入口是 `src/commands/doctor/index.ts`。它导出一个 `Command` 对象，名称是 `doctor`，描述是“Diagnose and verify your Claude Code installation and settings”，并通过 `load: () => import('./doctor.js')` 做动态加载。这里还有一个开关：`isEnabled` 会读取 `DISABLE_DOCTOR_COMMAND` 环境变量，若为真则禁用该命令。

真正被 CLI 调用的执行入口在 `src/commands/doctor/doctor.tsx`。它导出 `call: LocalJSXCommandCall`，内部只做一件事：返回 `<Doctor onDone={onDone} />`。也就是说，这个目录并不自己做诊断，它只是把命令生命周期交给 `Doctor` 组件。

## 主流程位置

主流程起点在 `src/main.tsx` 的 `program.command('doctor')` 注册段。这里的 action 会并行加载两个东西：`./cli/handlers/util.js` 里的 `doctorHandler`，以及 `@anthropic/ink` 里的 `createRoot`。随后它通过 `createRoot(getBaseRenderOptions(false))` 创建终端渲染根节点，再调用 `doctorHandler(root)` 进入诊断界面。

再往下，实际诊断逻辑的中心在 `src/screens/Doctor.tsx`。这个组件的流程大致是：

1. 从 `AppState` 读取 agent、MCP 工具、权限上下文、插件错误等状态。
2. 调用 `getDoctorDiagnostic()` 获取安装与运行环境诊断信息。
3. 计算自动更新的 dist-tags，区分 native 与 npm 发行路径。
4. 检查 agent 目录、上下文告警、版本锁、环境变量边界值。
5. 在诊断数据未就绪时显示 loading；就绪后渲染诊断内容，并支持 Enter、Escape、Ctrl+C 关闭。

因此，`src/commands/doctor` 只是一道门，真正的“体检报告生成器”在屏幕层和诊断工具链里。

## 推荐阅读顺序

1. 先看 `src/commands/doctor/index.ts`，确认命令如何注册、是否可用、如何懒加载。
2. 再看 `src/commands/doctor/doctor.tsx`，理解命令如何进入 React/Ink 界面。
3. 然后看 `src/main.tsx` 里 `doctor` 的 command 注册段，弄清楚它在整个 CLI 命令树中的位置。
4. 最后看 `src/screens/Doctor.tsx`，把诊断数据从哪里来、如何汇总、如何展示这条主线串起来。

## 常见误区

一个常见误区是把这个目录当成“完整诊断引擎”。实际上它只包含命令入口和一个 JSX 调度层，真正的检测逻辑主要在 `src/screens/Doctor.tsx` 以及它调用的工具函数里。

另一个误区是忽略 `isEnabled`。`doctor` 并非永远可用，它受 `DISABLE_DOCTOR_COMMAND` 控制；排查命令不可见时，先看环境变量，而不是先怀疑路由或打包。

还有一个容易混淆的点是：`src/commands/doctor/doctor.tsx` 里的 `call` 并不直接做 I/O 诊断，它只是把 UI 挂起来。若要改行为，通常要改的是 `src/screens/Doctor.tsx`、`src/main.tsx` 的注册逻辑，或者更底层的诊断工具函数，而不是只动这个目录里的壳文件。
