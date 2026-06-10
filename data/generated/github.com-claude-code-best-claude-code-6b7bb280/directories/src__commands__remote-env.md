# 目录：src/commands/remote-env

## 它负责什么

`src/commands/remote-env` 负责提供一个本地 JSX 命令：`remote-env`。它的作用是让用户在 Claude Code CLI 内配置 teleport sessions 使用的默认远程环境。这里的“远程环境”不是本地 shell 环境变量，也不是 MCP server 配置，而是与 Remote Sessions / Teleport 相关的一组云端或远端执行环境资源。

从当前片段看，这个目录本身非常薄，只承担“命令声明”和“命令渲染入口”两件事：  
一是向命令系统注册 `remote-env`，描述它的名称、说明、可用条件、隐藏条件和懒加载模块；二是在命令被调用时渲染 `RemoteEnvironmentDialog`，把后续的环境拉取、选择、写入设置等 UI 流程交给组件层处理。

真正的业务逻辑不在这个目录内，而是分散在邻近模块中：环境列表与当前选中环境来自 `src/utils/teleport/environmentSelection.js`，环境资源类型来自 `src/utils/teleport/environments.js`，设置写入走 `src/utils/settings/settings.js`，权限和订阅判断分别走 `src/services/policyLimits/index.js`、`src/utils/auth.js`。因此本目录可以理解为“命令到远程环境选择对话框的桥接层”。

## 直接子目录地图

这个目录没有直接子目录，只有两个文件：

`src/commands/remote-env/index.ts`：命令元信息入口，导出符合 `Command` 类型的默认对象。它声明命令名为 `remote-env`，类型为 `local-jsx`，并通过 `load` 懒加载实际 JSX 命令实现。

`src/commands/remote-env/remote-env.tsx`：命令执行入口，导出 `call(onDone)`。该函数返回一个 React 节点，即 `RemoteEnvironmentDialog`，并把命令完成回调 `onDone` 传入对话框。

由于目录规模很小，阅读时不需要逐行拆解成多个层次。理解它最重要的是把它放回 CLI 命令体系和远程环境 UI 流程中看。

## 关键入口

第一个关键入口是 `src/commands/remote-env/index.ts`。它是命令系统识别 `remote-env` 的位置。这里的核心字段包括：

`type: 'local-jsx'` 表示该命令会在本地 Ink/React UI 中渲染，而不是简单打印文本或执行纯命令逻辑。

`name: 'remote-env'` 是用户侧命令名称。根据命令体系惯例，它通常会被 CLI 的斜杠命令或本地命令注册机制收集。

`description: 'Configure the default remote environment for teleport sessions'` 说明这个命令的语义是为 teleport sessions 配置默认 remote environment。

`isEnabled` 和 `isHidden` 控制命令可用性。当前条件要求用户是 Claude AI subscriber，并且策略允许 `allow_remote_sessions`。换句话说，即使代码存在，普通用户或受策略限制的环境也可能看不到或不能执行这个命令。

`load: () => import('./remote-env.js')` 是实际执行模块的懒加载入口。命令列表阶段不急着加载 JSX 组件，只有执行时才载入 `remote-env` 实现。

第二个关键入口是 `src/commands/remote-env/remote-env.tsx`。它导出 `call(onDone)`，返回 `<RemoteEnvironmentDialog onDone={onDone} />`。这里没有额外业务判断，说明运行时流程几乎完全由组件 `RemoteEnvironmentDialog` 负责。

## 主流程位置

主流程从命令系统加载 `index.ts` 开始。命令注册阶段读取 `remote-env` 的元信息，并根据 `isEnabled`、`isHidden` 决定它是否可用、是否显示。判断条件来自 `isClaudeAISubscriber()` 和 `isPolicyAllowed('allow_remote_sessions')`，所以这个命令天然受账号订阅状态和组织/策略限制影响。

当用户触发 `remote-env` 后，命令系统通过 `load()` 动态导入 `src/commands/remote-env/remote-env.tsx`，再调用其中的 `call(onDone)`。`call` 返回 `RemoteEnvironmentDialog`，进入 Ink UI 渲染流程。

