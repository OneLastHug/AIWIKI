# 目录：apps/android

## 它负责什么

`apps/android` 是 OpenClaw 的 Android 客户端工程目录，整体上是一个独立的 Gradle/Android 项目，而不是根仓库 TS/Node 主工程的一部分。它负责构建 Android 端应用包、维护 Android 专属资源、声明 Android 权限和入口、组织应用与基准测试模块，并通过产品 flavor 区分不同分发渠道。

从已读取到的工程配置看，这里使用 Kotlin、Jetpack Compose、Android Gradle Plugin、Material 组件、CameraX、WebKit、OkHttp、kotlinx serialization、AndroidX Security Crypto、dnsjava 等依赖。`app/build.gradle.kts` 还把 `../../shared/OpenClawKit/Sources/OpenClawKit/Resources` 加入 `main` source set 的 assets，说明 Android 客户端会复用 `apps/shared` 下的一部分跨平台资源。根据当前片段推断，Android 端并不是核心 agent/runtime 的实现位置，而是面向移动端用户体验、设备能力接入和本地分发打包的应用壳与客户端层。

这个目录同时包含 release 签名、APK 命名、R8 资源处理、lint、单元测试、benchmark 和若干脚本入口，因此阅读时应把它看作“Android 应用工程边界”，不要把它误认为根仓库的插件系统、provider 路由或 gateway 主实现。

## 直接子目录地图

`app` 是主 Android 应用模块。它包含 `app/build.gradle.kts`、`app/src/main`、`app/src/debug`、`app/src/play`、`app/src/thirdParty`、`app/src/test`、`app/src/testThirdParty` 等 source set。`main` 放通用应用代码、资源和主 manifest；`debug` 放调试构建的 manifest 或代码；`play` 与 `thirdParty` 对应两个分发 flavor；测试 source set 则用于普通单测和第三方渠道相关测试。

`benchmark` 是 Android benchmark 模块，在 `settings.gradle.kts` 中以 `include(":benchmark")` 方式注册。它的职责是性能或启动相关验证，不是主应用运行入口。目录里还有 `scripts/perf-online-benchmark.sh`、`scripts/perf-startup-benchmark.sh`、`scripts/perf-startup-hotspots.sh`，说明 benchmark 与脚本配合用于性能场景执行。

`gradle` 保存 Gradle wrapper、版本目录和 JVM 配置。关键文件包括 `gradle/libs.versions.toml`、`gradle/wrapper/gradle-wrapper.properties`、`gradle/gradle-daemon-jvm.properties`。依赖版本与插件别名主要从这里进入构建脚本。

`scripts` 是 Android 工程辅助脚本目录，已看到 `scripts/build-release-aab.ts`、`scripts/voice-e2e.sh` 和性能脚本。它们服务于发布包构建、语音端到端验证和性能测试，不是应用代码本身。

`THIRD_PARTY_LICENSES` 放第三方授权文本。当前能看到 `THIRD_PARTY_LICENSES/MANROPE_OFL.txt`，与 `app/src/main/res/font/manrope_*.ttf` 字体资源对应。

## 关键入口

工程级入口是 `apps/android/settings.gradle.kts`。它设置插件仓库、依赖仓库、`rootProject.name = "OpenClawNodeAndroid"`，并注册 `:app` 与 `:benchmark` 两个模块。判断这个 Android 工程由哪些模块组成，应先看这个文件。

根构建入口是 `apps/android/build.gradle.kts`。它只集中声明 Android、Kotlin、ktlint 等 Gradle 插件别名，并采用 `apply false`，实际配置下沉到模块级脚本。

主应用构建入口是 `apps/android/app/build.gradle.kts`。这里定义 `namespace = "ai.openclaw.app"`、`applicationId = "ai.openclaw.app"`、`compileSdk = 36`、`minSdk = 31`、`targetSdk = 36`、`versionCode = 2026052601`、`versionName = "2026.5.26"`，同时配置 `play` 与 `thirdParty` flavor、`debug` 与 `release` build type、release 签名属性、Compose、资源打包排除、lint、单元测试和依赖。要理解 Android 包如何构建、如何命名、如何区分渠道，应重点读这里。

运行时入口的声明位置是 `apps/android/app/src/main/AndroidManifest.xml`，渠道和调试差异则分别在 `apps/android/app/src/play/AndroidManifest.xml`、`apps/android/app/src/thirdParty/AndroidManifest.xml`、`apps/android/app/src/debug/AndroidManifest.xml`。当前片段没有展开 manifest 内容，因此具体启动 `Activity` 类名需要继续读取 manifest 才能确认；根据 Android 工程惯例和 namespace，可推断主入口类大概率位于 `apps/android/app/src/main/java` 下的 `ai.openclaw.app` 包内，但类名不能仅凭当前片段断言。

