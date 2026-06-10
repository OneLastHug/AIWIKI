# 目录：extensions/voice-call

## 它负责什么

`extensions/voice-call` 是 OpenClaw 的官方语音通话插件包，对外包名是 `@openclaw/voice-call`。它把 OpenClaw agent 的能力接到电话通道上：既能通过 CLI、Gateway RPC 或工具调用发起外呼，也能接收运营商 webhook 处理来电、通话状态、语音输入、媒体流和挂断事件。

从 `openclaw.plugin.json` 看，这个插件的 id 是 `voice-call`，命令别名是 `voicecall`，启动策略包含 `onStartup: true`，并在 `voicecall` 命令出现时激活。它声明的工具契约是 `voice_call`，说明模型侧可通过工具触发拨号、继续通话、播报、挂断、查询状态等动作。README 中列出的 provider 包括 Twilio、Telnyx、Plivo 和 Mock，其中 Mock 用于本地开发或无网络场景。

这个目录还承担插件自己的配置、兼容迁移、webhook 安全、TTS、实时转写、实时语音、通话管理、外部隧道暴露等职责。它是插件边界内的实现，按照 `extensions/AGENTS.md` 的规则，生产代码应通过 `openclaw/plugin-sdk/*` 和本包自己的 `api.ts`、`runtime-api.ts` 这类本地 barrel 暴露能力，而不是直接依赖 OpenClaw core 内部路径。

## 直接子目录地图

这个目标不是深层大目录，直接子目录主要集中在 `src/` 下面：

`src/manager/` 是通话状态与生命周期管理区。根据文件名可见，它包含 `lifecycle.ts`、`state.ts`、`store.ts`、`events.ts`、`lookup.ts`、`outbound.ts`、`timers.ts`、`twiml.ts`、`context.ts` 等模块，负责把“一个电话会话”组织成可查、可续、可结束、可恢复的运行时状态。

`src/providers/` 是运营商适配层。这里有 `base.ts`、`twilio.ts`、`telnyx.ts`、`plivo.ts`、`mock.ts`，以及 `twilio.types.ts`。它把不同电话服务商的发起通话、签名校验、状态回调、XML/TwiML 或 Call Control 差异封装在插件内部。

`src/webhook/` 是 webhook 子流程区，包含 `realtime-handler.ts`、`stream-frame-adapter.ts`、`realtime-audio-pacer.ts`、`stale-call-reaper.ts`、`tailscale.ts` 等。它处理媒体流帧、实时语音连接、音频节奏控制、过期通话清理和 Tailscale 暴露相关逻辑。

根层还有 `api.ts`、`runtime-api.ts`、`config-api.ts`、`setup-api.ts`、`cli-metadata.ts`、`runtime-entry.ts`、`index.ts` 等入口型文件；`openclaw.plugin.json` 是插件发现和 UI 元数据；`package.json` 是 npm 包、依赖和 OpenClaw 插件声明；`npm-shrinkwrap.json` 锁定插件发布依赖。

## 关键入口

`extensions/voice-call/index.ts` 是插件主入口。依据 `package.json` 的 `openclaw.extensions` 字段，OpenClaw 发现此插件时会加载 `./index.ts`。具体导出的对象和注册细节未在当前片段中展开，因此这里根据当前片段推断：它应负责把 CLI、工具、runtime、setup 或配置描述挂到插件系统。

`extensions/voice-call/runtime-entry.ts` 是运行时装配入口。根据命名推断，它可能服务于插件 runtime 激活，把 `src/runtime.ts`、manager、providers、webhook 服务连接起来。

`extensions/voice-call/api.ts` 与 `extensions/voice-call/runtime-api.ts` 是插件对外或对 core 快路径暴露的窄接口。结合 `extensions/AGENTS.md` 的边界规则，这类文件用于避免 core 或测试直接 deep-import `src/**` 私有实现。

`extensions/voice-call/config-api.ts`、`extensions/voice-call/setup-api.ts` 是配置和安装/设置层入口。`openclaw.plugin.json` 中大量 `uiHints` 与 channel env vars 表明配置面很宽，包括 provider、from/to number、inbound policy、serve、tunnel、streaming、realtime、TTS 等。

`extensions/voice-call/src/cli.ts` 是 `openclaw voicecall ...` 命令实现位置。README 列出的子命令包括 `call`、`continue`、`speak`、`end`、`status`、`tail`、`expose`。

## 主流程位置

