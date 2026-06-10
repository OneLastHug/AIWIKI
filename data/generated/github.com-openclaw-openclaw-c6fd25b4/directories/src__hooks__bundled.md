# 目录：src/hooks/bundled

## 它负责什么

`src/hooks/bundled` 存放 OpenClaw 随程序一起发布的内置 internal hooks。它不是 hook 框架本身，也不是外部插件 SDK，而是一组“可被发现、可按配置启用、在特定事件上执行”的默认 hook 实现集合。

从目录内的 `README.md` 和各子目录 `HOOK.md` 可以看出，这里的 hook 覆盖几类横切能力：启动后执行工作区 `BOOT.md`、在 agent bootstrap 阶段追加额外上下文文件、记录命令事件、在会话压缩前后发送提示、以及在 `/new` 或 `/reset` 时把会话内容保存成 memory 文档。它们都遵循同一个基本形态：每个 hook 一个目录，目录里有 `HOOK.md` 描述元数据和用户说明，有 `handler.ts` 暴露默认处理函数。

这个目录的角色更接近“内置 hook 包”。发现、过滤、导入、注册、触发这些框架流程主要在邻近的 `src/hooks/workspace.ts`、`src/hooks/loader.ts`、`src/hooks/internal-hooks.ts` 完成；`src/hooks/bundled` 主要提供具体 handler 和对应的 `HOOK.md` 元数据。

## 直接子目录地图

`src/hooks/bundled/boot-md` 是 gateway 启动类 hook，监听 `gateway:startup`，在 gateway 启动并完成 channel 相关启动后，按 agent scope 检查并运行对应工作区的 `BOOT.md`。它连接的是启动生命周期和 `gateway/boot` 的实际执行逻辑。

`src/hooks/bundled/bootstrap-extra-files` 是 prompt/bootstrap 上下文增强类 hook，监听 `agent:bootstrap`。它按配置里的 `paths`、`patterns` 或 `files` 从工作区加载额外 bootstrap 文件，再合并进当前 session 可见的 bootstrap 文件列表。它适合 monorepo 或多上下文根场景。

`src/hooks/bundled/command-logger` 是命令审计类 hook，监听通用 `command` 事件。它把命令动作、时间、session key、sender/source 等写成 JSONL 日志。它属于旁路记录能力，不改变会话或 prompt。

`src/hooks/bundled/compaction-notifier` 是会话压缩提示类 hook，监听 `session:compact:before` 和 `session:compact:after`。它通过 `event.messages` 向调用方返回用户可见提示，说明压缩开始或完成，并可携带消息数、token 数变化等摘要。

`src/hooks/bundled/session-memory` 是会话记忆保存类 hook，监听 `command:new` 和 `command:reset`。它读取最近会话 transcript，生成带日期和 slug 的 Markdown memory 文件。该子目录还包含 `transcript.ts`，用于封装“从当前或前一个 session 取可保存内容”的读取逻辑。

## 关键入口

目录级入口是 `src/hooks/bundled/README.md`。它说明 bundled hooks 的结构、启用方式、配置位置、支持事件类型和 handler API，是理解这个目录“约定”的第一站。

每个 hook 的声明入口是对应子目录里的 `HOOK.md`。这些文件用 YAML frontmatter 描述 `name`、`description`、`metadata.openclaw.events`、`requires`、`install` 等信息。loader 不是靠硬编码目录名来决定事件，而是读取 hook metadata 里的 events，再注册到 internal hook registry。

每个 hook 的执行入口是对应的 `handler.ts` 默认导出。`src/hooks/loader.ts` 会动态 import handler 模块，默认读取 `default` export；如果 metadata 指定了其他 export，也可从模块中解析命名导出。对 `src/hooks/bundled` 里的当前实现来说，核心都是默认导出的 `HookHandler`。

发现 bundled hooks 的入口不在本目录，而在 `src/hooks/bundled-dir.ts` 和 `src/hooks/workspace.ts`。`resolveBundledHooksDir()` 负责根据运行形态定位 bundled hooks 目录：可由 `OPENCLAW_BUNDLED_HOOKS_DIR` 覆盖，也会尝试 Bun 编译产物旁边的 `hooks/bundled`、npm 安装后的 `dist/hooks/bundled`、开发环境的 `src/hooks/bundled`。`loadWorkspaceHookEntries()` 会把 bundled、plugin、managed、workspace 等来源统一装配成 hook entries，其中 bundled 来源标记为 `openclaw-bundled`。

## 主流程位置

主流程可以按“发现、过滤、注册、触发、执行”理解。

