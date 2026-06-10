# 文件：src/gateway/server/plugin-route-runtime-scopes.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { IncomingMessage } from "node:http";
import {
  getHeader,
  resolveTrustedHttpOperatorScopes,
  type AuthorizedGatewayHttpRequest,
} from "../http-auth-utils.js";
import { CLI_DEFAULT_OPERATOR_SCOPES, WRITE_SCOPE } from "../method-scopes.js";

export type PluginRouteRuntimeScopeSurface = "write-default" | "trusted-operator";

export function resolvePluginRouteRuntimeOperatorScopes(
  req: IncomingMessage,
  requestAuth: AuthorizedGatewayHttpRequest,
  surface: PluginRouteRuntimeScopeSurface = "write-default",
): string[] {
  if (surface === "trusted-operator") {
    if (!requestAuth.trustDeclaredOperatorScopes) {
      return [...CLI_DEFAULT_OPERATOR_SCOPES];
    }
    return resolveTrustedHttpOperatorScopes(req, requestAuth);
  }
  if (requestAuth.authMethod !== "trusted-proxy") {
    return [WRITE_SCOPE];
  }
  if (getHeader(req, "x-openclaw-scopes") === undefined) {
    return [WRITE_SCOPE];
  }
  return resolveTrustedHttpOperatorScopes(req, requestAuth);
}

```
