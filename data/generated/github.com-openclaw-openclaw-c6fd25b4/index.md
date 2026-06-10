# OpenClaw 中文源码学习索引

本索引是给第一次阅读 `openclaw` 仓库的中文读者准备的导航页。内容只基于当前仓库里的 `README.md`、`package.json`、`pnpm-workspace.yaml`、`openclaw.mjs`、`src/entry.ts`、`src/cli/**`、`src/gateway/**`、`src/plugins/**`、`src/channels/**`、`packages/**`、`extensions/**`、`ui/**`、`apps/**` 和 `docs/**` 等真实文件整理；涉及外部站点或仓库地址时均不写真实网址。

## 推荐阅读顺序

1. [00-overview.md](00-overview.md)：先建立项目要解决什么问题、能力边界、核心模块和初学者切入点。
2. [01-tech-stack.md](01-tech-stack.md)：再看运行环境、包管理、构建测试脚本、主要依赖和读源码前的基础概念。
3. [02-architecture.md](02-architecture.md)：理解目录分层、核心与插件边界、Gateway、channel、agent、SDK 的依赖方向。
4. [03-runtime-flow.md](03-runtime-flow.md)：顺着 CLI 启动、配置读取、Gateway 启动、WebSocket/HTTP 请求、插件加载、agent 执行来读运行链路。
5. [04-reading-guide.md](04-reading-guide.md)：最后按“先读、后读、可跳过”的方式安排下钻路线。
6. [critical_paths.json](critical_paths.json)：作为机器可读的关键路径种子列表，适合导入后续阅读工具。

## 后续最值得看的目录/文件

- `README.md`：项目定位、安装方式、安全默认值、开发方式和主要能力的最高层说明。
- `package.json`：`bin.openclaw`、`exports`、`scripts`、`engines`、依赖清单和发布文件范围都在这里。
- `pnpm-workspace.yaml`：确认这是包含根包、`ui`、`packages/*`、`extensions/*` 的 workspace。
- `openclaw.mjs` 与 `src/entry.ts`：理解 CLI 二进制如何检查 Node 版本、处理编译缓存、解析参数并进入主 CLI。
- `src/cli/**`：所有命令注册、选项解析、Gateway CLI、daemon CLI、message/agent/config 等命令都从这里延伸。
- `src/gateway/server.ts` 与 `src/gateway/server.impl.ts`：Gateway 懒加载入口与完整启动实现。
- `src/gateway/server-startup-plugins.ts`、`src/gateway/server-plugin-bootstrap.ts`：插件启动、自动启用、registry 准备和 channel plugin 绑定的关键路径。
- `src/gateway/methods/registry.ts`、`src/gateway/server-ws-runtime.ts`、`src/gateway/server-request-context.ts`：Gateway 方法注册、WebSocket 连接处理和请求上下文。
- `src/agents/agent-command.ts`、`src/agents/command/**`、`src/acp/**`：agent 会话、模型选择、运行时、ACP 控制面和执行尝试。
- `src/channels/**`：消息入口、allowlist、DM/group policy、session 路由、channel plugin runtime。
- `src/plugins/**` 与 `src/plugin-sdk/**`：核心插件加载器、插件 manifest/registry，以及暴露给插件作者的 SDK 面。
- `packages/plugin-sdk/**`、`packages/plugin-package-contract/**`：独立包形式的 SDK 与插件包契约。
- `extensions/*/openclaw.plugin.json` 与各插件 `index.ts`：理解真实插件如何声明能力、提供 provider/channel/tool/http route。
- `ui/package.json` 与 `ui/src/**`：Control UI 使用 Vite、Lit、Vitest，与 Gateway 通过协议交互。
- `apps/macos/**`、`apps/ios/**`、`apps/android/**`：伴随应用与移动节点，初学核心后再看。
- `docs/docs.json` 与 `docs/concepts/**`、`docs/cli/**`、`docs/channels/**`：现有文档的信息架构和用户视角解释。

阅读时建议先用“入口文件 -> Gateway 启动 -> 插件加载 -> agent 执行 -> channel 消息”的顺序建立主线，再按自己关心的能力下钻到具体插件或 UI/app。
