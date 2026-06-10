# 文件：extensions/qa-lab/src/providers/live-frontier/model-selection.runtime.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import {
  listProfilesForProvider,
  loadAuthProfileStoreForRuntime,
} from "openclaw/plugin-sdk/agent-runtime";
import { resolveEnvApiKey } from "openclaw/plugin-sdk/provider-auth";

const QA_CODEX_OAUTH_LIVE_MODEL = "openai/gpt-5.5";

export function resolveQaLiveFrontierPreferredModel() {
  if (resolveEnvApiKey("openai")?.apiKey) {
    return undefined;
  }
  try {
    const store = loadAuthProfileStoreForRuntime(undefined, {
      readOnly: true,
      allowKeychainPrompt: false,
      externalCliProviderIds: ["openai-codex"],
    });
    if (listProfilesForProvider(store, "openai").length > 0) {
      return undefined;
    }
    return listProfilesForProvider(store, "openai-codex").length > 0
      ? QA_CODEX_OAUTH_LIVE_MODEL
      : undefined;
  } catch {
    return undefined;
  }
}

```
