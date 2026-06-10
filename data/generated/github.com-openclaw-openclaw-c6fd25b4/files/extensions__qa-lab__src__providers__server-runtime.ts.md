# 文件：extensions/qa-lab/src/providers/server-runtime.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { getQaProvider, type QaMockProviderServer, type QaProviderModeInput } from "./index.js";

type QaProviderServerParams = {
  host: string;
  port: number;
};

async function startMockOpenAiProviderServer(params: QaProviderServerParams) {
  const { startQaMockOpenAiServer } = await import("./mock-openai/server.js");
  return await startQaMockOpenAiServer(params);
}

async function startAimockProviderServer(params: QaProviderServerParams) {
  const { startQaAimockServer } = await import("./aimock/server.js");
  return await startQaAimockServer(params);
}

export async function startQaProviderServer(
  input: QaProviderModeInput,
  params?: { host?: string; port?: number },
): Promise<QaMockProviderServer | null> {
  const provider = getQaProvider(input);
  const serverParams = {
    host: params?.host ?? "127.0.0.1",
    port: params?.port ?? 0,
  };
  switch (provider.mode) {
    case "mock-openai":
      return await startMockOpenAiProviderServer(serverParams);
    case "aimock":
      return await startAimockProviderServer(serverParams);
    case "live-frontier":
    default:
      return null;
  }
}

```
