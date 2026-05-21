# 文件：pnpm-workspace.yaml

## 它负责什么

`pnpm-workspace.yaml` 是这个仓库的 **pnpm monorepo 工作区总开关**。它不参与应用运行时逻辑，也没有 `import/export`，但会直接影响：

- `pnpm install` 时哪些目录被识别为 workspace package；
- `workspace:*` 依赖能否被解析到本仓库内的本地包；
- 某些依赖是否允许执行安装期构建脚本；
- 跨 workspace 的依赖版本是否被强制统一；
- 某些第三方依赖是否套用本仓库维护的补丁。

在这个仓库里，根 `package.json` 大量依赖形如 `@lobechat/agent-runtime: workspace:*`、`@lobechat/builtin-tool-xxx: workspace:*` 的本地包。`pnpm-workspace.yaml` 就是 pnpm 判断这些本地包“在哪里”的依据。

它的内容很短：

```yaml
packages:
  - packages/**
  - .
  - e2e
  - apps/desktop/src/main

onlyBuiltDependencies:
  - '@google/genai'
  - '@lobehub/editor'
  - '@vercel/speed-insights'

overrides:
  jose: ^6.1.3
  stylelint-config-clean-order: 7.0.0
  pdfjs-dist: 5.4.530
  react: 19.2.4
  react-dom: 19.2.4
  '@react-pdf/image': 3.0.4

patchedDependencies:
  '@upstash/qstash': patches/@upstash__qstash.patch
```

可以把它理解为：**告诉 pnpm 这个仓库由哪些包组成，并在安装阶段施加统一的依赖治理规则。**

## 关键组成

第一部分是 `packages`：

```yaml
packages:
  - packages/**
  - .
  - e2e
  - apps/desktop/src/main
```

这定义了 workspace 成员范围。

`packages/**` 表示 `packages` 下的多层子目录都可能是 workspace 包。这个仓库的 `packages` 目录下有大量内部包，例如：

- `packages/agent-runtime`
- `packages/agent-signal`
- `packages/builtin-tools`
- `packages/builtin-tool-web-browsing`
- `packages/database`
- `packages/model-runtime`
- `packages/business/model-bank`
- `packages/business/model-runtime`

这里使用 `packages/**`，比根 `package.json` 里的 `workspaces` 更宽。根 `package.json` 写的是：

```json
"workspaces": [
  "packages/*",
  "packages/business/*",
  "e2e",
  "apps/desktop/src/main"
]
```

而 `pnpm-workspace.yaml` 的 `packages/**` 会覆盖更深层级的包。对 pnpm 来说，真正决定 workspace 边界的是 `pnpm-workspace.yaml`。

`.` 表示仓库根目录本身也是一个 workspace package。根目录的 `package.json` 名称是 `@lobehub/lobehub`，它承载了主应用、根脚本、主依赖和大量 `workspace:*` 内部依赖。

`e2e` 表示端到端测试包也是 workspace 成员。它的 `package.json` 名称是 `@lobechat/e2e-tests`，包含 Cucumber、Playwright、PostgreSQL 测试相关依赖和测试脚本。

`apps/desktop/src/main` 表示桌面端主进程相关的类型包也单独作为 workspace 成员。它的 `package.json` 名称是 `@lobehub/desktop-ipc-typings`，导出 `exports.d.ts`。根据当前片段推断，这个包用于桌面端 IPC 类型共享，依据是它只声明了 `exports`、`main`、`types`，且入口全部指向 `exports.d.ts`。

第二部分是 `onlyBuiltDependencies`：

```yaml
onlyBuiltDependencies:
  - '@google/genai'
  - '@lobehub/editor'
  - '@vercel/speed-insights'
```

这是 pnpm 安装安全策略的一部分。现代 pnpm 对依赖的安装脚本更谨慎，`onlyBuiltDependencies` 用来声明：这些依赖允许在安装阶段执行构建脚本。

这里列出的包都不是普通业务代码入口，而是安装时可能需要构建或准备产物的依赖：

- `@google/genai`
- `@lobehub/editor`
- `@vercel/speed-insights`

常见场景是：如果某个包安装后需要运行 `postinstall`、构建 native/预编译资源或生成运行所需文件，pnpm 需要知道哪些包是被允许执行构建的。

第三部分是 `overrides`：

```yaml
overrides:
  jose: ^6.1.3
  stylelint-config-clean-order: 7.0.0
  pdfjs-dist: 5.4.530
  react: 19.2.4
  react-dom: 19.2.4
  '@react-pdf/image': 3.0.4
```

`overrides` 是依赖版本的强制覆盖规则。它会影响整个 workspace 的依赖解析，即使某个子包或第三方依赖间接声明了不同版本，也会被 pnpm 尽量压到这里指定的版本。

这个文件里重点固定了几类依赖：

