# 目录：apps

## 它负责什么

`apps` 是 OpenClaw 仓库里的原生客户端与平台辅助工具区，覆盖 Android、iOS、macOS 桌面伴随应用、共享 Swift 包、语音唤醒组件和一个隔离的 macOS TTS helper。它不是核心 TypeScript gateway 或 plugin runtime 的所在地，而是这些平台端应用连接、展示、控制 OpenClaw Gateway 的外壳与节点实现。

从当前片段看，这个目录的主线是“设备端作为 node 连接 gateway”：移动端负责 onboarding、连接配置、权限、聊天、语音、屏幕/相机/媒体能力和推送；macOS 端负责菜单栏应用、gateway 启动/连接、IPC、设置界面、dashboard/canvas、执行审批和本机 node mode；`shared/OpenClawKit` 提供 Swift 平台共用协议、连接与聊天 UI 基础；`swabble` 提供语音唤醒/转写能力，供 CLI 或 macOS app 复用。

## 直接子目录地图

`apps/android` 是 Android 原生应用，使用 Kotlin、Jetpack Compose、Gradle。根据 `README.md` 和文件结构，它包含 `app` 主应用 module、`benchmark` 性能 benchmark module、Gradle 配置、release bundle 脚本和启动/语音性能脚本。功能处于 alpha/rebuild 状态，重点是 Connect、Chat、Settings、Voice、Screen、push、biometric/security、gateway pairing。

`apps/ios` 是 iPhone app，SwiftUI/XcodeGen 项目。它包含主 app 源码 `Sources`、测试 `Tests`、`ActivityWidget`、`ShareExtension`、`WatchApp`、`WatchExtension`、签名与版本配置、Fastlane beta/TestFlight 流程。README 明确说它作为 `role: node` 连接 OpenClaw Gateway，当前是 super-alpha/internal-use。

`apps/macos` 是 macOS companion app，SwiftPM package。它产出菜单栏 app executable `OpenClaw`、CLI executable `openclaw-mac`，以及 `OpenClawIPC`、`OpenClawDiscovery` library。源码集中在 `Sources/OpenClaw`，并拆出 `Sources/OpenClawMacCLI`、`Sources/OpenClawIPC`、`Sources/OpenClawDiscovery`。它还包含 packaging、icon、dmg 资源和测试。

`apps/macos-mlx-tts` 是独立 SwiftPM 包，只构建 `openclaw-mlx-tts` helper。Package 注释说明它被隔离出来，是为了避免普通 macOS app 测试编译完整 MLX audio stack。

`apps/shared/OpenClawKit` 是 iOS/macOS 共享 Swift package，产出 `OpenClawProtocol`、`OpenClawKit`、`OpenClawChatUI`。它承载 gateway protocol models、WebSocket/channel 抽象、连接问题建模、共享聊天 UI 与资源。

`apps/swabble` 是 Swift 6.2 语音唤醒/转写项目，包含 library `Swabble`、`SwabbleKit` 和 executable `swabble`。README 描述它基于 Speech.framework，提供 wake word、hook daemon、file transcribe、launchd/service stub，以及可供 iOS/macOS 复用的 wake-gate utilities。

## 关键入口

Android 的构建入口是 `apps/android/settings.gradle.kts`、`apps/android/build.gradle.kts`、`apps/android/app/build.gradle.kts`。运行入口根据当前片段可定位到 `apps/android/app/src/main/AndroidManifest.xml` 和 `apps/android/app/src/main/java/ai/openclaw/app/MainActivity.kt`。业务连接主干集中在 `apps/android/app/src/main/java/ai/openclaw/app/NodeRuntime.kt`，其中出现 gateway connection refresh、mic capture connection state 等逻辑。

iOS 的项目生成入口是 `apps/ios/project.yml`，应用入口是 `apps/ios/Sources/OpenClawApp.swift`，其中定义 `@main struct OpenClawApp`，初始化 `NodeAppModel` 与 `GatewayConnectionController`，并注册 `OpenClawAppDelegate` 处理 APNs、background refresh、notification delegate 等系统生命周期。根视图从 `apps/ios/Sources/RootView.swift` 进入 `RootCanvas`，再扩展到 tabs、onboarding、settings、gateway prompts 等 UI。

macOS 的 package 入口是 `apps/macos/Package.swift`。主 app target 是 `Sources/OpenClaw`，CLI 入口在 `apps/macos/Sources/OpenClawMacCLI/EntryPoint.swift`。主连接单例在 `apps/macos/Sources/OpenClaw/GatewayConnection.swift`，菜单栏和界面入口可从 `MenuBar.swift`、`MenuContentView.swift`、`AppState.swift`、`GatewayProcessManager.swift`、`ConnectionModeCoordinator.swift` 这一组开始看。

