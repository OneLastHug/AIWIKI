# 文件：packages/ai/package.json

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
{
	"name": "@earendil-works/pi-ai",
	"version": "0.79.1",
	"description": "Unified LLM API with automatic model discovery and provider configuration",
	"type": "module",
	"main": "./dist/index.js",
	"types": "./dist/index.d.ts",
	"exports": {
		".": {
			"types": "./dist/index.d.ts",
			"import": "./dist/index.js"
		},
		"./anthropic": {
			"types": "./dist/providers/anthropic.d.ts",
			"import": "./dist/providers/anthropic.js"
		},
		"./azure-openai-responses": {
			"types": "./dist/providers/azure-openai-responses.d.ts",
			"import": "./dist/providers/azure-openai-responses.js"
		},
		"./google": {
			"types": "./dist/providers/google.d.ts",
			"import": "./dist/providers/google.js"
		},
		"./google-vertex": {
			"types": "./dist/providers/google-vertex.d.ts",
			"import": "./dist/providers/google-vertex.js"
		},
		"./mistral": {
			"types": "./dist/providers/mistral.d.ts",
			"import": "./dist/providers/mistral.js"
		},
		"./openai-codex-responses": {
			"types": "./dist/providers/openai-codex-responses.d.ts",
			"import": "./dist/providers/openai-codex-responses.js"
		},
		"./openai-completions": {
			"types": "./dist/providers/openai-completions.d.ts",
			"import": "./dist/providers/openai-completions.js"
		},
		"./openai-responses": {
			"types": "./dist/providers/openai-responses.d.ts",
			"import": "./dist/providers/openai-responses.js"
		},
		"./oauth": {
			"types": "./dist/oauth.d.ts",
			"import": "./dist/oauth.js"
		},
		"./bedrock-provider": {
			"types": "./dist/bedrock-provider.d.ts",
			"import": "./dist/bedrock-provider.js"
		}
	},
	"bin": {
		"pi-ai": "./dist/cli.js"
	},
	"files": [
		"dist",
		"README.md"
	],
	"scripts": {
		"clean": "shx rm -rf dist",
		"generate-models": "node scripts/generate-models.ts",
		"generate-image-models": "node scripts/generate-image-models.ts",
		"build": "npm run generate-models && npm run generate-image-models && tsgo -p tsconfig.build.json",
		"test": "vitest --run",
		"prepublishOnly": "npm run clean && npm run build"
	},
	"dependencies": {
		"@anthropic-ai/sdk": "0.91.1",
		"@aws-sdk/client-bedrock-runtime": "3.1048.0",
		"@smithy/node-http-handler": "4.7.3",
		"@google/genai": "1.52.0",
		"@mistralai/mistralai": "2.2.1",
		"http-proxy-agent": "7.0.2",
		"https-proxy-agent": "7.0.6",
		"openai": "6.26.0",
		"partial-json": "0.1.7",
		"typebox": "1.1.38"
	},
	"keywords": [
		"ai",
		"llm",
		"openai",
		"anthropic",
		"gemini",
		"bedrock",
		"unified",
		"api"
	],
	"author": "Mario Zechner",
	"license": "MIT",
	"repository": {
		"type": "git",
		"url": "git+[URL已移除]",
		"directory": "packages/ai"
	},
	"engines": {
		"node": ">=22.19.0"
	},
	"devDependencies": {
		"@types/node": "24.12.4",
		"canvas": "3.2.3",
		"vitest": "3.2.4"
	}
}

```
