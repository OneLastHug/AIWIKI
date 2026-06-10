# 目录：apps/macos

## 它负责什么

`apps/macos` 是 OpenClaw 的 macOS 伴生应用工程，采用 Swift Package 组织。它同时产出菜单栏应用 `OpenClaw`、命令行工具 `openclaw-mac`，以及供两者复用的 Swift library target：`OpenClawIPC` 和 `OpenClawDiscovery`。从 `Package.swift` 看，这个目录面向 macOS 15，依赖 `OpenClawKit`、`OpenClawChatUI`、`OpenClawProtocol`、`SwabbleKit`、`MenuBarExtraAccess`、`Sparkle`、`Peekaboo`、`swift-log` 等，用来把桌面菜单栏、Gateway 连接、控制通道、远程发现、设置页、语音/会话/画布等本机体验接到 OpenClaw 的核心 Gateway 协议上。

它不是核心 TypeScript Gateway 本体，也不是插件实现目录。更准确地说，它是 macOS 原生壳层：负责启动或连接 Gateway、展示菜单栏状态、打开设置和 dashboard、处理本机权限、语音唤醒、屏幕/相机/音频相关能力、远程/本地连接模式切换，以及通过 WebSocket/IPC 与 Gateway 交换请求和推送事件。

## 直接子目录地图

`apps/macos/Sources` 是源码主体，下面按 Swift Package target 分成几个区域：

`apps/macos/Sources/OpenClaw` 是主菜单栏 App target。这里数量最大，承载 SwiftUI/AppKit UI、状态管理、Gateway 生命周期、控制通道、设置页、会话菜单、dashboard、canvas、web chat、onboarding、权限、语音、talk mode、node mode、执行审批、cron、skills、channels 等桌面功能。它下面还有少量二级目录：`Logging` 放日志封装，`NodeMode` 放 macOS node 模式运行相关代码，`Resources` 放 `Info.plist`、App 图标和设备型号资源。

`apps/macos/Sources/OpenClawIPC` 是 IPC library，目前关键文件是 `IPC.swift`。从 target 名和测试命名看，它为 app、CLI 或测试提供进程间通信/协议相关基础类型。根据当前片段推断，它是低层共享库，依据是 `Package.swift` 将它声明为 library，并让主 App 和测试 target 依赖它。

`apps/macos/Sources/OpenClawDiscovery` 是 Gateway/网络发现库，包含 `GatewayDiscoveryModel.swift`、`TailscaleNetwork.swift`、`TailscaleServeGatewayDiscovery.swift`、`WideAreaGatewayDiscovery.swift`。它负责把远程或局域网可用 Gateway 发现结果抽象出来，供 CLI 和 App 选择连接目标。

`apps/macos/Sources/OpenClawMacCLI` 是 `openclaw-mac` 可执行 target。这里是命令行入口和子命令实现，包括 `connect`、`configure-remote`、`discover`、`wizard`，用于连接 Gateway、配置远程 SSH/Tailscale 场景、发现实例和跑引导流程。

`apps/macos/Tests` 是 Swift 测试目录，当前只有 `OpenClawIPCTests` 一个 test target，但覆盖范围远大于 IPC 名称本身：包括 Gateway 连接、配置、设置页 smoke test、权限、语音、canvas、channels、cron、node mode、远程发现、CLI 命令等。

`apps/macos/Packaging` 放 macOS 打包素材，例如 DMG 背景图。`apps/macos/Icon.icon` 放图标源资源。`apps/macos/Package.resolved` 固定 Swift Package 依赖解析结果。`apps/macos/README.md` 说明本地运行、打包、签名和 Team ID 检查流程。

## 关键入口

主 App 入口在 `apps/macos/Sources/OpenClaw/MenuBar.swift`。这里定义 `@main struct OpenClawApp: App`，通过 `MenuBarExtra` 创建菜单栏应用，并挂载 `MenuContent`、状态图标 `CritterStatusLabel`、设置窗口 `SettingsRootView`。同一文件还通过 `AppDelegate` 处理应用生命周期，并在状态变化时驱动 `GatewayProcessManager`、`ControlChannel`、`ConnectionModeCoordinator` 等核心对象。

CLI 入口在 `apps/macos/Sources/OpenClawMacCLI/EntryPoint.swift`。`@main struct OpenClawMacCLI` 读取 `CommandLine.arguments`，分发到 `runConnect`、`runConfigureRemote`、`runDiscover`、`runWizardCommand`。如果只想理解 `openclaw-mac` 命令的用户面，先看这个文件，再顺着同目录的各 `*Command.swift` 读。

Gateway 通信入口在 `apps/macos/Sources/OpenClaw/GatewayConnection.swift`。它是 `actor GatewayConnection`，持有共享 WebSocket 通道，封装 `request`、订阅推送、Gateway method 枚举、agent/chat/config/channels/cron/skills/voicewake 等请求。大量 UI store 和控制器都通过 `GatewayConnection.shared` 调 Gateway。

连接模式入口在 `apps/macos/Sources/OpenClaw/ConnectionModeCoordinator.swift`。它把 App 的 `unconfigured`、`local`、`remote` 三种模式落实为具体动作：停止或启动本地 Gateway、管理远程 tunnel、配置 `ControlChannel`、清理 WebChat tunnel、触发端口清理等。

Endpoint 状态入口在 `apps/macos/Sources/OpenClaw/GatewayConnectivityCoordinator.swift`。它订阅 `GatewayEndpointStore`，记录当前 resolved URL、模式和 host label，并在 endpoint 变化时刷新控制通道。

