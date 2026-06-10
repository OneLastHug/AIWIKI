# 文件：packages/@ant/model-provider/src/index.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
// @ant/model-provider
// Model provider abstraction layer for Claude Code
//
// This package owns the model calling logic and provides:
// - Core query functions (queryModelWithStreaming, etc.)
// - Provider implementations (Anthropic, OpenAI, Gemini, Grok)
// - Type definitions (Message, Tool, Usage, etc.)
// - Dependency injection hooks (analytics, cost tracking, etc.)
//
// Initialization:
//   registerClientFactories({ ... })  // inject auth clients
//   registerHooks({ ... })            // inject analytics/cost/logging

// Hooks (dependency injection)
export { registerHooks, getHooks } from './hooks/index.js'
export type { ModelProviderHooks } from './hooks/types.js'

// Client factories
export { registerClientFactories, getClientFactories } from './client/index.js'
export type { ClientFactories } from './client/types.js'

// Types
export * from './types/index.js'

// Provider model mappings
export { resolveOpenAIModel } from './providers/openai/modelMapping.js'
export { resolveGrokModel } from './providers/grok/modelMapping.js'
export { resolveGeminiModel } from './providers/gemini/modelMapping.js'

// Gemini provider utilities
export { anthropicMessagesToGemini } from './providers/gemini/convertMessages.js'
export {
  anthropicToolsToGemini,
  anthropicToolChoiceToGemini,
} from './providers/gemini/convertTools.js'
export { adaptGeminiStreamToAnthropic } from './providers/gemini/streamAdapter.js'
export {
  GEMINI_THOUGHT_SIGNATURE_FIELD,
  type GeminiContent,
  type GeminiGenerateContentRequest,
  type GeminiPart,
  type GeminiStreamChunk,
  type GeminiTool,
  type GeminiFunctionCallingConfig,
  type GeminiFunctionDeclaration,
  type GeminiFunctionCall,
  type GeminiFunctionResponse,
  type GeminiInlineData,
  type GeminiUsageMetadata,
  type GeminiCandidate,
} from './providers/gemini/types.js'

// Error utilities
export {
  formatAPIError,
  extractConnectionErrorDetails,
  sanitizeAPIError,
  getSSLErrorHint,
  type ConnectionErrorDetails,
} from './errorUtils.js'

// Shared OpenAI conversion utilities
export { anthropicMessagesToOpenAI } from './shared/openaiConvertMessages.js'
export type { ConvertMessagesOptions } from './shared/openaiConvertMessages.js'
export {
  anthropicToolsToOpenAI,
  anthropicToolChoiceToOpenAI,
} from './shared/openaiConvertTools.js'
export { adaptOpenAIStreamToAnthropic } from './shared/openaiStreamAdapter.js'

```
