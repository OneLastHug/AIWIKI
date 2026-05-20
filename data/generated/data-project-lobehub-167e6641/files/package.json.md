# `package.json` 文件说明

## 文件职责

路径：`/data/project/lobehub/package.json`

这是整个 monorepo 的总控清单文件。

它同时承担几类职责：

- 定义仓库自身的包信息
- 定义 workspace 范围
- 定义开发、构建、测试、数据库、桌面端相关脚本
- 声明核心依赖与版本覆盖
- 告诉 `pnpm`、`bun`、CI、构建工具“这个仓库应该怎样被装起来和跑起来”

如果你想把仓库跑起来，或者想知道“哪个命令该怎么执行”，这个文件一定要看。

## 它为什么存在

如果没有这个文件，工具链几乎不知道这个仓库是什么：

- `pnpm` 不知道哪些目录属于 workspace
- `bun run` 不知道有哪些脚本可执行
- `next`、`vite`、`electron` 相关命令不知道该从哪里触发
- CI 不知道测试和构建入口

所以它虽然不是业务源码，但它决定了整个工程的“操作面板”。

## 主要导入 / 依赖代表什么

这个文件不是 TypeScript 文件，所以它没有 `import`。

对 `package.json` 来说，最接近“依赖说明”的是这些字段：

- `dependencies`
  运行时依赖，例如 React、Next.js、tRPC、Zustand、Drizzle、各类 workspace 包
- `devDependencies`
  开发、构建、测试依赖
- `workspaces`
  告诉包管理器哪些目录属于本仓库内部包
- `overrides`
  强制锁定某些依赖版本，减少不同子包之间的版本漂移

一个很值得注意的片段是：

```json
"workspaces": [
  "packages/*",
  "packages/business/*",
  "e2e",
  "apps/desktop/src/main"
]
```

这里前面三项比较常见，最后一项容易让新手疑惑。

结合 `apps/desktop/src/main/package.json` 可以确认：

- `apps/desktop/src/main` 被单独当成一个 workspace 包
- 这个小包名叫 `@lobehub/desktop-ipc-typings`
- 它主要暴露 `exports.d.ts`，用于桌面 IPC 类型共享

这不是推测，而是当前代码里能直接看到的事实。

## 主要导出 / 函数 / 类 / 组件逐个解释

这个文件没有导出函数、类或组件。

对 `package.json` 来说，等价的“阅读对象”是顶层字段。最值得读的几个如下。

### `name` / `version` / `private`

- `name: "@lobehub/lobehub"`
  仓库主包名
- `version: "2.2.0"`
  当前主仓库版本号
- 没有顶层 `private: true`
  说明它保留了包信息与发布相关元数据，但这不等于它会作为普通 npm 包使用

### `sideEffects`

这里声明了：

```json
"sideEffects": [
  "./src/initialize.ts"
]
```

这表示打包工具不要把这个初始化文件当成可随意 tree-shake 掉的纯文件，因为它会：

- 注册 dayjs 插件
- 启用 immer patch / mapset
- 处理 chunk load error
- 在开发环境启用 `react-scan`

### `scripts`

这是新手最应该优先看的部分。

可以按功能分组理解：

#### 开发启动

- `dev`
  主开发入口，走 `scripts/devStartupSequence.mts`
- `dev:spa`
  只启前端 SPA，走 Vite，默认端口 `9876`
- `dev:next`
  只启 Next.js，默认端口 `3010`
- `dev:desktop`
  进入 `apps/desktop` 启桌面端开发

#### 构建

- `build`
  总构建入口，顺序是 `build:spa -> build:spa:copy -> build:next`
- `build:spa`
  构建 Vite SPA
- `build:spa:copy`
  复制构建产物并生成 SPA 模板
- `build:next`
  构建 Next.js

这能直接反映项目架构：它不是只构建一个 Next.js 站点，而是先构建 SPA，再把 SPA 成果接到 Next.js 外壳里。

#### 数据库

- `db:generate`
- `db:migrate`
- `db:studio`
- `db:visualize`

这些和 Drizzle 生态直接相关。

#### 桌面端

- `desktop:build:*`
- `desktop:package:*`
- `desktop:main:build`

这些脚本证明桌面端不是顺手附带功能，而是明确的一条构建产线。

#### 质量保障

- `lint`
- `type-check`
- `test`
- `test:e2e`

### `dependencies`

这一段很长，但你不应该逐行死记。

更好的读法是按簇看：

- Web 前端框架：`next`、`react`、`react-dom`
- 前端路由与状态：`react-router-dom`、`zustand`
- 数据请求：`swr`、`@tanstack/react-query`
- 类型安全接口：`@trpc/*`
- 数据库：`drizzle-orm`
- UI：`antd`、`antd-style`、`@lobehub/ui`
- 桌面桥接：`@lobechat/desktop-bridge`、`@lobechat/electron-*`
- AI 运行时：`@lobechat/model-runtime`、`@lobechat/agent-runtime`
- 工具生态：`@lobechat/builtin-tools` 与一长串 `builtin-tool-*`

### `overrides`

这部分用于强行统一关键依赖版本，例如：

- React 类型
- antd
- Drizzle
- pdfjs-dist

对于大型 workspace 来说，这很常见，因为不同子包一旦拉到不兼容版本，会很痛苦。

## 输入 / 输出 / 副作用

### 输入

这个文件的“输入”不是函数参数，而是工具链读取它的过程：

- `pnpm install`
- `bun run xxx`
- `next build`
- `vite build`
- `electron-builder`
- CI 流水线

### 输出

通过不同脚本，它会驱动出不同产物：

- `public/_spa`、`dist/desktop`、`dist/mobile`
- Next.js 构建产物
- 桌面端安装包或目录包
- 数据库迁移产物

### 副作用

它本身没有运行时代码副作用，但它定义的脚本可能有非常实际的工程副作用，例如：

- 删除 `node_modules`
- 触发数据库迁移
- 构建桌面安装包
- 运行工作流脚本

所以阅读脚本名时要有“这是工程动作，不只是说明文字”的意识。

## 它被谁使用或可能被谁使用

- 开发者：查怎么启动、怎么构建、怎么跑数据库
- CI：查 lint/test/build 入口
- 包管理器：解析 workspace 与依赖树
- 子工程：共享版本约束与 workspace 关系
- 构建系统：Next.js、Vite、Electron 打包流程

## 小白阅读建议

第一次读这个文件时，不要从上到下逐行扫。

建议按这个顺序看：

1. `workspaces`
2. `scripts`
3. `dependencies` 里你认识的框架名
4. `overrides`

如果你只想快速上手开发，先记住三条命令就够：

- `bun run dev`
- `bun run dev:spa`
- `bun run dev:desktop`

等真正开始改数据库、桌面端或发布流程时，再回来读剩下的脚本。