共享 Swift 包的入口是 `apps/shared/OpenClawKit/Package.swift`。协议模型主要在 `apps/shared/OpenClawKit/Sources/OpenClawProtocol/GatewayModels.swift`，WebSocket/channel 基础在 `apps/shared/OpenClawKit/Sources/OpenClawKit/GatewayChannel.swift`，连接问题归因在 `apps/shared/OpenClawKit/Sources/OpenClawKit/GatewayConnectionProblem.swift`。

`swabble` 的入口是 `apps/swabble/Package.swift`，CLI 在 `apps/swabble/Sources/swabble`，核心 Speech pipeline 在 `apps/swabble/Sources/SwabbleCore`，可复用 wake gate 在 `apps/swabble/Sources/SwabbleKit`。

## 主流程位置

移动端主流程大致是：首次启动进入 onboarding/connect，用户通过 setup code、QR/manual 配置 gateway；连接信息和 token 进入本地安全存储；app 通过 WebSocket 以 node 身份和 gateway 通信；之后 Chat、Voice、Screen、Camera、Location、Media、Permissions、Push 等模块围绕这个连接提供能力。Android 这条线根据当前片段推断主要落在 `MainActivity.kt`、`NodeRuntime.kt`、`ui/*`、`gateway/*`、`voice/*`、`node/*`。iOS 这条线更清晰地分布在 `OpenClawApp.swift`、`Gateway/GatewayConnectionController.swift`、`Gateway/GatewaySettingsStore.swift`、`Onboarding/*`、`RootCanvas.swift`、`RootTabs.swift`、`Settings/*`、`Push/*`、`Services/*`。

macOS 主流程是 companion app 启动后管理 gateway 连接和本机状态：`AppState` 维护 UI/连接模式，`GatewayProcessManager` 和 launch agent 相关文件处理 gateway 进程，`GatewayConnection.shared` 提供请求、订阅、chat、skills、config、health 等访问点，菜单栏/设置/窗口组件通过它读取和修改 gateway 状态。node mode 相关流程在 `apps/macos/Sources/OpenClaw/NodeMode`，dashboard/canvas 流程在 `DashboardManager.swift`、`CanvasManager.swift`、`CanvasWindowController.swift` 等位置。

共享协议流程位于 `OpenClawKit`：`OpenClawProtocol` 定义请求/响应数据结构，`GatewayChannel` 封装 WebSocket 收发和错误映射，`OpenClawChatUI` 提供跨 iOS/macOS 的聊天展示基础。平台 app 不应各自重新发明协议层，而应优先复用这里。

## 推荐阅读顺序

1. 先读 `apps/ios/README.md`、`apps/android/README.md`、`apps/macos/README.md`，了解三个端的定位、构建方式和当前成熟度。
2. 再读三个 manifest：`apps/android/app/build.gradle.kts`、`apps/ios/project.yml`、`apps/macos/Package.swift`，建立 target/module 关系。
3. 看共享层 `apps/shared/OpenClawKit/Package.swift`、`OpenClawProtocol/GatewayModels.swift`、`OpenClawKit/GatewayChannel.swift`，先理解 app 与 gateway 的共同协议。
4. 看 iOS 入口 `apps/ios/Sources/OpenClawApp.swift`、`RootCanvas.swift`、`Gateway/GatewayConnectionController.swift`，这是当前片段里最完整的移动端主流程样本。
5. 看 Android 的 `MainActivity.kt`、`NodeRuntime.kt` 和 `ui`、`gateway`、`voice` 相关包，用 iOS 的结构作对照。
6. 最后看 macOS 的 `AppState.swift`、`GatewayConnection.swift`、`GatewayProcessManager.swift`、`MenuBar.swift`、`NodeMode/*`，理解桌面伴随应用如何管理 gateway 和本机能力。

## 常见误区

不要把 `apps` 当成 OpenClaw 核心业务后端。核心 gateway、plugin SDK、channels、loader 等在仓库其他目录；`apps` 主要是平台客户端和本机 companion。

不要把 `apps/shared/OpenClawKit` 理解成普通工具库。它承载 iOS/macOS 共用的协议与连接抽象，很多平台行为需要先看这里再看具体 app。

不要把 `apps/macos-mlx-tts` 并入 `apps/macos` 主应用理解。它被单独拆包是有意隔离依赖和编译成本，普通 macOS app 测试不应默认拉入 MLX audio stack。

不要只看 UI 文件判断流程。连接、推送、权限、后台唤醒、执行审批等关键行为通常分散在 controller、store、service、delegate、manager 中，例如 iOS 的 `OpenClawApp.swift` 和 `GatewayConnectionController.swift`，macOS 的 `GatewayConnection.swift` 和 `GatewayProcessManager.swift`。

不要假设 Android/iOS/macOS 三端完全同构。它们共享“连接 gateway 并作为 node/companion 提供能力”的方向，但生命周期、权限模型、发布流程、推送机制和本机能力边界不同。
