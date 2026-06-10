# 文件：src/config/runtime-schema.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { resolveAgentWorkspaceDir, resolveDefaultAgentId } from "../agents/agent-scope.js";
import { resolvePluginMetadataSnapshot } from "../plugins/plugin-metadata-snapshot.js";
import {
  collectChannelSchemaMetadata,
  collectPluginSchemaMetadata,
} from "./channel-config-metadata.js";
import { getRuntimeConfig, readConfigFileSnapshot } from "./config.js";
import type { OpenClawConfig } from "./config.js";
import { buildConfigSchema, type ConfigSchemaResponse } from "./schema.js";

function loadManifestRegistry(config: OpenClawConfig, env?: NodeJS.ProcessEnv) {
  const workspaceDir = resolveAgentWorkspaceDir(config, resolveDefaultAgentId(config));
  return resolvePluginMetadataSnapshot({
    config,
    env: env ?? process.env,
    workspaceDir,
    allowWorkspaceScopedCurrent: true,
  }).manifestRegistry;
}

export function loadGatewayRuntimeConfigSchema(): ConfigSchemaResponse {
  const config = getRuntimeConfig();
  const registry = loadManifestRegistry(config);
  return buildConfigSchema({
    plugins: collectPluginSchemaMetadata(registry),
    channels: collectChannelSchemaMetadata(registry),
  });
}

export async function readBestEffortRuntimeConfigSchema(): Promise<ConfigSchemaResponse> {
  const snapshot = await readConfigFileSnapshot();
  const config = snapshot.valid ? snapshot.config : { plugins: { enabled: true } };
  const registry = loadManifestRegistry(config);
  return buildConfigSchema({
    plugins: snapshot.valid ? collectPluginSchemaMetadata(registry) : [],
    channels: collectChannelSchemaMetadata(registry),
  });
}

```
