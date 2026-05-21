# 目录：packages

## 它负责什么
`packages` 是 LobeHub 代码树中的一个功能区域。下面的说明基于真实目录结构和被选中的源码文件生成，后续 Codex 深度解释会继续补全更细的调用关系。

## 下面有哪些子目录
- `agent-gateway-client`：`packages/agent-gateway-client` 下的子功能区，建议展开继续读。
- `agent-manager-runtime`：`packages/agent-manager-runtime` 下的子功能区，建议展开继续读。
- `agent-mock`：`packages/agent-mock` 下的子功能区，建议展开继续读。
- `agent-runtime`：`packages/agent-runtime` 下的子功能区，建议展开继续读。
- `agent-signal`：`packages/agent-signal` 下的子功能区，建议展开继续读。
- `agent-templates`：`packages/agent-templates` 下的子功能区，建议展开继续读。
- `agent-tracing`：`packages/agent-tracing` 下的子功能区，建议展开继续读。
- `builtin-agents`：`packages/builtin-agents` 下的子功能区，建议展开继续读。
- `builtin-skills`：`packages/builtin-skills` 下的子功能区，建议展开继续读。
- `builtin-tool-activator`：`packages/builtin-tool-activator` 下的子功能区，建议展开继续读。
- `builtin-tool-agent-builder`：`packages/builtin-tool-agent-builder` 下的子功能区，建议展开继续读。
- `builtin-tool-agent-documents`：`packages/builtin-tool-agent-documents` 下的子功能区，建议展开继续读。
- `builtin-tool-agent-management`：`packages/builtin-tool-agent-management` 下的子功能区，建议展开继续读。
- `builtin-tool-brief`：`packages/builtin-tool-brief` 下的子功能区，建议展开继续读。
- `builtin-tool-calculator`：`packages/builtin-tool-calculator` 下的子功能区，建议展开继续读。
- `builtin-tool-claude-code`：`packages/builtin-tool-claude-code` 下的子功能区，建议展开继续读。
- `builtin-tool-cloud-sandbox`：`packages/builtin-tool-cloud-sandbox` 下的子功能区，建议展开继续读。
- `builtin-tool-creds`：`packages/builtin-tool-creds` 下的子功能区，建议展开继续读。
- `builtin-tool-group-agent-builder`：`packages/builtin-tool-group-agent-builder` 下的子功能区，建议展开继续读。
- `builtin-tool-group-management`：`packages/builtin-tool-group-management` 下的子功能区，建议展开继续读。
- `builtin-tool-knowledge-base`：`packages/builtin-tool-knowledge-base` 下的子功能区，建议展开继续读。
- `builtin-tool-lobe-agent`：`packages/builtin-tool-lobe-agent` 下的子功能区，建议展开继续读。
- `builtin-tool-local-system`：`packages/builtin-tool-local-system` 下的子功能区，建议展开继续读。
- `builtin-tool-memory`：`packages/builtin-tool-memory` 下的子功能区，建议展开继续读。
- `builtin-tool-message`：`packages/builtin-tool-message` 下的子功能区，建议展开继续读。
- `builtin-tool-notebook`：`packages/builtin-tool-notebook` 下的子功能区，建议展开继续读。
- `builtin-tool-page-agent`：`packages/builtin-tool-page-agent` 下的子功能区，建议展开继续读。
- `builtin-tool-remote-device`：`packages/builtin-tool-remote-device` 下的子功能区，建议展开继续读。
- `builtin-tool-self-iteration`：`packages/builtin-tool-self-iteration` 下的子功能区，建议展开继续读。
- `builtin-tool-skill-maintainer`：`packages/builtin-tool-skill-maintainer` 下的子功能区，建议展开继续读。
- `builtin-tool-skill-store`：`packages/builtin-tool-skill-store` 下的子功能区，建议展开继续读。
- `builtin-tool-skills`：`packages/builtin-tool-skills` 下的子功能区，建议展开继续读。
- `builtin-tool-task`：`packages/builtin-tool-task` 下的子功能区，建议展开继续读。
- `builtin-tool-topic-reference`：`packages/builtin-tool-topic-reference` 下的子功能区，建议展开继续读。
- `builtin-tool-user-interaction`：`packages/builtin-tool-user-interaction` 下的子功能区，建议展开继续读。
- `builtin-tool-web-browsing`：`packages/builtin-tool-web-browsing` 下的子功能区，建议展开继续读。
- `builtin-tool-web-onboarding`：`packages/builtin-tool-web-onboarding` 下的子功能区，建议展开继续读。
- `builtin-tools`：`packages/builtin-tools` 下的子功能区，建议展开继续读。
- `business`：`packages/business` 下的子功能区，建议展开继续读。
- `chat-adapter-feishu`：`packages/chat-adapter-feishu` 下的子功能区，建议展开继续读。

