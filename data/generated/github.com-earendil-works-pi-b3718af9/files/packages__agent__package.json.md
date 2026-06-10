# 文件：packages/agent/package.json

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
{
	"name": "@earendil-works/pi-agent-core",
	"version": "0.79.1",
	"description": "General-purpose agent with transport abstraction, state management, and attachment support",
	"type": "module",
	"main": "./dist/index.js",
	"types": "./dist/index.d.ts",
	"exports": {
		".": {
			"types": "./dist/index.d.ts",
			"import": "./dist/index.js"
		},
		"./node": {
			"types": "./dist/node.d.ts",
			"import": "./dist/node.js"
		},
		"./package.json": "./package.json"
	},
	"files": [
		"dist",
		"README.md"
	],
	"scripts": {
		"clean": "shx rm -rf dist",
		"build": "tsgo -p tsconfig.build.json",
		"test": "vitest --run",
		"test:harness": "vitest --run --config vitest.harness.config.ts",
		"coverage:harness": "vitest --run --config vitest.harness.config.ts --coverage",
		"prepublishOnly": "npm run clean && npm run build"
	},
	"dependencies": {
		"@earendil-works/pi-ai": "^0.79.1",
		"ignore": "7.0.5",
		"typebox": "1.1.38",
		"yaml": "2.9.0"
	},
	"keywords": [
		"ai",
		"agent",
		"llm",
		"transport",
		"state-management"
	],
	"author": "Mario Zechner",
	"license": "MIT",
	"repository": {
		"type": "git",
		"url": "git+[URL已移除]",
		"directory": "packages/agent"
	},
	"engines": {
		"node": ">=22.19.0"
	},
	"devDependencies": {
		"@types/node": "24.12.4",
		"@vitest/coverage-v8": "3.2.4",
		"typescript": "5.9.3",
		"vitest": "3.2.4"
	}
}

```
