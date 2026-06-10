# 子系统：apps/android/app/src/main/java/ai/openclaw/app/ui

## 解决什么问题

`apps/android/app/src/main/java/ai/openclaw/app/ui` 是 Android 客户端的 Jetpack Compose UI 子系统，负责把 `MainViewModel` 暴露的连接、聊天、语音、画布、设置、网关诊断等状态组织成移动端可交互界面。它不直接拥有网关连接、节点能力、聊天协议或语音运行时，而是通过 `MainViewModel` 读取 `StateFlow` 状态并调用动作方法，把用户输入转交给 `NodeRuntime`、`gateway`、`node`、`voice`、`chat` 等下层模块。

从职责边界看，这个目录主要解决三类问题：应用入口后的页面编排、移动端功能屏幕呈现、UI 内部设计系统复用。`MainActivity` 只设置 `OpenClawTheme`、挂载 `RootScreen`，并在 runtime 初始化后附着相机、短信等权限相关 UI 能力；真正的页面状态切换由 `RootScreen`、`ShellScreen`、`OnboardingFlow` 等组件完成。

## 相关目录和文件

入口链路从 `apps/android/app/src/main/java/ai/openclaw/app/MainActivity.kt` 进入 `apps/android/app/src/main/java/ai/openclaw/app/ui/RootScreen.kt`。`RootScreen` 根据 `viewModel.onboardingCompleted` 决定进入 `OnboardingFlow` 还是主应用 shell。

主界面编排集中在 `apps/android/app/src/main/java/ai/openclaw/app/ui/ShellScreen.kt`，它维护 Home、Chat、Voice、Sessions、Settings、Providers 等 tab 状态，并负责 `CommandPalette`、网关信任弹窗、设置详情路由等横切 UI。`apps/android/app/src/main/java/ai/openclaw/app/ui/PostOnboardingTabs.kt` 是另一套 tab 结构；根据当前片段推断，它可能是旧版或并行保留的移动首页实现，依据是当前入口 `RootScreen` 选择的是 `ShellScreen`，而 `PostOnboardingTabs` 未在入口片段中出现。

功能屏幕分布在同级文件中：连接页是 `ConnectTabScreen.kt`，聊天入口是 `ChatSheet.kt` 并下沉到 `ui/chat/ChatScreen.kt`、`ChatComposer.kt`、`ChatMessageViews.kt` 等；语音页是 `VoiceTabScreen.kt` 和 `VoiceScreen.kt`；WebView 画布是 `CanvasScreen.kt`；设置总路由在 `SettingsScreens.kt`，部分详情拆到 `ChannelsSettingsScreen.kt`、`SkillsSettingsScreen.kt`、`NodesDevicesSettingsScreen.kt`、`HealthLogsSettingsScreen.kt` 等。

设计系统在 `ui/design` 和 `MobileUiTokens.kt`。前者提供 `ClawDesignTheme`、`ClawTheme`、`ClawPanel`、`ClawScaffold`、`ClawPrimaryButton` 等统一组件；后者保留移动端颜色、字体、渐变和旧式 token 访问器。

## 核心对象

`RootScreen` 是顶层 Compose 分流器，只判断 onboarding 是否完成。它本身不处理业务。

`ShellScreen` 是当前主 UI 的导航中枢。内部 `Tab` 枚举定义主区域，`SettingsRoute` 定义设置详情页。它监听 `requestedHomeDestination` 来响应外部 intent 或助理启动请求，并在 tab 切换时调用 `viewModel.setVoiceScreenActive`，确保语音页生命周期影响运行时。

`OnboardingFlow` 负责首次连接和授权流程。它包含 Welcome、Gateway、Recovery、Permissions 步骤，支持 setup code、手动 host/port/tls、QR 扫描、附近 gateway、TLS 指纹信任和权限检查。

`GatewayConfigResolver.kt` 是 UI 层中少数非 Composable 的解析辅助对象，定义 `GatewayConnectConfig`、`GatewaySetupCode`、`GatewayEndpointConfig` 等结构，负责 setup code 解码、URL 解析、手动 endpoint 组装，以及禁止非 loopback 的不安全远程 `ws/http` 连接。

`CanvasScreen` 是 Compose 与 Android `WebView` 的桥。它通过 `AndroidView` 创建 WebView，关闭文件访问，开启 JavaScript 和 DOM storage，并通过 `WebViewCompat.addWebMessageListener` 暴露 `openclawCanvasA2UIAction`，再交给 `viewModel.handleCanvasA2UIActionFromWebView`。

`ChatScreen` 组织聊天消息、历史加载、流式 assistant 文本、待处理 tool call、图片附件和发送动作。`VoiceTabScreen` 组织手动麦克风、Talk Mode、扬声器开关、实时转写、输入音量和对话气泡。

## 运行流程

应用启动后，`MainActivity.onCreate` 创建 `MainViewModel`，设置沉浸式窗口，监听 `preventSleep` 和 `runtimeInitialized`。当 runtime 准备好时，Activity 调用 `viewModel.attachRuntimeUi` 注入 lifecycle 和权限请求器，并启动 `NodeForegroundService`。