- `react` 和 `react-dom`：统一到 `19.2.4`，避免主应用、内部包、第三方包之间出现 React 版本漂移。
- `pdfjs-dist`：统一到 `5.4.530`，通常和 PDF 渲染、worker、打包兼容性有关。
- `stylelint-config-clean-order`：固定 lint 配置版本，避免格式化或 stylelint 规则变化造成大面积差异。
- `jose`：固定认证/加密相关依赖版本。
- `@react-pdf/image`：固定 react-pdf 图像处理子依赖版本。

需要注意：根 `package.json` 里也有一个 `overrides` 字段，例如包含 `antd`、`better-auth`、`drizzle-orm`、`lexical` 等更多覆盖项。pnpm 对 workspace 安装时主要读取 `pnpm-workspace.yaml` 中的 pnpm 配置；`package.json` 的 `overrides` 更像 npm/yarn 生态也能识别的包管理元信息。根据当前片段推断，这个仓库同时保留两处，是为了兼顾不同工具链或历史迁移，但 pnpm workspace 的核心配置仍以 `pnpm-workspace.yaml` 为准。

第四部分是 `patchedDependencies`：

```yaml
patchedDependencies:
  '@upstash/qstash': patches/@upstash__qstash.patch
```

这表示安装 `@upstash/qstash` 时，pnpm 会额外应用本仓库里的补丁文件：

```text
patches/@upstash__qstash.patch
```

也就是说，项目并不是直接使用 npm 上原始的 `@upstash/qstash`，而是在安装解析后对它打了一个本地 patch。

这种机制通常用于：

- 临时修复第三方包 bug；
- 等待上游合并修复前先在项目内兜底；
- 调整类型定义或兼容某个运行环境；
- 避免 fork 整个第三方包。

阅读到这里要意识到：如果项目里和 QStash、Upstash Workflow、异步任务相关的行为和官方包表现不一致，`patches/@upstash__qstash.patch` 是必须检查的上游证据之一。

## 上下游关系

这个文件的上游主要是 **包管理器 pnpm** 和仓库根目录的包管理配置。

相关上游配置包括：

- 根 `package.json`：定义根包、脚本、依赖、`workspace:*` 本地依赖。
- `.npmrc`：定义 pnpm/npm 安装行为，例如 `lockfile=false`、`resolution-mode=highest`、`dedupe-peer-dependents=true`、`ignore-workspace-root-check=true` 等。
- `patches/`：保存 `patchedDependencies` 引用的补丁文件。
- 各 workspace 子包的 `package.json`：只有存在 `package.json` 的目录，才会真正成为可安装、可过滤、可发布或可构建的包。

它的下游主要是所有依赖安装、脚本执行和包解析流程：

- `pnpm install`
- `pnpm --filter <package> ...`
- `pnpm -r ...`
- 根脚本中调用的 `pnpm run build:spa:raw`
- 根脚本中调用的 `pnpm db:migrate`
- 根脚本中调用的 `pnpm --filter @lobechat/e2e-tests test`
- `workspace:*` 依赖解析
- 第三方依赖版本锁定
- patched dependency 的补丁应用

从项目结构看，`packages/**` 是最大下游。根应用通过 `package.json` 依赖大量内部包，例如：

```json
"@lobechat/agent-runtime": "workspace:*",
"@lobechat/agent-signal": "workspace:*",
"@lobechat/builtin-tools": "workspace:*",
"@lobechat/model-runtime": "workspace:*"
```

这些依赖能指向本地源码，而不是去 npm registry 下载，靠的就是 workspace 配置。

`e2e` 也是下游。根脚本里有：

```json
"test:e2e": "pnpm --filter @lobechat/e2e-tests test"
```

这个命令能找到 `@lobechat/e2e-tests`，前提就是 `e2e` 被列入 `packages`。

`apps/desktop/src/main` 也是下游。它作为 `@lobehub/desktop-ipc-typings` 暴露类型定义，供桌面相关代码引用。根据当前片段推断，它被单独纳入 workspace，是为了让 IPC 类型包可以通过包名被解析，而不是靠相对路径到处引用。

## 运行/调用流程

这个文件没有函数级调用流程，它的“运行”发生在包管理阶段。可以按以下顺序理解：

1. 开发者在仓库根目录执行 `pnpm install` 或其他 pnpm 命令。

2. pnpm 读取根目录的 `pnpm-workspace.yaml`。

3. pnpm 根据 `packages` 展开 workspace 范围：

   ```text
   packages/**
   .
   e2e
   apps/desktop/src/main
   ```

4. pnpm 在这些路径下寻找 `package.json`，把匹配到的目录注册为 workspace package。

5. 当根 `package.json` 或某个子包声明：

   ```json
   "@lobechat/xxx": "workspace:*"
   ```

   pnpm 会在 workspace 成员中查找同名包，建立本地链接。

6. pnpm 解析依赖树时应用 `overrides`，例如强制把 `react`、`react-dom` 统一到 `19.2.4`。

7. pnpm 安装依赖时，如果遇到 `@upstash/qstash`，会应用：

   ```text
   patches/@upstash__qstash.patch
   ```

