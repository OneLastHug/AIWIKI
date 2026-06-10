# 文件：packages/tui/package.json

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
{
	"name": "@earendil-works/pi-tui",
	"version": "0.79.1",
	"description": "Terminal User Interface library with differential rendering for efficient text-based applications",
	"type": "module",
	"main": "dist/index.js",
	"scripts": {
		"clean": "shx rm -rf dist",
		"build": "tsgo -p tsconfig.build.json",
		"test": "node --test test/*.test.ts",
		"prepublishOnly": "npm run clean && npm run build"
	},
	"files": [
		"dist/**/*",
		"native/win32/prebuilds/**/*.node",
		"native/darwin/prebuilds/**/*.node",
		"README.md"
	],
	"keywords": [
		"tui",
		"terminal",
		"ui",
		"text-editor",
		"differential-rendering",
		"typescript",
		"cli"
	],
	"author": "Mario Zechner",
	"license": "MIT",
	"repository": {
		"type": "git",
		"url": "git+[URL已移除]",
		"directory": "packages/tui"
	},
	"engines": {
		"node": ">=22.19.0"
	},
	"types": "./dist/index.d.ts",
	"dependencies": {
		"get-east-asian-width": "1.6.0",
		"marked": "15.0.12"
	},
	"devDependencies": {
		"@xterm/headless": "5.5.0",
		"chalk": "5.6.2"
	}
}

```
