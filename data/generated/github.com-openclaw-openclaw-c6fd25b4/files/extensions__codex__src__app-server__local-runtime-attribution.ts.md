# 文件：extensions/codex/src/app-server/local-runtime-attribution.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { EmbeddedRunAttemptParams } from "openclaw/plugin-sdk/agent-harness-runtime";

const OPENAI_PROVIDER_ID = "openai";
const OPENAI_RESPONSES_API = "openai-responses";
const OPENAI_CODEX_PROVIDER_ID = "openai-codex";
const OPENAI_CODEX_RESPONSES_API = "openai-codex-responses";

export type CodexLocalRuntimeAttribution = {
  provider: string;
  api?: string;
};

function normalizeRuntimeId(value: string | undefined): string {
  return value?.trim().toLowerCase() ?? "";
}

export function resolveCodexLocalRuntimeAttribution(
  params: EmbeddedRunAttemptParams,
): CodexLocalRuntimeAttribution {
  const authProfileProvider = normalizeRuntimeId(
    params.runtimePlan?.auth?.authProfileProviderForAuth,
  );
  if (
    normalizeRuntimeId(params.runtimePlan?.observability.harnessId) === "codex" &&
    authProfileProvider !== OPENAI_PROVIDER_ID &&
    normalizeRuntimeId(params.model.provider) === OPENAI_PROVIDER_ID &&
    normalizeRuntimeId(params.model.api) === OPENAI_RESPONSES_API
  ) {
    return {
      provider: OPENAI_CODEX_PROVIDER_ID,
      api: OPENAI_CODEX_RESPONSES_API,
    };
  }

  return {
    provider: params.provider,
    api: params.model.api,
  };
}

```
