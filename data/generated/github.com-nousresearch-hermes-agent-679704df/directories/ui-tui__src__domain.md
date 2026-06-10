# 子系统：ui-tui/src/domain

## 解决什么问题

`ui-tui/src/domain` 是 TUI 前端里的“领域规则层”。它不直接渲染 React/Ink 组件，也不负责 JSON-RPC 通信，而是把聊天终端界面中反复出现的业务判断收拢成可复用的纯函数和常量：消息如何转成可显示的 transcript、长消息如何压缩展示、详情区默认展开还是隐藏、slash command 如何解析、当前目录与 Git 分支如何缩短、provider 名称如何消歧、视口滚动时如何生成 sticky prompt 等。

从职责边界看，这个目录处在 `app/` 状态编排、`components/` 渲染组件和 `gatewayTypes.ts` 后端协议之间。它让上层组件少写散落的字符串规则和兼容逻辑，降低 UI 行为在多个入口之间不一致的风险。根据当前片段推断，`domain` 的定位不是完整领域模型，而是 TUI 专用的轻量 domain helpers；依据是目录下文件都导出无副作用函数，调用方集中在 `useMainApp.ts`、`useConfigSync.ts`、`useSessionLifecycle.ts`、`messageLine.tsx`、`thinking.tsx`、slash command 模块和测试文件中。

## 相关目录和文件

`ui-tui/src/domain/messages.ts` 负责 transcript 消息转换与显示文案，包括 `introMsg()`、`toTranscriptMessages()`、`userDisplay()`、`attachedImageNotice()`、`fmtDuration()`。它依赖 `ui-tui/src/types.ts` 中的 `Msg`、`SessionInfo`，并使用 `config/limits.ts` 的 `LONG_MSG` 控制长消息摘要。

`ui-tui/src/domain/details.ts` 负责详情面板可见性规则，定义 `SECTION_NAMES`，并提供 `parseDetailsMode()`、`resolveDetailsMode()`、`resolveSections()`、`sectionMode()`、`nextDetailsMode()`。它连接配置项 `display.details_mode`、旧的 `thinking_mode` 兼容字段、以及 `/details` 运行时命令。

`ui-tui/src/domain/slash.ts` 放 slash command 的基础解析和 TUI 特殊模型切换标记，如 `looksLikeSlashCommand()`、`parseSlashCommand()`、`TUI_SESSION_MODEL_FLAG`。

`ui-tui/src/domain/viewport.ts` 处理 transcript 视口相关规则，核心是 `stickyPromptFromViewport()`，用于滚动历史时在顶部提示最近一个已经滚出视口的用户 prompt。

`ui-tui/src/domain/paths.ts` 提供 `shortCwd()`、`fmtCwdBranch()`，用于状态栏或 chrome 区域展示工作目录与分支。

`ui-tui/src/domain/providers.ts` 提供 `providerDisplayNames()`，当多个 provider 拥有同名 display name 时追加 slug 消歧。

`ui-tui/src/domain/roles.ts` 定义 `ROLE` 映射，把 `assistant`、`system`、`tool`、`user` 映射到主题颜色、glyph 和前缀颜色。

`ui-tui/src/domain/usage.ts` 只有 `ZERO`，作为 token/cost usage 状态的零值基准。

邻近目录中，`ui-tui/src/app` 负责状态、生命周期、slash 分发和 gateway 事件处理；`ui-tui/src/components` 负责 Ink 渲染；`ui-tui/src/lib` 提供更底层的文本、RPC、viewport、terminal 等工具；`ui-tui/src/__tests__` 和 `ui-tui/src/lib/*.test.ts` 覆盖这些规则的回归测试。

## 核心对象

核心类型主要来自 `ui-tui/src/types.ts`。`Msg` 是 transcript 的显示消息结构，包含 `role`、`text`、`kind`、`tools`、`thinking`、`todos`、`info` 等字段。`domain/messages.ts` 的主要职责就是把后端 transcript row 或 session info 转成 `Msg[]`。

`DetailsMode` 是 `'hidden' | 'collapsed' | 'expanded'`，表示详情区隐藏、折叠或展开。`SectionName` 是 `'thinking' | 'tools' | 'subagents' | 'activity'`，`SectionVisibility` 是各 section 的局部覆盖配置。`details.ts` 中的 `SECTION_DEFAULTS` 很关键：默认 `thinking`、`tools` 展开，`activity` 隐藏，`subagents` 回落到全局模式。

`ROLE` 是角色到视觉语义的映射，不保存状态，但直接影响 `MessageLine` 的 gutter glyph 和颜色。修改它会改变所有 transcript 行的基本视觉语言。

`TUI_SESSION_MODEL_FLAG` 是 TUI model picker 和 `/model` 命令之间的协议标记。它被 `modelPicker.tsx`、`activeSessionSwitcher.tsx` 和 `app/slash/commands/session.ts` 使用，用来表示模型切换应作用于当前 session。

## 运行流程

TUI 启动后，`useSessionLifecycle()` 通过 gateway 创建或恢复 session，拿到 `SessionInfo` 后调用 `introMsg(info)` 生成开场系统消息，并用 `ZERO` 初始化 usage。恢复历史或压缩 transcript 时，后端返回的 rows 会经 `toTranscriptMessages()` 转为前端 `Msg[]`：连续 `tool` row 会先聚合成 pending trail，随后挂到下一条 assistant 消息的 `tools` 字段上。

