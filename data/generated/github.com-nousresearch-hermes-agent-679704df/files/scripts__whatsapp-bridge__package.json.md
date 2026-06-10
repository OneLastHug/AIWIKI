# 文件：scripts/whatsapp-bridge/package.json

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
{
  "name": "hermes-whatsapp-bridge",
  "version": "1.0.0",
  "description": "WhatsApp bridge for Hermes Agent using Baileys",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "node bridge.js"
  },
  "dependencies": {
    "@whiskeysockets/baileys": "WhiskeySockets/Baileys#01047debd81beb20da7b7779b08edcb06aa03770",
    "express": "^4.21.0",
    "qrcode-terminal": "^0.12.0",
    "pino": "^9.0.0"
  },
  "overrides": {
    "protobufjs": "^7.5.5"
  }
}

```
