# 文件：src/plugins/bundled/index.ts
## 一句话定位
这个文件是“内置插件”的启动入口，职责非常窄：在 CLI 启动早期，把随程序一起发货、且允许用户在 `/plugin` 里显式启用/禁用的插件注册进全局插件注册表。根据当前片段推断，它本身不保存业务状态，只负责把注册动作串起来。

## 它暴露/定义了什么
对外只暴露一个核心函数 `initBuiltinPlugins()`。当前实现里它只调用 `registerWeixinBuiltinPlugin()`，也就是说这个文件更像一个聚合层或装配点，而不是插件逻辑实现处。文件头注释还明确了边界：适合“用户可控开关”的内置插件，不适合像 `claude-in-chrome` 这类需要复杂自动启用逻辑的内容，那类应放到 `src/skills/bundled/`。

## 谁调用它
直接调用方是 `src/main.tsx`。从启动流程看，它在 `setup()` 之前、`getCommands()` 之前被执行，目的是尽早完成插件注册，避免命令和技能枚举时拿到空的注册表。也就是说，它是 CLI 启动链路中的早期初始化步骤，而不是运行期按需触发。

## 它调用谁
当前文件只调用 `src/plugins/bundled/weixin.ts` 里的 `registerWeixinBuiltinPlugin()`。后者再调用 `src/plugins/builtinPlugins.ts` 的 `registerBuiltinPlugin()` 把定义写入内存注册表，并通过 `src/utils/cliLaunch.ts` 组装启动命令。换句话说，这个文件不直接操作插件数据结构，而是把初始化职责委托给具体插件模块。

## 核心流程
流程非常短：`initBuiltinPlugins()` 被启动器调用后，顺序执行各个内置插件的注册函数；当前只注册了 `weixin`。注册完成后，插件定义进入 `BUILTIN_PLUGINS` 这类全局内存表，后续 `/plugin` UI、启用状态计算、以及从内置插件派生出的命令列表，都会读取这份注册结果。根据当前片段推断，这种早注册是为了让后续同步枚举逻辑稳定看到完整数据。

## 关键函数的高层作用
`initBuiltinPlugins()`：内置插件总入口，负责触发所有 bundled plugin 的注册。  
`registerWeixinBuiltinPlugin()`：具体插件装配函数，构造 `weixin` 插件定义，包括名称、描述、版本、默认启用状态和 MCP server 配置。  
它背后依赖的 `registerBuiltinPlugin()`：把定义写进注册表。`buildCliLaunch()`：生成可执行入口与参数，供 `weixin` 的 stdio MCP 服务启动使用。

## 修改风险
这个文件看起来简单，但改动影响面不小。第一，启动顺序很敏感：如果晚于 `getCommands()` 或相关技能加载，UI 和命令系统可能读到不完整的注册表。第二，`weixin` 默认 `defaultEnabled: true`，改这里会直接影响用户首次启动后的可见行为。第三，`mcpServers` 里的启动命令依赖 `buildCliLaunch()` 和 `MACRO.VERSION`，一旦路径、参数或版本注入变化，插件可能无法正常起服务。第四，新增更多内置插件时要注意不要和 `src/skills/bundled/` 的职责重叠，否则会把“可手动开关的插件”和“自动加载的 bundled skill”混在一起，后续维护会变脏。
