# 目录：apps/swabble

## 它负责什么

`apps/swabble` 是仓库中的一个独立 Swift Package，围绕 “本地语音识别 + wake word + hook 命令执行” 组织。它不是 OpenClaw 主 TypeScript 运行时的一部分，而更像一个旁路应用/工具：用 Swift 调 macOS/iOS 的 `Speech.framework`、`AVFoundation` 等系统能力，把麦克风或音频文件中的语音转成文本，再按 wake word 规则决定是否触发本地命令。

从 `Package.swift` 看，它定义了三个产品：`Swabble`、`SwabbleKit`、`swabble`。其中 `Swabble` 对应 `Sources/SwabbleCore`，承载配置、Speech pipeline、hook 执行、日志和 transcript 存储；`SwabbleKit` 对应 `Sources/SwabbleKit`，提供可复用的 wake word gate 逻辑；`swabble` 是 CLI 可执行程序，对应 `Sources/swabble`。README 中描述的核心用途是本地 wake-word hook daemon，默认 wake word 是 `clawd`，也支持 `--no-wake` 绕过 wake 检测。

这个目录还带有自己的 Swift 工程配置，例如 `.swiftformat`、`.swiftlint.yml`、`Package.resolved`、`scripts/format.sh`、`scripts/lint.sh`，说明它按 SwiftPM 子项目维护。

## 直接子目录地图

`apps/swabble/.github` 放该 Swift 子项目自己的 GitHub workflow 配置。这里只看到 `.github/workflows` 目录，角色应是自动化检查或发布流程入口。

`apps/swabble/Sources` 是主源码区，分成三个 target 目录：`SwabbleCore`、`SwabbleKit`、`swabble`。其中 `SwabbleCore` 是库核心；`SwabbleKit` 是更小的可复用 wake gate 工具包；`swabble` 是命令行程序。

`apps/swabble/Sources/SwabbleCore` 下按领域继续分层：`Config` 管配置结构和读写；`Hooks` 管触发外部命令；`Speech` 管麦克风、音频转换和 Speech framework pipeline；`Support` 放日志、输出格式、transcript 存储、AttributedString 辅助等支撑能力。

`apps/swabble/Sources/SwabbleKit` 当前主要是 `WakeWordGate.swift`，封装 wake word 匹配、去除触发词、基于 speech segment 的间隔判断等逻辑。

`apps/swabble/Sources/swabble` 是 CLI target。`CLI` 目录注册命令描述和命令树；`Commands` 目录放每个子命令的执行实现；`main.swift` 是程序入口和分发层。

`apps/swabble/Tests` 分成 `SwabbleKitTests` 和 `swabbleTests`。前者覆盖 wake word gate，后者覆盖 swabble 核心配置等行为。

`apps/swabble/docs` 当前包含 `spec.md`，应是该工具的设计/规格说明补充。`apps/swabble/scripts` 放本子项目的格式化和 lint 脚本。

## 关键入口

构建和 target 入口在 `apps/swabble/Package.swift`。这里能看到 Swift 工具链版本、平台约束、三个 products、依赖、target 到目录的映射。阅读这个文件可以先建立 “库核心、工具包、CLI” 三层结构。

运行入口在 `apps/swabble/Sources/swabble/main.swift`。它先检查 macOS 版本可用性，要求 macOS 26 或更新；随后构造 `Program(descriptors:)`，解析 `CommandLine.arguments`，再把解析后的 `CommandInvocation` 分发到具体命令。`dispatchSwabble` 是第一层命令分发，`mic`、`service` 有二级子命令，其余如 `serve`、`transcribe`、`test-hook`、`doctor`、`setup` 等通过 `swabbleHandlers` 映射到对应 command struct。

命令注册入口在 `apps/swabble/Sources/swabble/CLI/CLIRegistry.swift`。它把 `ServeCommand`、`TranscribeCommand`、`TestHookCommand`、`MicList`、`MicSet`、`ServiceInstall` 等组装成 Commander 的 `CommandDescriptor` 树。想知道 CLI 暴露了哪些命令，优先看这里。

核心 daemon 入口是 `apps/swabble/Sources/swabble/Commands/ServeCommand.swift`。它加载或创建 `SwabbleConfig`，处理 `--no-wake`，创建 `SpeechPipeline`，消费异步语音 segment stream，然后做 wake 判断、strip wake、构造 `HookJob`、调用 `HookExecutor`，并按配置写 transcript。

## 主流程位置

实时语音主流程集中在 `ServeCommand.run()` 和 `SpeechPipeline.start(localeIdentifier:etiquette:)` 两处。

`ServeCommand.run()` 代表 CLI 层的业务编排：先用 `ConfigLoader.load(at:)` 读取配置；如果配置不存在，就用默认 `SwabbleConfig()` 并保存。之后创建 `Logger` 和 `SpeechPipeline`，调用 `pipeline.start(...)` 得到 `AsyncStream<SpeechSegment>`。每个 `SpeechSegment` 进入循环后，如果 wake 开启，就通过 `WakeWordGate.matchesTextOnly(text:triggers:)` 判断是否包含触发词；通过后再用 `WakeWordGate.stripWake(text:triggers:)` 去掉 wake word，把剩余文本交给 hook。

