# 00. 项目整体是什么

## 一句话先讲明白

LobeHub 不是“一个聊天页”这么简单。

按 README 的产品表述，它更像一个面向 AI Agent 的工作空间：你可以创建 Agent、组织 Agent 群组、安排任务、管理知识和页面、在桌面端使用它，还能把部分能力通过分享页、社区页、技能体系、远程执行等方式扩出去。

如果你习惯把它叫做“AI Chat 应用”，这个说法不算错，但已经太小了。

## 站在普通用户角度，它像什么

可以把 LobeHub 想成一套“AI 团队工作台”：

- `agent`
  单个 AI 角色。像一个有自己设定、模型、工具、开场白的助手。
- `group`
  多个 Agent 组成的小组。不是只和一个助手聊天，而是和一组 AI 协作。
- `task`
  可以被 Agent 执行、跟踪、暂停、继续的任务。
- `page`
  类似文档/页面编辑空间，用来承接结构化内容。
- `resource` / `knowledge`
  文件、知识库、资源管理。
- `memory`
  让系统长期记住用户偏好、经历、上下文的记忆层。
- `community`
  浏览 Agent、模型、Provider、技能、MCP 等公共资源。
- `desktop`
  Electron 桌面端，把网页能力接到本地系统能力上。

所以它不是只有“输入一句话，返回一段回答”。

## 站在开发者角度，它像什么

从代码结构上看，LobeHub 是“多层拼起来的一套平台”：

1. `src/app`
   Next.js 外壳和后端入口。负责 API、认证页面、SPA HTML 模板服务。
2. `src/spa`
   真正的浏览器 SPA 入口，使用 React Router 注册页面树。
3. `src/routes`
   页面段落和布局壳，决定某个 URL 最终显示哪块页面。
4. `src/features`
   真正的业务 UI 和交互实现。很多页面的大部分重量都在这里。
5. `src/store`
   Zustand 状态管理层，统一放前端数据、动作和选择器。
6. `src/server`
   tRPC router、后端 service、运行时模块、Agent 执行链路。
7. `packages`
   共享工作区包，给前端、后端、桌面端一起复用。
8. `apps/desktop`
   Electron 桌面端宿主，补上本地文件、系统命令、截图、窗口管理等能力。

## 为什么这个仓库看起来“很杂”

因为它本来就不是单一形态应用，而是几种运行形态共存：

- Web 端：Next.js 提供壳和 API，SPA 提供主要交互。
- Mobile 变体：同一套仓库里有 mobile 路由树和入口。
- Popup 变体：桌面端弹窗/快速聊天窗口。
- Desktop 端：Electron 复用主工程页面，再额外接本地能力。
- Server 端：为前端提供 tRPC、异步任务、Agent 运行和 webhook 处理。

这也是为什么你会同时看到：

- `next.config.ts`
- `vite.config.ts`
- `src/app`
- `src/spa`
- `apps/desktop`

它们不是重复，而是在解决不同层的问题。

## 这套项目最重要的几个“阅读事实”

### 1. `src/routes` 不是全部页面实现

很多新手看到 `routes` 以为“页面代码都在这里”。

在这个仓库里，更准确的理解是：

- `src/routes` 更像页面入口和布局段
- `src/features` 更像真正的业务实现

而且根据仓库里的 `AGENTS.md` 与 `spa-routes` 约定，项目正在往“routes 薄、features 厚”的方向整理。当前快照里，这个目标已经在一些模块上体现得比较明显，例如 `/page` 路由；但也仍有一些旧模块还在 `src/routes` 里放了较多实现，例如 `agent` 相关页面。

## 2. `src/server` 不是“只做 API 转发”

这里不只是把数据库包一层接口而已。

后端里还有几类重量级逻辑：

- 全局配置拼装
- Feature Flag 读取
- Agent Runtime 协调
- 工具启用规则
- 异步图像/视频/文档任务
- Hono webhook / agent 执行入口

所以理解它时，不要只用“增删改查接口层”的眼光看。

## 3. `packages` 不是杂物堆

`packages` 很多，看上去容易让人紧张，但它的本质是工作区共享层：

- 有些包是“基础常量/类型/配置”
- 有些包是“AI 运行时能力”
- 有些包是“数据库和模型层”
- 有些包是“Electron IPC 桥”
- 有些包是“内置工具生态”

只要先抓住“分组”，就不会迷路。

## 4. 桌面端不是完全独立重写

`apps/desktop` 不是另起炉灶写了一套完全不同的 UI。

更准确地说：

- 主进程、preload、IPC、系统能力在 `apps/desktop`
- 具体页面 UI 仍大量复用 `src/*`

所以桌面端阅读路径通常是“先懂主工程页面，再看 Electron 怎么把系统能力接进来”。

## 推荐你马上接着看什么

如果你刚读完这一页，最顺的下一步是：

1. [01-tech-stack.md](./01-tech-stack.md)
2. [02-architecture.md](./02-architecture.md)
3. [03-runtime-flow.md](./03-runtime-flow.md)

先建立词汇表、分层图、运行流，再去翻目录，会轻松很多。