Compose 内容树从 `OpenClawTheme -> Surface -> RootScreen` 开始。未完成 onboarding 时，`OnboardingFlow` 收集连接状态、发现到的 gateways、保存的 token、pending trust prompt 等状态；用户提交连接配置后，UI 调用 `viewModel.connect` 或相关 setter，runtime 负责实际连接。连接和节点都 ready 后，流程进入权限页并最终调用 `setOnboardingCompleted(true)`。

完成 onboarding 后进入 `ShellScreen`。Home/overview 负责概览和导航；Chat tab 调用聊天加载、刷新 session、发送消息；Voice tab 处理录音权限并切换 mic/talk 状态；Settings tab 根据 `SettingsRoute` 展示具体设置；Canvas 相关页面把 WebView 附着到 `viewModel.canvas`，可见性变化时暂停或恢复 WebView。

## 上下游依赖

上游入口是 `MainActivity.kt`、`MainViewModel.kt` 和 Android lifecycle。UI 几乎所有状态都来自 `MainViewModel` 中的 `StateFlow`：连接状态、gateway 信息、聊天消息、语音状态、画布状态、设置偏好、pending trust、模型目录、skills、channels、health logs 等。

下游运行时包括 `apps/android/app/src/main/java/ai/openclaw/app/NodeRuntime.kt`、`node/CanvasController.kt`、`node/CameraCaptureManager.kt`、`gateway/GatewayEndpoint.kt`、`gateway/GatewayProtocol.kt`、`voice/*`、`chat/*`。UI 不应绕过 `MainViewModel` 直接控制这些运行时对象，例外是 `viewModel.canvas`、`viewModel.camera` 这类由 ViewModel 明确暴露的窄接口。

外部 Android 依赖包括 Compose Material3、Activity Result API、Android WebView、AndroidX WebKit、ML Kit barcode scanner、系统权限和 settings intent。setup code 解析依赖 Kotlin serialization JSON 和 Java `URI`、`Base64`。

## 修改时最容易踩的坑

第一，生命周期和可见性不能只看 Compose 重组。语音页在 `DisposableEffect` 中关闭 manual mic，`ShellScreen` 在 tab 切换时调用 `setVoiceScreenActive`；改导航时如果漏掉这些调用，可能导致麦克风、TTS 或 Talk Mode 状态异常。

第二，网关连接配置有安全约束。`GatewayConfigResolver.kt` 明确只允许 loopback 使用非 TLS，远程 gateway 需要 `wss/https` 或等价安全暴露。不要在 UI 表单里绕过 `parseGatewayEndpointResult` 或复制一套宽松解析逻辑。

第三，WebView 桥接是安全边界。`CanvasA2UIActionBridge` 虽然 `allowedOriginRules` 是 `*`，但真正处理前会调用 `viewModel.isTrustedCanvasActionUrl`。修改画布 action 时要保持 trusted page 校验、主 frame 校验和 detach/destroy 清理。

第四，当前存在两套视觉 token：`ui/design/ClawTheme` 与 `MobileUiTokens.kt`。新增主 shell 页面优先观察邻近文件使用的是 `ClawDesignTheme` 还是旧 `mobile*` token，避免同一屏混用造成风格和暗色模式不一致。

第五，设置页会在 `LaunchedEffect(isConnected)` 中刷新 usage、cron、agents 等远端摘要。新增设置项时要区分本地偏好、gateway 摘要和运行时动作，避免无连接时触发无意义请求或显示误导状态。

## 推荐阅读顺序

1. `apps/android/app/src/main/java/ai/openclaw/app/MainActivity.kt`：了解 Compose 挂载、runtime UI 附着和前台服务启动。
2. `apps/android/app/src/main/java/ai/openclaw/app/MainViewModel.kt`：理解 UI 状态和动作的统一出口。
3. `apps/android/app/src/main/java/ai/openclaw/app/ui/RootScreen.kt`、`apps/android/app/src/main/java/ai/openclaw/app/ui/ShellScreen.kt`：掌握 onboarding 与主 shell 的分流、tab 和设置路由。
4. `apps/android/app/src/main/java/ai/openclaw/app/ui/OnboardingFlow.kt`、`apps/android/app/src/main/java/ai/openclaw/app/ui/GatewayConfigResolver.kt`：理解首次配对、setup code、TLS trust 和 endpoint 校验。
5. `apps/android/app/src/main/java/ai/openclaw/app/ui/chat/ChatScreen.kt`、`apps/android/app/src/main/java/ai/openclaw/app/ui/VoiceTabScreen.kt`、`apps/android/app/src/main/java/ai/openclaw/app/ui/CanvasScreen.kt`：分别学习聊天、语音和画布三条核心交互链路。
6. `apps/android/app/src/main/java/ai/openclaw/app/ui/SettingsScreens.kt`、`apps/android/app/src/main/java/ai/openclaw/app/ui/design/ClawTheme.kt`、`apps/android/app/src/main/java/ai/openclaw/app/ui/MobileUiTokens.kt`：最后看设置页组织方式和设计系统。