对话框主流程位于 `src/components/RemoteEnvironmentDialog.tsx`。组件挂载后调用 `getEnvironmentSelectionInfo()` 获取环境选择信息。根据当前片段，这个结果至少包含 `availableEnvironments`、`selectedEnvironment`、`selectedEnvironmentSource`。组件随后进入几个分支：

加载中时显示 `Loading environments…`。

拉取失败时把异常转成标准错误，调用 `logError`，并在对话框中显示错误信息。

如果没有当前选中的环境，则提示没有可用 remote environments，并显示配置入口提示。源码中提示包含一个真实外部地址，文档中按要求记为 `[URL已移除]`。

如果只有一个环境，则显示当前正在使用该环境，用户按确认键即可关闭。

如果有多个环境，则显示选择列表。用户选择某个环境后，组件调用 `updateSettingsForSource('localSettings', { remote: { defaultEnvironmentId } })`，把默认环境 ID 写入本地设置，然后通过 `onDone` 返回成功消息。

因此，本目录的主流程位置是“命令触发到对话框渲染”，而不是“远程环境发现”或“远程会话创建”。真正的数据获取和设置持久化已经下沉到 `utils/teleport` 与 `utils/settings`。

## 推荐阅读顺序

建议先读 `src/commands/remote-env/index.ts`，确认命令名称、可用条件和懒加载方式。这个文件能回答“用户什么时候能看到这个命令”以及“命令系统如何找到实现”。

第二步读 `src/commands/remote-env/remote-env.tsx`。它非常短，但能确认该命令没有额外中间逻辑，只是渲染 `RemoteEnvironmentDialog`。这一步有助于避免在命令目录里寻找不存在的业务实现。

第三步读 `src/components/RemoteEnvironmentDialog.tsx`。这里是实际交互流程，包括加载环境、错误展示、单环境展示、多环境选择、写入 local settings、快捷键提示等。

第四步再按需追踪 `src/utils/teleport/environmentSelection.js` 和 `src/utils/teleport/environments.js`。根据当前片段推断，前者负责聚合“可用环境 + 当前选择 + 选择来源”，后者定义或获取环境资源结构。这个推断依据是 `RemoteEnvironmentDialog` 直接导入了 `getEnvironmentSelectionInfo` 和 `EnvironmentResource`。

最后再看 `src/utils/settings/settings.js`、`src/utils/settings/constants.js`，理解 `localSettings`、设置来源名称、以及本地设置覆盖其他设置来源的规则。

## 常见误区

不要把 `remote-env` 理解成配置本地环境变量的命令。它配置的是 teleport sessions 的默认 remote environment，最终写入的是 `remote.defaultEnvironmentId`。

不要以为这个目录负责创建、删除或同步远程环境。它只负责选择默认环境。环境列表从 `getEnvironmentSelectionInfo()` 来，环境的配置入口在外部服务侧，源码提示为 `[URL已移除]`。

不要忽略 `isEnabled` 和 `isHidden`。这个命令受 `isClaudeAISubscriber()` 和 `isPolicyAllowed('allow_remote_sessions')` 双重限制。调试时如果命令不可见，不一定是注册失败，也可能是订阅状态或策略限制导致。

不要在 `src/commands/remote-env` 里寻找完整 UI 状态机。目录内的 `remote-env.tsx` 只是把 `onDone` 传给 `RemoteEnvironmentDialog`。加载态、错误态、空环境态、单环境态、多环境选择态都在组件文件中。

不要把设置来源显示和写入目标混为一谈。对话框会显示当前环境可能来自非 `localSettings` 的设置来源，但用户选择新环境时写入的是 `localSettings`。这意味着本地设置会成为后续默认环境选择的重要覆盖层。

不要把 `local-jsx` 当作普通命令执行模式。它意味着命令返回 React 节点，由 Ink 渲染交互式对话框，并通过 `onDone` 通知命令完成。对于这类命令，入口函数通常不是直接打印结果，而是返回 UI 组件。
