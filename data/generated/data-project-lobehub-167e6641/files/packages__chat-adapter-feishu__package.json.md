# 文件：packages/chat-adapter-feishu/package.json

## 文件职责
这个文件位于 `packages/chat-adapter-feishu`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

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
  "name": "@lobechat/chat-adapter-feishu",
  "version": "0.1.0",
  "description": "Lark/Feishu adapter for chat SDK",
  "type": "module",
  "exports": {
    ".": "./src/index.ts"
  },
  "files": [
    "dist"
  ],
  "scripts": {
    "build": "tsup",
    "clean": "rm -rf dist",
    "dev": "tsup --watch",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "chat": "^4.23.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "tsup": "^8.3.5",
    "typescript": "^5.7.2"
  }
}

```
