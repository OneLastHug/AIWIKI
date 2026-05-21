# 文件：packages/model-runtime/package.json

## 文件职责
这个文件位于 `packages/model-runtime`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
未在节选中发现明显 import/export 语句。
```

## 主要对外内容
```text
未在节选中发现明显导出的类型、函数或组件。
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
{
  "name": "@lobechat/model-runtime",
  "version": "1.0.0",
  "private": true,
  "exports": {
    ".": "./src/index.ts",
    "./vertexai": "./src/providers/vertexai/index.ts"
  },
  "scripts": {
    "test": "vitest",
    "test:coverage": "vitest --coverage --silent='passed-only'",
    "test:update": "vitest -u"
  },
  "dependencies": {
    "@anthropic-ai/sdk": "^0.73.0",
    "@aws-sdk/client-bedrock-runtime": "^3.941.0",
    "@azure-rest/ai-inference": "1.0.0-beta.5",
    "@azure/core-auth": "^1.10.1",
    "@fal-ai/client": "^1.7.2",
    "@google/genai": "^1.43.0",
    "@huggingface/inference": "^4.13.4",
    "@lobechat/business-model-runtime": "workspace:*",
    "@lobechat/const": "workspace:*",
    "@lobechat/utils": "workspace:*",
    "async-retry": "^1.3.3",
    "dayjs": "^1.11.19",
    "debug": "^4.4.3",
    "immer": "^10.2.0",
    "langfuse": "^3.38.6",
    "langfuse-core": "^3.38.6",
    "model-bank": "workspace:*",
    "nanoid": "^5.1.6",
    "ollama": "^0.6.2",
    "openai": "^4.104.0",
    "replicate": "^1.4.0",
    "tokenx": "^1.3.0",
    "type-fest": "^5.2.0",
    "url-join": "^5.0.0"
  },
  "devDependencies": {
    "@lobechat/types": "workspace:*"
  },
  "peerDependencies": {
    "zod": "^3.25.76"
  }
}

```