外呼主流程大致从 CLI、Gateway RPC 或 `voice_call` 工具进入。README 中列出的动作包括 `initiate_call`、`continue_call`、`speak_to_user`、`end_call`、`get_status`；对应的 Gateway RPC 是 `voicecall.initiate`、`voicecall.continue`、`voicecall.speak`、`voicecall.end`、`voicecall.status`。这些入口最终应落到 `src/runtime.ts`、`src/manager.ts` 和 `src/manager/outbound.ts`，再由 `src/providers/*` 选择 Twilio、Telnyx、Plivo 或 Mock 发起实际通话。

来电和回调主流程集中在 `src/webhook.ts` 与 `src/webhook/*`。README 明确提到 Twilio/Telnyx/Plivo 需要公网可达 webhook，并且插件做 webhook 签名校验、Twilio/Plivo replay protection、Twilio speech turn token、防止旧回调完成新语音轮次等。对应实现位置可优先看 `src/webhook-security.ts`、`src/http-headers.ts`、`src/webhook.ts`、`src/webhook/stale-call-reaper.ts`。

语音生成和播放流程分成两条：普通响应生成与实时语音。普通响应相关文件包括 `src/response-generator.ts`、`src/response-model.ts`、`src/telephony-tts.ts`、`src/tts-provider-voice.ts`，README 说明会强制 spoken JSON 合约并过滤 reasoning/meta 输出。实时链路则看 `src/realtime-voice.runtime.ts`、`src/realtime-transcription.runtime.ts`、`src/realtime-agent-context.ts`、`src/realtime-fast-context.ts`、`src/webhook/realtime-handler.ts`、`src/media-stream.ts`、`src/telephony-audio.ts`。

配置兼容与迁移相关流程在 `src/config.ts`、`src/config-compat.ts`、`src/voice-mapping.ts`、`src/deep-merge.ts`。README 提到旧配置如 `provider: "log"`、`twilio.from`、旧的 `streaming.*` OpenAI keys 需要通过 `openclaw doctor --fix` 改写；这说明 runtime 可能仍有短期兼容，但正式迁移入口属于 doctor/setup 配置层。

## 推荐阅读顺序

1. 先读 `extensions/voice-call/openclaw.plugin.json` 和 `extensions/voice-call/package.json`，明确插件 id、激活条件、工具契约、命令别名、依赖和发布形态。
2. 再读 `extensions/voice-call/README.md`，把 provider、配置、CLI、tool、Gateway RPC 和运行注意事项串起来。
3. 接着看入口层：`extensions/voice-call/index.ts`、`extensions/voice-call/runtime-entry.ts`、`extensions/voice-call/api.ts`、`extensions/voice-call/runtime-api.ts`、`extensions/voice-call/src/runtime.ts`。
4. 然后看通话核心：`extensions/voice-call/src/manager.ts` 和 `extensions/voice-call/src/manager/`，理解 call id、session scope、状态恢复、事件、计时器和外呼。
5. 最后按问题阅读分支：运营商问题看 `src/providers/`；webhook 和安全问题看 `src/webhook.ts`、`src/webhook/`、`src/webhook-security.ts`；实时语音问题看 `src/realtime-*.ts`、`src/media-stream.ts`；配置问题看 `src/config*.ts`。

## 常见误区

不要把 `extensions/voice-call` 当成 core 电话模块。它是插件，边界规则要求插件生产代码使用 Plugin SDK 和本包公开 barrel，不能随意 import `src/**` core 内部实现，也不能把 Twilio/Telnyx/Plivo 的 provider 策略上移到 core。

不要认为 `voice_call` 只是 CLI 包装。它同时暴露模型工具、Gateway RPC、webhook 服务和 provider runtime，CLI 只是其中一个入口。

不要把所有语音路径混成一条。普通电话响应、TTS 播报、运营商语音输入、Media Streams、realtime voice、realtime transcription 是相互关联但不同的路径，分别散落在 `response-*`、`telephony-*`、`media-stream.ts`、`realtime-*` 和 `webhook/*` 中。

不要忽略公网暴露和签名校验。README 明确指出真实 Twilio/Telnyx/Plivo 需要公网 webhook，且插件实现了签名校验与 replay protection；本地 Mock 成功不代表真实运营商回调链路已通。

不要直接改旧配置兼容逻辑来“让运行时多接收一点”。仓库根规则强调 runtime 读 canonical config，旧键迁移应走 doctor/fix 或配置兼容边界。对于 `voice-call`，优先从 `src/config-compat.ts`、`setup-api.ts`、`config-api.ts` 理解现有迁移策略。