## 下面有哪些重要文件
- 没有发现直接文件，主要内容在更深层子目录。

## 文件树节选
```text
packages/model-bank/tsconfig.json
packages/model-runtime/src/providers/openrouter/index.ts
packages/device-gateway-client/tsconfig.json
packages/electron-server-ipc/package.json
packages/electron-server-ipc/README.md
packages/builtin-tool-skill-store/package.json
packages/model-runtime/src/core/RouterRuntime/index.ts
packages/model-runtime/package.json
packages/model-bank/package.json
packages/business/model-runtime/package.json
packages/builtin-tool-user-interaction/tsconfig.json
packages/agent-mock/tsconfig.json
packages/agent-tracing/tsconfig.json
packages/edge-config/package.json
packages/config/package.json
packages/builtin-tool-calculator/tsconfig.json
packages/builtin-tool-topic-reference/tsconfig.json
packages/eval-rubric/tsconfig.json
packages/web-crawler/tsconfig.json
packages/chat-adapter-feishu/tsconfig.json
packages/chat-adapter-line/tsconfig.json
packages/chat-adapter-qq/tsconfig.json
packages/chat-adapter-wechat/tsconfig.json
packages/business/config/package.json
packages/electron-client-ipc/package.json
packages/device-gateway-client/package.json
packages/agent-gateway-client/package.json
packages/builtin-tool-page-agent/package.json
packages/electron-client-ipc/README.md
packages/builtin-agents/src/agents/page-agent/README.md
packages/model-bank/src/modelProviders/openrouter.ts
packages/model-runtime/src/providers/openrouter/fixtures/frontendModels.json
packages/model-runtime/src/providers/openrouter/fixtures/models.json
packages/model-runtime/src/providers/openrouter/type.ts
packages/agent-templates/package.json
packages/agent-mock/README.md
packages/desktop-bridge/package.json
packages/markdown-patch/package.json
packages/builtin-tool-brief/package.json
packages/builtin-skills/package.json
packages/builtin-tool-topic-reference/package.json
packages/local-file-shell/package.json
packages/tool-runtime/package.json
packages/python-interpreter/package.json
packages/builtin-tool-remote-device/package.json
packages/builtin-tool-skill-maintainer/package.json
packages/agent-manager-runtime/package.json
packages/prompts/package.json
packages/conversation-flow/package.json
packages/editor-runtime/package.json
packages/builtin-tool-creds/package.json
packages/builtin-tool-group-management/package.json
packages/builtin-tool-notebook/package.json
packages/agent-tracing/package.json
packages/builtin-tool-activator/package.json
packages/agent-mock/package.json
packages/agent-runtime/package.json
packages/web-crawler/package.json
packages/agent-signal/package.json
packages/builtin-tool-task/package.json
packages/builtin-tool-agent-management/package.json
packages/chat-adapter-qq/package.json
packages/chat-adapter-feishu/package.json
packages/builtin-tool-user-interaction/package.json
packages/chat-adapter-wechat/package.json
```

## 小白阅读建议
先看本目录下的 `index`、`route`、`store`、`service`、`schema`、`config` 等名字明显的文件，再顺着导入关系读更深层文件。
