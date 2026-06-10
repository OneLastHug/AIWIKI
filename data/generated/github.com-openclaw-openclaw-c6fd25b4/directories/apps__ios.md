# 目录：apps/ios

## 它负责什么

`apps/ios` 是 OpenClaw 的 Apple 移动端应用目录，主要承载 iOS 主 App、Share Extension、Live Activity Widget、watchOS App/Extension、测试与发布配置。它不是核心 TypeScript 运行时的一部分，而是一个 Swift / SwiftUI 客户端：负责在 iPhone 上发现并连接 OpenClaw gateway，展示状态与聊天/语音/屏幕等交互界面，把 iOS 设备能力暴露给 gateway，并桥接推送、通知、Watch、Live Activity、分享入口等系统能力。

从 `project.yml` 看，这里使用 XcodeGen 风格组织工程，主 target 是 `OpenClaw`，部署目标是 iOS 18，Swift 版本为 6，并依赖相邻的 `apps/shared/OpenClawKit`、`apps/swabble` 以及 WebRTC 包。主应用还嵌入 `OpenClawShareExtension`、`OpenClawActivityWidget` 和 `OpenClawWatchApp`。因此学习这个目录时，应把它理解为“OpenClaw gateway 的 iOS 控制台与设备能力代理”，而不是单纯 UI 壳。

## 直接子目录地图

`apps/ios/Sources` 是主 App 代码根目录，也是最重要的阅读入口。它按功能拆分为 `Gateway`、`Model`、`Chat`、`Voice`、`Screen`、`Camera`、`Location`、`Contacts`、`Calendar`、`Reminders`、`Motion`、`Media`、`Push`、`LiveActivity`、`Onboarding`、`Permissions`、`Settings`、`Status`、`Services` 等模块。整体结构比较清楚：`Gateway` 管连接与发现，`Model` 管全局应用状态，其他目录多是 iOS 能力或界面分区。

`apps/ios/ShareExtension` 是系统分享扩展。它的入口在 `ShareExtension/ShareViewController.swift`，用于接收来自 iOS share sheet 的文本、网页、图片、视频等内容，再交给 OpenClaw 主应用或 agent 处理。

`apps/ios/ActivityWidget` 是 Live Activity / Widget 扩展。它包含 `ActivityWidget/OpenClawActivityWidgetBundle.swift` 和 `ActivityWidget/OpenClawLiveActivity.swift`，并复用 `Sources/LiveActivity/OpenClawActivityAttributes.swift` 作为 ActivityKit 属性定义。

`apps/ios/WatchApp` 和 `apps/ios/WatchExtension` 负责 watchOS 端。`WatchApp` 主要放 Watch 应用资源和 `Info.plist`，`WatchExtension/Sources` 放 Watch 端 SwiftUI 入口、收件箱、连接接收逻辑，例如 `WatchExtension/Sources/OpenClawWatchApp.swift`、`WatchExtension/Sources/WatchConnectivityReceiver.swift`。

`apps/ios/Tests` 是 iOS 侧测试目录，覆盖 gateway 连接、设置存储、安全、深链、聊天 transport、语音 wake、屏幕录制、推送通知桥、Watch 归一化等行为。`apps/ios/Tests/Logic` 放更偏纯逻辑的小测试。

`apps/ios/Config`、`apps/ios/fastlane`、`apps/ios/project.yml`、`apps/ios/version.json`、`apps/ios/VERSIONING.md`、`apps/ios/README.md` 是工程、签名、版本、发布与人工部署说明。`Config/Signing.xcconfig`、`Signing.xcconfig`、`LocalSigning.xcconfig.example` 说明本目录对本地签名和发布配置有较强依赖。

## 关键入口

主 App 的 SwiftUI 入口是 `apps/ios/Sources/OpenClawApp.swift`。这里定义 `OpenClawApp`，并包含 `OpenClawAppDelegate`。`OpenClawAppDelegate` 负责启动期注册后台刷新、远程通知、通知分类，以及把 APNs token、Watch prompt action、exec approval 推送等早到事件暂存后转交给 `NodeAppModel`。

主界面入口在 `apps/ios/Sources/RootView.swift`、`apps/ios/Sources/RootTabs.swift`、`apps/ios/Sources/RootCanvas.swift`。这些文件负责把全局模型和不同 tab / canvas 呈现出来，是理解用户看到什么、各功能页如何挂载的入口。

全局状态核心是 `apps/ios/Sources/Model/NodeAppModel.swift`。它是 `@Observable` 的主模型，集中持有 gateway 状态、agent 选择、深链 prompt、exec approval prompt、node/operator 两条 gateway session、语音 wake、talk mode、设备能力服务、Watch messaging、推送和后台状态等。学习主流程时，这个文件比单个 UI 页面更关键。

gateway 连接入口集中在 `apps/ios/Sources/Gateway/GatewayConnectionController.swift` 和 `apps/ios/Sources/Gateway/GatewayDiscoveryModel.swift`。前者处理发现结果、自动重连、手动连接、TLS 指纹信任提示、认证覆盖；后者负责发现 gateway 并维护发现状态、调试日志和发现结果。

