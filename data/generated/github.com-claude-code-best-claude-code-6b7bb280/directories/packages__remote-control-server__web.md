# 目录：packages/remote-control-server/web

## 它负责什么

`packages/remote-control-server/web` 是远程控制服务器的前端工作区，职责是把后端提供的会话、ACP 连接、鉴权、消息流和令牌管理，组织成一个浏览器可用的控制台界面。根据当前片段推断，它不是独立业务库，而是整个 `remote-control-server` 的 Web UI 层，配合上层 `packages/remote-control-server/package.json` 里的 `dev:web`、`build:web`、`preview:web` 脚本运行。

这块代码的核心目标很明确：一个页面里同时承载仪表盘、会话详情、ACP 直连视图、身份面板和 token 管理，并通过 `/web`、`/v1`、`/v2`、`/acp` 这些代理路径与本地后端通信。Vite 配置里还能看到 `base: '/code/'`，说明它最终会部署在带前缀的子路径下，而不是站点根目录。

## 直接子目录地图

这里的直接目录结构不复杂，主要是两层：

- `src`：前端运行时主体，放页面入口、路由壳、API 客户端、ACP 适配、hooks、通用工具、类型和测试。
- `components`：页面级和领域级组件，拆成更清晰的 UI 目录。
- 其余直接文件是构建与启动相关的骨架：`index.html`、`vite.config.ts`、`tsconfig.json`。

`src` 下面再分成几个明显的功能区：

- `src/pages`：页面级视图，当前能看到 `Dashboard` 和 `SessionDetail`。
- `src/components`：更靠近业务的组件，如 `Navbar`、`SessionList`、`EventStream`、`TokenManagerDialog`、`ACPDirectView`。
- `src/api`：浏览器侧请求封装，负责与后端 API 和 SSE 交互。
- `src/acp`：ACP 相关客户端、relay 和类型。
- `src/hooks`：状态和数据拉取逻辑，像 token、auth、SSE、模型、命令、扫码器。
- `src/lib`：通用能力和协议适配，比如 theme、工具函数、RCS transport、chat adapter。
- `src/types`：前端侧类型定义。
- `src/__tests__`：这块前端的单元测试。

而 `components` 目录则更像第二层组件库：

- `components/chat`：聊天界面主干，包含会话侧栏、消息气泡、输入框、权限面板、计划视图、命令菜单。
- `components/ui`：基础 UI 组件层，通常是 Radix 封装和样式原子件。
- `components/ai-elements`：面向 AI 对话内容展示的组合件。
- `components/model-selector`：模型选择相关交互。
- 另外还有 `ACPMain.tsx`、`ChatInterface.tsx`、`ChatMessage.tsx`、`ThreadHistory.tsx`、`ACPConnect.tsx` 这类顶层复合组件。

## 关键入口

这个目录最关键的浏览器入口是 `index.html`、`src/main.tsx`、`src/App.tsx` 三个点。

`index.html` 是 Vite 的挂载页，负责提供 `#root` 容器。`src/main.tsx` 则是 React 根启动文件，只做两件事：创建 root，并把 `App` 渲染进去。真正的应用控制逻辑集中在 `src/App.tsx`。

`vite.config.ts` 也是事实上的入口之一，因为它定义了构建与开发时的行为：React + Tailwind 插件、`/code/` 基路径、别名 `@/src` 和 `@/components`、构建 chunk 拆分，以及把 `/web`、`/v1`、`/v2`、`/acp` 代理到 `localhost:3000`。这说明前端不是孤立运行，而是紧贴本地后端服务。

## 主流程位置

主流程基本都从 `src/App.tsx` 展开。这里先初始化主题，再挂载顶层布局 `Navbar`，然后根据浏览器地址和查询参数决定显示哪条主线：

- 普通首页进入 `Dashboard`
- 带会话 id 的路径进入 `SessionDetail`
- 带 `?acp=1` 时进入 `ACPDirectView`
- 带 `?sid=...` 时会把会话绑定到当前 UUID，并跳转到对应会话页
- 带 `?uuid=...` 时会做 UUID 导入清理

也就是说，`App.tsx` 同时承担了路由解析、会话切换、ACP 直连和 token 同步的总调度角色。它里面还会调用 `useTokens()` 管理当前 token，`setActiveApiToken()` 把激活 token 传给 API 层，避免视图和请求状态脱节。

更细一点看，主流程的能力分散在几个协作点：

- `src/api/client.ts`：负责普通 API 请求、UUID、session bind 等动作。
- `src/api/sse.ts`、`src/hooks/useSSE.ts`：负责流式事件接收。
- `src/acp/client.ts`、`src/acp/relay-client.ts`：负责 ACP 链接。
- `src/pages/Dashboard.tsx`、`src/pages/SessionDetail.tsx`：负责首页和详情页的内容装配。
- `components/chat/*`：负责会话内容、工具调用、权限请求、输入区等聊天主链路。

## 推荐阅读顺序

1. 先看 `src/main.tsx`，确认这个应用如何挂载。
2. 再看 `src/App.tsx`，把路由分支、token 同步和 ACP 入口理顺。
3. 接着看 `src/api/client.ts`、`src/api/sse.ts`，理解前端怎么连后端。
4. 然后看 `src/pages/Dashboard.tsx` 和 `src/pages/SessionDetail.tsx`，建立页面级视图模型。
5. 再进入 `components/chat` 和 `components/ACPMain.tsx`，看具体交互是怎么拼起来的。
6. 最后补 `src/hooks` 和 `src/lib`，把状态获取、协议适配、主题和工具函数补齐。

## 常见误区

- 容易把 `packages/remote-control-server/web` 当成完整后端，其实它只是前端壳，真正接口在上层 `packages/remote-control-server`。
- 容易忽略 `vite.config.ts` 里的 `/code/` 基路径，结果在本地调试时路径跳转不对。
- 容易把 `src/main.tsx` 误认为主逻辑入口，但它只是挂载器，真正分支控制在 `src/App.tsx`。
- 容易只看 `src/components` 而忽略根目录的 `components`，实际上两边共同构成 UI 体系。
- 容易忽略 `?sid`、`?uuid`、`?acp` 这些查询参数，它们直接改变应用主流程，是这个目录里最重要的隐式入口。
