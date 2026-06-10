# 目录：packages

## 它负责什么

`packages` 是这个仓库的工作区包集合，承担了“把 CLI 主程序拆成可复用模块”的角色。这里既有真正对外发布的库，也有只服务于主程序的内部包和平台适配层。根据当前片段推断，这个目录的边界不是“业务代码的一部分”，而是整个仓库的组件仓库：主 CLI 会从这里引入工具系统、MCP 适配、电脑控制、图像/音频原生能力、远程控制服务等能力。

从 `package.json` 的 workspace 配置看，`packages/*`、`packages/@ant/*`、`packages/@anthropic-ai/*` 都属于同一工作区，因此 `packages` 既是源码组织层，也是构建与类型检查的主要承载层。`packages/tsconfig.json` 也说明这里统一采用严格 TypeScript 配置，所有子包都在同一套编译约束下工作。

## 直接子目录地图

- `packages/@ant/`：内部 scoped 包的聚合目录，放的是平台能力和 UI 基础设施。
  - `claude-for-chrome-mcp`：Chrome 相关的 MCP 桥接能力。
  - `computer-use-input`、`computer-use-mcp`、`computer-use-swift`：电脑控制链路的输入、MCP 服务和 Swift/系统层实现。
  - `ink`：终端 UI 框架封装，供 CLI 的 Ink 组件树使用。
  - `model-provider`：模型提供方抽象层。
- `packages/acp-link/`：ACP 代理桥接包，有自己的 CLI 和构建产物，偏服务端/通信层。
- `packages/agent-tools/`：agent 相关工具集合，偏任务编排和辅助执行。
- `packages/audio-capture-napi/`、`packages/color-diff-napi/`、`packages/image-processor-napi/`、`packages/modifiers-napi/`、`packages/url-handler-napi/`：原生能力或系统接口封装。
- `packages/builtin-tools/`：内置工具库，主 CLI 的大部分工具能力来自这里。
- `packages/mcp-client/`：MCP 客户端基础库。
- `packages/remote-control-server/`：远程控制服务端，包含 `src` 和 `web` 两个面向不同层的目录。
- `packages/weixin/`：微信相关适配或集成包。
- `packages/tsconfig.json`：工作区统一 TypeScript 配置。

## 关键入口

- `packages/*/src/index.ts`：大多数子包的主入口都是这里，`package.json` 的 `main` 基本都指向这个文件。
- `packages/acp-link/src/cli/bin.ts`：`acp-link` 的命令行入口，说明它不只是库，还是可直接运行的服务工具。
- `packages/remote-control-server/src/index.ts`：远程控制服务的核心入口；同时 `packages/remote-control-server/web` 表示它还有独立的 Web 前端面。
- `packages/builtin-tools/src/index.ts`：内置工具总入口，工具注册和导出通常会从这里开始。
- `packages/@ant/ink/src/index.ts`：Ink UI 层入口，CLI 终端界面组件会依赖它。
- `packages/@ant/computer-use-mcp/src/index.ts`、`packages/@ant/computer-use-input/src/index.ts`：电脑控制链路的关键入口。
- `packages/@ant/model-provider/src/index.ts`：模型提供方能力入口。

## 主流程位置

这里的“主流程”不是单一路径，而是几条主线分别落在不同包里：

1. 工具执行主线：`packages/builtin-tools/src/`  
   这里是 CLI 的工具系统核心，文件读写、Shell、搜索、MCP、计划类工具通常都在这一层被组织和导出。

2. 电脑控制主线：`packages/@ant/computer-use-input/src/`、`packages/@ant/computer-use-mcp/src/`、`packages/@ant/computer-use-swift/src/`  
   这条链路把键鼠/屏幕/系统能力串起来，供“computer use”模式调用。

3. 终端交互主线：`packages/@ant/ink/src/`  
   这是主 CLI 的 UI 基础层，REPL、提示输入、面板与交互组件都依赖它。

4. 远程接入主线：`packages/acp-link/src/`、`packages/remote-control-server/src/`  
   前者负责协议桥接，后者负责服务端和 Web 控制面，适合看作远程控制/代理接入的核心路径。

5. 原生能力主线：`packages/*-napi/src/`  
   这些包通常是薄封装，重点在系统边界和性能敏感点，而不是复杂业务逻辑。

根据当前片段推断，真正的业务编排逻辑会更多出现在各包的 `src/index.ts`、`src/cli/`、`src/tools/`、`src/server/` 这类目录中，而不是 `packages` 根目录本身。

## 推荐阅读顺序

1. 先看 `packages/tsconfig.json`，确认这里统一遵循的编译约束。
2. 再看 `packages/builtin-tools/package.json` 和 `packages/builtin-tools/src/`，把工具系统的入口先建立起来。
3. 接着看 `packages/@ant/ink/package.json`、`packages/@ant/ink/src/`，理解终端 UI 怎么被组织。
4. 然后看 `packages/@ant/computer-use-mcp` 与 `packages/@ant/computer-use-input`，补上系统交互链路。
5. 再看 `packages/acp-link`、`packages/remote-control-server`，理解外部接入和远程控制。
6. 最后补 `packages/*-napi`、`packages/mcp-client`、`packages/weixin` 这些能力包。

## 常见误区

- 误以为 `packages` 是一个单独应用。实际上它是工作区集合，里面多数目录是库或能力包。
- 误以为所有子目录都对外发布。实际上像 `@ant/*`、`builtin-tools`、`agent-tools` 这类更多是仓库内部模块。
- 误以为入口一定在根目录。这里的大多数包入口都在 `src/index.ts`，只有少数包会额外提供 `src/cli/bin.ts`、`src/server.ts` 之类入口。
- 误以为 `packages/remote-control-server/web` 是附属资源。它是该包的重要组成部分，说明服务端和前端控制面是并存的。
- 误以为原生包只是“可有可无”的附件。对这个仓库来说，`*-napi` 包常常是功能恢复和性能稳定的关键层。