配置同步由 `useConfigSync()` 触发。它请求 `config.get full` 后调用 `resolveDetailsMode()` 和 `resolveSections()`，把自由格式配置规范化到 UI state。渲染时，`MessageLine` 和 `thinking.tsx` 不直接读取原始配置，而是通过 `sectionMode()` 计算某个 section 的最终模式。最终优先级是：显式 section 覆盖、运行时 `/details` 全局命令覆盖、内建 section 默认值、全局配置。

用户输入提交前，`useSubmission()` 和 `useCompletion()` 用 `looksLikeSlashCommand()` 判断是否是 slash command；`createSlashHandler()` 用 `parseSlashCommand()` 拆出命令名和参数，再先查本地命令注册表，找不到时回退到 gateway 的 `slash.exec` 或 `command.dispatch`。

界面滚动时，`appChrome.tsx` 会调用 `stickyPromptFromViewport()`，结合消息列表、高度 offset、视口 top/bottom 判断是否显示最近的用户 prompt 摘要。长用户消息的摘要规则复用 `userDisplay()`，避免 sticky prompt 或 transcript 中出现大段 paste 内容。

## 上下游依赖

上游输入主要来自三个方向：gateway RPC 返回的 session、transcript、config、provider、image attach 等数据；用户输入的命令和 prompt；终端视口与主题状态。`domain` 层不直接请求 gateway，而是由 `app/` 层传入已经拿到的数据。

下游消费者主要是 `ui-tui/src/app` 和 `ui-tui/src/components`。`useMainApp.ts` 使用 `SECTION_NAMES`、`sectionMode()`、`attachedImageNotice()`、`fmtCwdBranch()` 等函数组织主界面状态；`useSessionLifecycle.ts` 使用 `introMsg()`、`toTranscriptMessages()`、`ZERO` 初始化或恢复会话；`createSlashHandler.ts` 使用 slash parser 统一命令解析；`messageLine.tsx`、`thinking.tsx` 和 `appChrome.tsx` 使用 domain helpers 控制实际渲染。

测试位于 `ui-tui/src/__tests__/details.test.ts`、`messages.test.ts`、`paths.test.ts`、`viewport.test.ts`、`providers.test.ts`、`constants.test.ts`、`createSlashHandler.test.ts` 等。因为这些函数大多是纯函数，测试可以直接验证输入输出，不需要启动完整 Ink runtime。

## 修改时最容易踩的坑

第一，`details.ts` 的默认值不是简单全局配置。`thinking` 和 `tools` 默认展开、`activity` 默认隐藏，是刻意覆盖在全局 `details_mode` 之上的；但运行时 `/details <mode>` 又需要用 `commandOverride` 让全局命令立即影响所有 section。改 `sectionMode()` 时必须保留这层差异，否则启动默认行为和命令行为会互相污染。

第二，`toTranscriptMessages()` 会把 tool row 作为下一条 assistant 消息的 trail。这个转换决定历史恢复、压缩后重建 transcript、工具轨迹显示的连续性。若改成直接输出 `role: 'tool'`，会影响 `MessageLine` 与 `ToolTrail` 的展示结构。

第三，`parseSlashCommand()` 目前是轻量解析，只按空白切分命令名和余下参数，不处理 shell quoting。调用方如果需要复杂参数语义，应在具体命令内部解析，而不是把基础 parser 做重。

第四，`TUI_SESSION_MODEL_FLAG` 是跨组件约定。`modelPicker.tsx` 添加它，`sessionCommands` 再剥离它后调用 `config.set`。改名或改匹配正则时要同时看 picker、session command 和相关测试。

第五，`paths.ts` 使用 `process.env.HOME` 进行 `~` 缩写，并用省略号裁剪尾部。它服务于窄终端状态栏，不能假设路径总能完整显示。

第六，`ROLE` 依赖 `Theme` 的字段结构。新增 role 或改 glyph 时，需要同步 `types.ts` 的 `Role` 类型、`MessageLine` gutter 宽度计算，以及 `constants.test.ts`。

## 推荐阅读顺序

1. 先读 `ui-tui/src/types.ts`，理解 `Msg`、`SessionInfo`、`Usage`、`DetailsMode`、`SectionName`、`SlashCatalog` 这些共享类型。
2. 再读 `ui-tui/src/domain/messages.ts`，掌握 transcript 如何从后端 rows 变成前端显示消息。
3. 接着读 `ui-tui/src/domain/details.ts`，这是该目录中业务规则最集中的文件，直接影响 reasoning、tools、subagents、activity 的可见性。
4. 然后读 `ui-tui/src/app/useConfigSync.ts`、`ui-tui/src/components/messageLine.tsx`、`ui-tui/src/components/thinking.tsx`，看 details 规则如何进入配置同步和渲染。
5. 再读 `ui-tui/src/domain/slash.ts` 与 `ui-tui/src/app/createSlashHandler.ts`、`ui-tui/src/app/slash/commands/session.ts`，理解命令解析与 fallback 到 gateway 的流程。
6. 最后读 `viewport.ts`、`paths.ts`、`providers.ts`、`roles.ts`、`usage.ts` 以及对应测试，补齐状态栏、provider picker、角色视觉和 usage 初始值这些边缘但高频的 UI 规则。
