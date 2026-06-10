# 文件：packages/desktop/src/common/utils/appConfig.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

// Configuration for app info - to be set by the caller in main process
let appConfig: { name: string; version: string; protocolVersion: string } | null = null;

/**
 * Function to set app info using Electron API in main process
 * This allows direct use of app.getName() and app.getVersion() in main process
 */
export function setAppConfig(config: { name: string; version: string; protocolVersion?: string }) {
  appConfig = {
    name: config.name,
    version: config.version,
    protocolVersion: config.protocolVersion || '1.0.0',
  };
}

/**
 * Gets the application client name from the app config if available
 */
export const getConfiguredAppClientName = (): string => {
  return appConfig?.name || 'AionUi';
};

/**
 * Gets the application client version from the app config if available
 */
export const getConfiguredAppClientVersion = (): string => {
  return appConfig?.version || 'unknown';
};

/**
 * Gets the Codex MCP protocol version from the app config if available
 */
export const getConfiguredCodexMcpProtocolVersion = (): string => {
  return appConfig?.protocolVersion || '1.0.0';
};

```