`SpeechPipeline` 位于 `apps/swabble/Sources/SwabbleCore/Speech/SpeechPipeline.swift`，代表系统 Speech framework 对接层。它请求 speech authorization，创建 `SpeechTranscriber` 和 `SpeechAnalyzer`，选择 analyzer 兼容音频格式，然后用 `AVAudioEngine` 在 input node 上安装 tap。麦克风 buffer 进入 `handleBuffer`，由 `BufferConverter` 转换成 analyzer 需要的格式，再 yield 到 `AnalyzerInput` stream。另一侧读取 `transcriber.results`，把系统结果变成项目自己的 `SpeechSegment(text:isFinal:)`。

hook 执行在 `apps/swabble/Sources/SwabbleCore/Hooks/HookExecutor.swift`。`HookExecutor.run(job:)` 先检查 cooldown，再要求 `config.hook.command` 非空，然后拼出 payload：`prefix + job.text`。它会通过 `Process` 启动外部命令，把 payload 作为最后一个参数传入，同时设置 `SWABBLE_TEXT`、`SWABBLE_PREFIX` 以及配置里的额外 env。超时逻辑用 task group 和 `Task.sleep` 实现，超时后 terminate 进程。

wake word 规则在 `apps/swabble/Sources/SwabbleKit/WakeWordGate.swift`。CLI 当前实时路径使用的是 `matchesTextOnly` 和 `stripWake` 这种文本包含式判断；同文件还提供基于 `WakeWordSegment` 的 `match(...)`，会利用 segment 的 start/duration 和 `minPostTriggerGap` 判断触发词之后是否有足够停顿。根据当前片段推断，这部分是为了更精确的语音分段 wake gate 或库使用者准备的，因为 `ServeCommand` 目前只走 text-only 分支。

离线转写主流程入口应在 `apps/swabble/Sources/swabble/Commands/TranscribeCommand.swift`。本次只做 overview，没有展开该文件；依据 README 和目录命名，它负责 `transcribe <file>` 命令，把音频文件输出为 TXT 或 SRT，并可能使用 `Support/AttributedString+Sentences.swift` 做句段拆分。

## 推荐阅读顺序

1. 先读 `apps/swabble/Package.swift`，确认 SwiftPM target、产品名、平台要求和依赖边界。
2. 再读 `apps/swabble/README.md`，快速理解用户视角：`serve`、`setup`、`test-hook`、`transcribe`、`doctor` 等命令分别解决什么问题。
3. 读 `apps/swabble/Sources/swabble/CLI/CLIRegistry.swift` 和 `apps/swabble/Sources/swabble/main.swift`，建立 CLI 命令树和分发模型。
4. 读 `apps/swabble/Sources/swabble/Commands/ServeCommand.swift`，抓住实时 daemon 的业务编排。
5. 顺着 `ServeCommand` 进入 `apps/swabble/Sources/SwabbleCore/Config/Config.swift`、`apps/swabble/Sources/SwabbleCore/Speech/SpeechPipeline.swift`、`apps/swabble/Sources/SwabbleCore/Hooks/HookExecutor.swift`，分别看配置、语音流、hook 三个核心支点。
6. 最后读 `apps/swabble/Sources/SwabbleKit/WakeWordGate.swift` 和 `apps/swabble/Tests/SwabbleKitTests/WakeWordGateTests.swift`，理解 wake word gate 的库级行为和测试约束。

## 常见误区

不要把 `apps/swabble` 当成主 OpenClaw TypeScript CLI。这里是 SwiftPM 子项目，命令是 `swift run swabble ...`，源码语言、构建系统、测试方式都不同。

不要把 `Swabble` 和 `SwabbleKit` 混为一谈。`Swabble` 是包含 Speech pipeline、config、hook 等较完整能力的核心库；`SwabbleKit` 更偏轻量工具包，目前主要提供 wake word gate，可被 iOS/macOS app 复用。

不要以为所有 wake word 判断都依赖精确 speech segment。当前 `serve` 路径使用 `matchesTextOnly`，也就是文本包含式判断；基于 `WakeWordSegment` 和 gap 的 `match(...)` 是更细粒度能力，但不是当前 CLI 实时主路径的直接实现。

不要忽略平台版本。`main.swift` 和 `SpeechPipeline.swift` 都有 macOS/iOS 26 相关可用性标记；README 也强调 CLI 目标是 macOS 26 的新 Speech API。低版本系统上不是简单缺少功能，而是入口会直接报版本不满足。

不要把 `service install|uninstall|status` 理解成完整 launchd 管理已经落地。README 明确说 launchd helper 仍是 stub/占位性质，`start`、`stop`、`restart` 也仍是 placeholders；真正可重点学习的主流程是 foreground `serve`、配置读写、wake gate 和 hook 执行。