8. pnpm 执行依赖构建脚本时，只允许 `onlyBuiltDependencies` 里列出的依赖走被批准的构建流程。

9. 后续执行根脚本或过滤包脚本时，例如：

   ```bash
   pnpm --filter @lobechat/e2e-tests test
   ```

   pnpm 会基于已经识别出的 workspace 图谱定位目标包和依赖关系。

这个流程说明：`pnpm-workspace.yaml` 不直接启动 Next.js、Vite、Electron 或测试框架，但它决定这些脚本在 monorepo 中能否找到正确的包和依赖版本。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就陷入所有 `packages` 子包：

1. 先读 `pnpm-workspace.yaml`

   重点看四个顶层字段：

   - `packages`
   - `onlyBuiltDependencies`
   - `overrides`
   - `patchedDependencies`

   先建立“这个仓库有哪些 workspace 成员，以及安装阶段有哪些全局规则”的概念。

2. 再读根 `package.json`

   重点看：

   - `name`
   - `workspaces`
   - `scripts`
   - `dependencies` 里的 `workspace:*`
   - `overrides`

   这里能看到根应用如何依赖内部包，以及常用命令如何调用 pnpm。

3. 再读 `.npmrc`

   重点看 pnpm 安装策略：

   - `lockfile=false`
   - `resolution-mode=highest`
   - `dedupe-peer-dependents=true`
   - `ignore-workspace-root-check=true`
   - `public-hoist-pattern[]`

   尤其要注意 `lockfile=false`：这个仓库当前配置下不会生成传统意义上的 `pnpm-lock.yaml` 锁文件。因此依赖稳定性更多依赖版本声明、`overrides` 和包管理策略。

4. 再抽样看 workspace 子包

   可以先看：

   - `e2e/package.json`
   - `apps/desktop/src/main/package.json`
   - `packages/agent-runtime/package.json`
   - `packages/builtin-tools/package.json`
   - `packages/database/package.json`

   目标不是立刻读源码，而是先理解这些包的 `name`、`scripts`、`dependencies` 和 `exports`。

5. 最后再看 `patches/`

   如果某个行为和第三方库官方文档不一致，或者看到 `@upstash/qstash` 相关问题，再进入 `patches/@upstash__qstash.patch` 查看具体修改。

## 常见误区

误区一：以为 `package.json` 的 `workspaces` 就是 pnpm 的唯一依据。

在 pnpm 项目里，`pnpm-workspace.yaml` 才是 workspace 的核心配置。这个仓库的根 `package.json` 也有 `workspaces`，但 `pnpm-workspace.yaml` 的 `packages/**` 更宽，会覆盖 `packages` 下更深层的包。阅读 monorepo 边界时，应优先看 `pnpm-workspace.yaml`。

误区二：以为 `packages/**` 会把所有文件都当成包。

不会。它只是搜索范围。真正成为 workspace package 的目录还需要有 `package.json`。例如 `packages/**` 覆盖很多路径，但 pnpm 只会把含有合法 `package.json` 的目录注册为包。

误区三：以为 `.` 只是当前目录，没有特殊意义。

这里的 `.` 表示仓库根目录本身也是 workspace 成员。根包 `@lobehub/lobehub` 不只是脚本集合，它也是一个真实 package，拥有依赖、脚本和 workspace 本地依赖关系。

误区四：忽略 `e2e` 是单独 workspace 包。

`e2e` 不只是测试目录，它有自己的 `package.json` 和包名 `@lobechat/e2e-tests`。根命令 `pnpm --filter @lobechat/e2e-tests test` 能工作，是因为 `e2e` 被显式写进了 `pnpm-workspace.yaml`。

误区五：忽略 `apps/desktop/src/main` 这个非常规包路径。

大多数人会以为 workspace 包只在 `packages/` 或 `apps/desktop` 一级目录下，但这里单独纳入的是 `apps/desktop/src/main`。它是 `@lobehub/desktop-ipc-typings`，导出 IPC 类型定义。根据当前片段推断，这是为了让桌面主进程相关类型能作为独立包被解析。

误区六：把 `overrides` 当成普通依赖声明。

`overrides` 不是“项目直接依赖这些包”的意思，而是“无论依赖树里谁要这些包，都尽量统一成这里指定的版本”。它是一种全局依赖治理手段。改这里可能影响整个仓库，而不只是某个包。

误区七：忽略 `patchedDependencies` 带来的行为差异。

`@upstash/qstash` 被本地 patch 过。排查 QStash、workflow、异步任务相关问题时，只看 npm 官方源码或文档可能不够，还要看 `patches/@upstash__qstash.patch`。

误区八：看到没有 `pnpm-lock.yaml` 就以为仓库不完整。

当前 `.npmrc` 里有：

```ini
lockfile=false
```

所以这个仓库配置上就是不生成或不使用常规 `pnpm-lock.yaml`。依赖解析稳定性更多由版本范围、`overrides`、pnpm resolution 策略和 CI 环境共同决定。