发现阶段在 `src/hooks/workspace.ts`。它调用 `resolveBundledHooksDir()` 找到 bundled hooks 根目录，再读取每个 hook 目录下的 `HOOK.md` 和 handler 文件，形成带 source、metadata、invocation policy 的 hook entry。根据当前片段推断，bundled hooks 与 managed/workspace/plugin hooks 共用同一套目录发现和 frontmatter 解析逻辑，依据是 `discoverWorkspaceHookEntries()` 把 `bundledHooks`、`pluginHooks`、`managedHooks`、`workspaceHooks` 合并返回。

过滤和注册阶段在 `src/hooks/loader.ts`。`loadInternalHooks(cfg, workspaceDir)` 会先清理旧注册，再检查配置中 internal hooks 是否启用；随后加载 workspace hook entries，按配置和策略筛出 eligible hooks。对每个 eligible entry，它会做 handler 路径边界检查，构造 import URL，动态导入模块，解析 handler 函数，然后把 metadata 中列出的每个 event 交给 `registerInternalHook(event, handler)`。

事件注册表和触发机制在 `src/hooks/internal-hooks.ts`。这里维护一个全局 singleton `Map<string, InternalHookHandler[]>`，避免 bundle splitting 后出现多个 registry。`triggerInternalHook(event)` 会同时查找通用类型监听器，例如 `command`，以及精确事件监听器，例如 `command:new`，并按注册顺序执行；单个 handler 抛错会被记录，但不会阻止其他 handler。

触发点分散在业务生命周期里。`agent:bootstrap` 由 `src/agents/bootstrap-hooks.ts` 的 `applyBootstrapHookOverrides()` 发出；`gateway:startup` 在 `src/gateway/server-startup-post-attach.ts` 中 channel 和 plugin service 启动后异步触发；`command:new` 可在 `src/gateway/server-methods/sessions.ts` 的 session create 相关流程里发出；`command:reset` 等 reset 类事件在 `src/gateway/session-reset-service.ts` 中触发；`session:compact:before` 和 `session:compact:after` 位于 `src/agents/pi-embedded-runner/compaction-hooks.ts` 的压缩前后钩子流程。

## 推荐阅读顺序

先读 `src/hooks/bundled/README.md`，建立内置 hook 的结构约定：一个目录、一个 `HOOK.md`、一个 handler、metadata 声明 events。

再读 `src/hooks/bundled-dir.ts` 和 `src/hooks/workspace.ts`，理解 bundled hooks 在不同运行形态下如何被定位，以及如何与 workspace、managed、plugin hooks 合并成统一条目。

然后读 `src/hooks/loader.ts`，重点看 `loadInternalHooks()`：配置启用、entry 过滤、handler 动态导入、events 注册都集中在这里。

接着读 `src/hooks/internal-hooks.ts`，理解 `createInternalHookEvent()`、`registerInternalHook()`、`triggerInternalHook()` 之间的关系，以及通用事件和精确事件如何同时命中。

最后回到各子目录的 `HOOK.md` 和 `handler.ts`。建议按生命周期顺序看：`boot-md`、`bootstrap-extra-files`、`command-logger`、`session-memory`、`compaction-notifier`。这样能先理解启动和 prompt 组装，再理解命令、session 和压缩事件。

## 常见误区

不要把 `src/hooks/bundled` 当成 hook 系统的总入口。它只是内置 hook 实现目录；真正的发现入口在 `src/hooks/workspace.ts`，注册入口在 `src/hooks/loader.ts`，事件总线在 `src/hooks/internal-hooks.ts`。

不要以为目录名决定监听事件。事件由 `HOOK.md` 的 `metadata.openclaw.events` 声明，loader 根据 metadata 注册；handler 内部通常还会用 `event.type`、`event.action` 或类型守卫再次确认事件形态。

不要把 bundled hooks 和 plugin hooks 混为一谈。bundled hooks 的 source 是 `openclaw-bundled`，它们运行在 internal hook 系统里；plugin hooks、provider hooks、Pi runner hooks 属于相邻但不同的扩展面。虽然有些生命周期相近，例如 compaction 同时可能有 internal hook 和 plugin hook，但它们的注册与调用路径不同。

不要误解 `event.messages`。它不是日志，也不是直接发送 API；handler 可以向数组里 push 文本，触发方再决定是否把这些消息反馈给用户。`compaction-notifier` 是这个模式的典型例子。

不要把 `bootstrap-extra-files` 理解为任意文件注入。根据当前片段推断，它只加载受认可的 bootstrap basename，并要求路径解析后仍在 workspace 内；依据是其 `HOOK.md` 明确提到 realpath 检查和允许的 `AGENTS.md`、`TOOLS.md` 等文件名。

不要认为所有 bundled hooks 默认都会执行。它们需要 internal hooks 总开关、配置 entry、hook eligibility 策略和 metadata event 注册共同生效。`handler.ts` 里也常有配置检查或事件类型检查，因此“发现到目录”不等于“运行了逻辑”。
