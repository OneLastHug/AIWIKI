# 文件：src/services/mcpServerApproval.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { MCPServerApprovalDialog } from '../components/MCPServerApprovalDialog.js';
import { MCPServerMultiselectDialog } from '../components/MCPServerMultiselectDialog.js';
import type { Root } from '@anthropic/ink';
import { KeybindingSetup } from '../keybindings/KeybindingProviderSetup.js';
import { AppStateProvider } from '../state/AppState.js';
import { getMcpConfigsByScope } from './mcp/config.js';
import { getProjectMcpServerStatus } from './mcp/utils.js';

/**
 * Show MCP server approval dialogs for pending project servers.
 * Uses the provided Ink root to render (reusing the existing instance
 * from main.tsx instead of creating a separate one).
 */
export async function handleMcpjsonServerApprovals(root: Root): Promise<void> {
  const { servers: projectServers } = getMcpConfigsByScope('project');
  const pendingServers = Object.keys(projectServers).filter(
    serverName => getProjectMcpServerStatus(serverName) === 'pending',
  );

  if (pendingServers.length === 0) {
    return;
  }

  await new Promise<void>(resolve => {
    const done = (): void => void resolve();
    if (pendingServers.length === 1 && pendingServers[0] !== undefined) {
      const serverName = pendingServers[0];
      root.render(
        <AppStateProvider>
          <KeybindingSetup>
            <MCPServerApprovalDialog serverName={serverName} onDone={done} />
          </KeybindingSetup>
        </AppStateProvider>,
      );
    } else {
      root.render(
        <AppStateProvider>
          <KeybindingSetup>
            <MCPServerMultiselectDialog serverNames={pendingServers} onDone={done} />
          </KeybindingSetup>
        </AppStateProvider>,
      );
    }
  });
}

```
