# 文件：extensions/openrouter/speech-provider.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import {
  asObject,
  createOpenAiCompatibleSpeechProvider,
  type SpeechProviderPlugin,
} from "openclaw/plugin-sdk/speech";
import { OPENROUTER_BASE_URL } from "./provider-catalog.js";

const DEFAULT_OPENROUTER_TTS_MODEL = "hexgrad/kokoro-82m";
const DEFAULT_OPENROUTER_TTS_VOICE = "af_alloy";
const OPENROUTER_TTS_MODELS = [
  DEFAULT_OPENROUTER_TTS_MODEL,
  "google/gemini-3.1-flash-tts-preview",
  "mistralai/voxtral-mini-tts-2603",
  "elevenlabs/eleven-turbo-v2",
] as const;
const OPENROUTER_TTS_RESPONSE_FORMATS = ["mp3", "pcm"] as const;

type OpenRouterTtsExtraConfig = {
  provider?: Record<string, unknown>;
};

export function buildOpenRouterSpeechProvider(): SpeechProviderPlugin {
  return createOpenAiCompatibleSpeechProvider<OpenRouterTtsExtraConfig>({
    id: "openrouter",
    label: "OpenRouter",
    autoSelectOrder: 35,
    models: OPENROUTER_TTS_MODELS,
    voices: [DEFAULT_OPENROUTER_TTS_VOICE],
    defaultModel: DEFAULT_OPENROUTER_TTS_MODEL,
    defaultVoice: DEFAULT_OPENROUTER_TTS_VOICE,
    defaultBaseUrl: OPENROUTER_BASE_URL,
    envKey: "OPENROUTER_API_KEY",
    responseFormats: OPENROUTER_TTS_RESPONSE_FORMATS,
    defaultResponseFormat: "mp3",
    voiceCompatibleResponseFormats: ["mp3"],
    baseUrlPolicy: { kind: "canonical", aliases: ["[URL已移除]"] },
    extraHeaders: {
      "HTTP-Referer": "[URL已移除]",
      "X-OpenRouter-Title": "OpenClaw",
    },
    apiErrorLabel: "OpenRouter TTS API error",
    missingApiKeyError: "OpenRouter API key missing",
    readExtraConfig: (raw) => ({ provider: asObject(raw?.provider) }),
    extraJsonBodyFields: [{ configKey: "provider" }],
  });
}

```