## 主流程位置

启动主流程从 `MenuBar.swift` 开始：`OpenClawApp.init()` 初始化日志和 `AppStateStore`，`body` 创建菜单栏、设置窗口和若干 `onChange` 监听。当用户切换连接模式或 pause 状态时，UI 状态变化会驱动 `GatewayProcessManager` 和 `ConnectionModeCoordinator.apply(...)`。

本地 Gateway 生命周期主线集中在 `GatewayProcessManager.swift`、`GatewayLaunchAgentManager.swift`、`LaunchAgentManager.swift`、`LaunchdManager.swift`、`GatewayAutostartPolicy.swift`。这些文件处理启动、停止、attach 现有进程、launch agent 和自动启动策略。

远程连接主线集中在 `GatewayEndpointStore.swift`、`RemoteTunnelManager.swift`、`RemotePortTunnel.swift`、`RemoteGatewayProbe.swift`、`CommandResolver.swift`、`OpenClawMacCLI/ConfigureRemoteCommand.swift`。App 模式切到 remote 时，会停止本地 Gateway，准备远程 tunnel，再配置控制通道。

Gateway 请求/推送主线集中在 `GatewayConnection.swift`、`ControlChannel.swift`、`GatewayPushSubscription.swift`。业务功能一般不会直接处理 socket 细节，而是通过 `GatewayConnection.shared.request...`、`subscribe(...)` 或特定 helper 方法进入协议层。

菜单栏和主要 UI 主线在 `MenuBar.swift`、`MenuContentView.swift`、`MenuSessionsInjector.swift`、`DashboardManager.swift`、`DashboardWindowController.swift`、`SettingsRootView.swift`。设置页再分流到 `GeneralSettings.swift`、`ChannelsSettings.swift`、`ConfigSettings.swift`、`PermissionsSettings.swift`、`VoiceWakeSettings.swift`、`SkillsSettings.swift`、`CronSettings.swift` 等。

语音和 talk mode 主线在 `VoiceWakeRuntime.swift`、`VoiceWakeForwarder.swift`、`VoiceWakeOverlayController+*.swift`、`VoicePushToTalk.swift`、`TalkModeRuntime.swift`、`TalkModeController.swift`、`TalkOverlay.swift`。屏幕、相机、音频能力分别散落在 `ScreenSnapshotService.swift`、`ScreenRecordService.swift`、`CameraCaptureService.swift`、`AudioInputDeviceObserver.swift`、`MicLevelMonitor.swift` 等。

## 推荐阅读顺序

第一步读 `apps/macos/Package.swift`，先确认 target、product、依赖和资源布局。它能帮助你理解为什么同一个目录里既有 App，又有 CLI 和 library。

第二步读 `apps/macos/Sources/OpenClaw/MenuBar.swift`。这是 macOS App 的真实入口，可以看到菜单栏 App 如何被创建、状态如何影响 Gateway、设置窗口如何挂载。

第三步读 `apps/macos/Sources/OpenClaw/AppState.swift` 和 `apps/macos/Sources/OpenClaw/ConnectionModeCoordinator.swift`。前者解释全局状态模型，后者解释状态如何落到本地/远程 Gateway 行为。

第四步读 `apps/macos/Sources/OpenClaw/GatewayConnection.swift`、`apps/macos/Sources/OpenClaw/ControlChannel.swift`、`apps/macos/Sources/OpenClaw/GatewayEndpointStore.swift`。这三块能把“UI 点击”与“Gateway 协议请求”连接起来。

第五步按兴趣分支阅读：想看 CLI，读 `apps/macos/Sources/OpenClawMacCLI/EntryPoint.swift` 和同目录命令文件；想看发现逻辑，读 `apps/macos/Sources/OpenClawDiscovery`；想看 UI，读 `MenuContentView.swift`、`SettingsRootView.swift`、`DashboardManager.swift`；想看语音，读 `VoiceWakeRuntime.swift` 和 `TalkModeRuntime.swift`。

第六步最后看 `apps/macos/Tests/OpenClawIPCTests`。这个测试 target 名称容易误导，但它实际上提供了很多行为索引；用测试文件名反查对应源码，是理解局部功能最快的方式。

## 常见误区

不要把 `apps/macos` 当作 Gateway 后端本体。这里主要是 macOS 原生客户端和伴生工具；Gateway 协议方法虽然在 `GatewayConnection.Method` 中集中列出，但实际服务端实现位于仓库其他区域。

不要被 `OpenClawIPCTests` 名称限制理解。测试目录虽然叫 IPC tests，但覆盖了 App 状态、Gateway、CLI、UI smoke、远程发现、权限、语音等大量 macOS 行为。

不要认为 `OpenClawDiscovery` 只给 UI 用。`Package.swift` 显示主 App 和 `OpenClawMacCLI` 都依赖它，因此它是 App/CLI 共享的发现层。

不要跳过 `ConnectionModeCoordinator.swift`。很多“为什么本地 Gateway 停了”“为什么远程模式要启动 node service/tunnel”“为什么切模式会断开 WebChat”的答案，都不在某个按钮 View 里，而在这里集中表达。

不要把签名和打包逻辑理解为 Swift 源码的一部分。`apps/macos/README.md` 指向的是脚本驱动流程；目录内 `Packaging` 和 `Icon.icon` 是素材，实际 packaging/codesign 脚本在仓库脚本区。根据当前片段推断，`apps/macos` 保存 App 工程和打包输入，完整发布流程需要结合根目录脚本阅读。