资源入口集中在 `apps/android/app/src/main/res`。其中 `values/strings.xml`、`values/themes.xml`、`values-night/themes.xml`、`values/colors.xml`、`values/assistant.xml` 管理文字、主题、颜色和 assistant 相关资源；`xml/network_security_config.xml`、`xml/file_paths.xml`、`xml/shortcuts.xml`、`xml/backup_rules.xml`、`xml/data_extraction_rules.xml` 管理 Android 平台配置；`mipmap-*` 是 launcher 图标资源；`font/manrope_*.ttf` 是应用字体。

## 主流程位置

构建主流程从 `apps/android/settings.gradle.kts` 进入，解析模块后进入 `apps/android/app/build.gradle.kts`。普通开发构建走 `debug` build type；发布构建走 `release` build type，并要求 `OPENCLAW_ANDROID_STORE_FILE`、`OPENCLAW_ANDROID_STORE_PASSWORD`、`OPENCLAW_ANDROID_KEY_ALIAS`、`OPENCLAW_ANDROID_KEY_PASSWORD` 这些 Gradle property 齐全。缺少签名属性时，release 相关任务会直接报错，这是发布流程的第一道门槛。

渠道分发流程由 `flavorDimensions += "store"` 和 `productFlavors` 控制。`play` 与 `thirdParty` 共享大多数 `main` 代码和资源，但可以在各自的 source set 中覆盖 manifest 或补充渠道代码。对应路径是 `apps/android/app/src/play` 和 `apps/android/app/src/thirdParty`。测试也有 `apps/android/app/src/testThirdParty`，说明第三方渠道可能有单独行为需要验证。

应用资源装配流程除 Android 标准 `res` 外，还会把 `apps/shared/OpenClawKit/Sources/OpenClawKit/Resources` 作为 assets 注入主应用。这是 Android 与共享跨平台资源的连接点。阅读 Android 端资源或协议提示类内容时，不应只看 `app/src/main/res`，还要意识到 shared 资源会参与打包。

性能验证流程主要落在 `apps/android/benchmark` 和 `apps/android/scripts/perf-*.sh`。根据当前片段推断，`benchmark` 模块负责 Android instrumentation 或 macrobenchmark 一类的性能测试承载，脚本则封装常用启动、热点或在线性能场景。

## 推荐阅读顺序

第一步读 `apps/android/settings.gradle.kts`，先确认这是双模块 Android 工程：`:app` 是主应用，`:benchmark` 是性能验证模块。

第二步读 `apps/android/gradle/libs.versions.toml`，建立依赖和插件版本地图。Android 工程大量行为由 Gradle 插件、AndroidX、Compose、CameraX、OkHttp 等依赖决定，先知道版本来源会减少后续误判。

第三步读 `apps/android/app/build.gradle.kts`，重点看 `android {}`、`productFlavors`、`buildTypes`、`sourceSets`、`dependencies` 和 release 相关配置。这是理解打包、渠道、权限能力依赖和测试策略的核心文件。

第四步读 `apps/android/app/src/main/AndroidManifest.xml`，再对照 `apps/android/app/src/debug/AndroidManifest.xml`、`apps/android/app/src/play/AndroidManifest.xml`、`apps/android/app/src/thirdParty/AndroidManifest.xml`。这一组文件能回答“应用从哪个组件启动”“不同构建或渠道改了什么”。

第五步进入 `apps/android/app/src/main/java`，从 manifest 指向的启动组件开始追 Compose UI、状态管理、设备能力调用和网络/本地存储边界。当前概览没有逐文件展开，因此这里应以后续专题阅读为准。

第六步按需读 `apps/android/benchmark` 与 `apps/android/scripts`。只有当关注启动性能、在线性能、语音 e2e 或发布包构建时，才需要深入这些路径。

## 常见误区

不要把 `apps/android` 当成 OpenClaw 核心 runtime 或插件系统的主实现。核心 TS、gateway、plugin SDK 等在根仓库其他目录；Android 目录主要是移动端应用工程和平台能力接入。

不要只看 `app/src/main` 就认为掌握了完整行为。`debug`、`play`、`thirdParty` source set 会通过 Gradle variant 参与合并，manifest、代码和测试都可能因构建变体不同而变化。

不要忽略 `apps/shared` 资源注入。`app/build.gradle.kts` 明确把共享 OpenClawKit 资源加入 assets，Android 打包内容可能来自 `apps/android` 之外的邻近目录。

不要把 `benchmark` 理解为普通业务模块。它在 `settings.gradle.kts` 中独立注册，配合性能脚本使用，主要服务性能验证，不是主应用功能入口。

不要假设 release 构建能在任意环境直接跑通。`app/build.gradle.kts` 对 release 签名属性有硬性校验，缺少本地签名配置会失败；这属于发布安全边界，不是普通编译错误。

不要根据依赖名过度推断具体功能实现。例如看到 CameraX、WebKit、dnsjava、Security Crypto 只能说明应用具备相应能力依赖；具体调用路径仍需继续读取 `apps/android/app/src/main/java` 下的代码和 manifest 声明。
