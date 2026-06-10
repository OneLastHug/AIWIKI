# 文件：cli/package.json

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
{
  "name": "agentgpt-cli",
  "version": "1.0.0",
  "description": "A CLI to create your AgentGPT environment",
  "private": true,
  "engines": {
    "node": ">=18.0.0 <19.0.0"
  },
  "type": "module",
  "main": "index.js",
  "scripts": {
    "start": "node src/index.js",
    "dev": "node src/index.js"
  },
  "author": "reworkd",
  "dependencies": {
    "@octokit/auth-basic": "^1.4.8",
    "@octokit/rest": "^20.0.2",
    "chalk": "^5.3.0",
    "clear": "^0.1.0",
    "clui": "^0.3.6",
    "configstore": "^6.0.0",
    "dotenv": "^16.3.1",
    "figlet": "^1.7.0",
    "inquirer": "^9.2.12",
    "lodash": "^4.17.21",
    "minimist": "^1.2.8",
    "node-fetch": "^3.3.2",
    "simple-git": "^3.20.0",
    "touch": "^3.1.0"
  }
}

```