系统能力分发入口是 `apps/ios/Sources/Capabilities/NodeCapabilityRouter.swift`。根据当前片段推断，它是 gateway 发起 `node.invoke` 类请求后，把请求路由到 camera、screen、location、contacts、calendar、reminders、motion 等服务的中心位置，依据是 `NodeAppModel` 中延迟构造 `capabilityRouter`，并且 `Sources` 下这些能力都有对应 service/controller。

## 主流程位置

连接主流程大致从 onboarding 或设置页发起，进入 `GatewayConnectionController`。自动发现由 `GatewayDiscoveryModel` 维护，连接时读取 `GatewaySettingsStore` 中的 token、bootstrap token、password 等配置，解析服务地址，校验 TLS 与信任指纹，然后把可用 gateway 地址交给 `NodeAppModel` 里的 gateway session 使用。相关 UI 分布在 `GatewayQuickSetupSheet.swift`、`GatewayTrustPromptAlert.swift`、`GatewayProblemView.swift`、`GatewayDiscoveryDebugLogView.swift` 和 `Onboarding/*`。

运行期交互主流程围绕 `NodeAppModel` 展开。主 App 启动后创建模型，UI 读取模型状态；gateway 连接成功后，node/operator session 分别承担设备能力请求与聊天/语音/配置类请求。聊天路径可从 `Chat/IOSGatewayChatTransport.swift` 看起，语音路径从 `Voice/TalkModeManager.swift`、`Voice/VoiceWakeManager.swift`、`Voice/VoiceTab.swift` 看起，屏幕能力从 `Screen/ScreenController.swift`、`Screen/ScreenRecordService.swift`、`Screen/ScreenTab.swift` 看起。

系统事件入口分散但最终大多回到模型。APNs 和后台唤醒在 `OpenClawApp.swift` 与 `Push/*`；Watch 互通在 `Services/WatchMessagingService.swift`、`Model/WatchReplyCoordinator.swift` 和 `WatchExtension/Sources/*`；Live Activity 在 `LiveActivity/LiveActivityManager.swift` 和 `ActivityWidget/*`；分享入口在 `ShareExtension/ShareViewController.swift`，并有 `Tests/ShareToAgentDeepLinkTests.swift` 验证深链路径。

## 推荐阅读顺序

1. 先读 `apps/ios/project.yml`，明确 target、依赖、嵌入扩展、Info.plist 权限、签名和测试 scheme。
2. 读 `apps/ios/README.md` 和 `apps/ios/VERSIONING.md`，了解当前 iOS App 的部署状态、APNs 预期、版本流程和已知限制。
3. 读 `apps/ios/Sources/OpenClawApp.swift`，掌握 App 生命周期、AppDelegate、通知和后台任务入口。
4. 读 `apps/ios/Sources/Model/NodeAppModel.swift`，建立全局状态、gateway session、agent、设备能力和系统事件之间的关系。
5. 读 `apps/ios/Sources/Gateway/*` 中的 `GatewayConnectionController.swift`、`GatewayDiscoveryModel.swift`、`GatewaySettingsStore.swift`，理解连接、发现、信任与配置。
6. 按兴趣进入功能目录：聊天看 `Chat`，语音看 `Voice`，屏幕看 `Screen`，Watch 看 `Services/WatchMessagingService.swift` 与 `WatchExtension/Sources`，推送看 `Push`。
7. 最后用 `apps/ios/Tests` 对照关键行为，尤其是 gateway、安全、深链、语音、推送和 Watch 相关测试。

## 常见误区

不要把 `apps/ios/Sources` 当成只有 UI 的目录。这里的 `NodeAppModel`、`GatewayConnectionController`、能力 service、推送桥和 Watch 桥都包含重要运行逻辑，很多行为不是简单的 SwiftUI 展示。

不要只看 `RootView` 就判断主流程。真正的业务状态与连接生命周期大多在 `NodeAppModel` 和 `Gateway` 目录，UI 只是消费这些状态并触发动作。

不要把 `ActivityWidget`、`ShareExtension`、`WatchExtension` 看成独立产品。它们是主 App 的系统扩展面：共享部分模型/协议/属性定义，并通过深链、WatchConnectivity、ActivityKit 或通知与主 App 形成闭环。

不要忽略 `project.yml`。权限文案、URL scheme、background modes、Live Activities、APNs 配置、嵌入扩展、Swift lint/format 脚本都在这里集中声明；很多“为什么某个系统能力可用或不可用”的答案不在 Swift 文件里。

不要把 gateway 发现等同于直接连接。当前代码片段显示连接前还会处理本机 instance id、存储的认证材料、服务端点解析、TLS 要求和指纹信任提示。理解连接问题时，应同时看 `GatewayDiscoveryModel`、`GatewayConnectionController`、`GatewaySettingsStore` 和相关测试。
