# 文件：package.json
## 一句话定位
这是仓库的根级“总入口配置”，同时定义了包元数据、CLI 可执行入口、workspace 范围、安装与发布脚本、测试与检查命令，以及依赖版本约束。对于这个项目来说，它不只是依赖清单，更像是整个工程的启动面板和发布契约。

## 它暴露/定义了什么
它定义了几个最关键的外部面向：`name`、`version`、`description`、`repository`、`homepage`、`bugs`，以及 `bin` 里的命令映射。当前可以看出，安装后会暴露 `ccb`、`ccb-bun`、`claude-code-best` 三个命令，其中主要指向 `dist/cli-node.js` 或 `dist/cli-bun.js`。  
同时它还定义了：
- `workspaces`：说明这是一个 Bun workspace monorepo，`packages/*`、`packages/@ant/*`、`packages/@anthropic-ai/*` 都纳入统一管理。
- `files`：发布时只带上 `dist` 和少量安装辅助脚本，控制包体积与可交付内容。
- `scripts`：构建、开发、测试、检查、发布前处理、健康检查等全部从这里对外暴露。
- `dependencies` / `devDependencies` / `optionalDependencies` / `overrides`：分别约束运行时依赖、开发依赖、可选依赖和补丁级版本锁定。

## 谁调用它
根据当前片段推断，调用它的主体主要有四类：
1. 包管理器和安装流程：`bun install`、发布安装、workspace 解析、`postinstall`。
2. 开发者命令：`bun run dev`、`bun run build`、`bun test`、`bun run typecheck` 等。
3. CI/CD 和发布流程：`prepublishOnly`、`precheck`、`check:*`、`build:vite`。
4. 下游运行环境：安装后的终端用户通过 `bin` 暴露的 CLI 命令启动程序。

## 它调用谁
它本身不包含业务逻辑，但通过脚本把执行权交给多个文件和工具。能直接看见的有：
- `build.ts`：负责正式构建。
- `scripts/dev.ts`、`scripts/dev-debug.ts`：开发与调试启动。
- `scripts/post-build.ts`：Vite 构建后的收尾处理。
- `scripts/production-test.ts`：生产形态测试。
- `scripts/check-bundle-integrity.ts`、`scripts/health-check.ts`、`scripts/rcs.ts`：分别承担包完整性检查、健康检查和远程控制服务入口。
- `scripts/run-parallel.mjs`、`scripts/postinstall.cjs`、`scripts/setup-chrome-mcp.mjs`：安装后并行执行的辅助脚本。
- 外部工具链：`tsc`、`biome`、`husky`、`vite`、`bun test`、`knip-bun`、`npx mintlify`。

## 核心流程
从工程视角看，它串起的是一条标准但很重的 CLI 产品链路：  
先由 `workspaces` 和依赖表定义整个单仓库边界，再由 `postinstall` 在安装时补齐环境；开发阶段走 `dev` 或 `dev:inspect`，直接进入源码运行；发布阶段走 `build` 或 `build:vite`，把源码打成 `dist/cli.js` 及相关产物；发布前会经过 `prepublishOnly`、`typecheck`、`check`、`test` 等门禁；最终安装到用户机器后，由 `bin` 中的命令进入真正的 CLI。

## 关键函数的高层作用
这里没有传统意义上的函数，真正承担“函数职责”的是几个关键脚本名：
- `build` / `build:bun`：生成可发布的 CLI 产物。
- `dev` / `dev:inspect`：以开发模式运行源码，后者额外开启调试能力。
- `postinstall`：安装后补齐环境、并行执行必要的初始化任务。
- `prepublishOnly`：限制发布前必须先完成构建。
- `typecheck`、`lint`、`test`、`precheck`：作为质量闸门，保证类型、格式和测试一致性。
- `rcs`：启动远程控制服务入口。
- `check:bundle`、`check:unused`、`health`：分别用于产物一致性、死代码检查和仓库健康状态确认。

## 修改风险
这个文件是高风险配置点，改动会直接影响安装、构建、发布和命令入口。最敏感的地方有：
- `bin` 改错会让用户装完后找不到命令，属于直接破坏面。
- `version`、`files`、`prepublishOnly` 会影响发布物内容和发布节奏。
- `scripts` 改错可能让 CI、开发启动、测试或安装流程断裂。
- `workspaces` 调整不当会让内部包解析失败，影响整个 monorepo。
- `overrides` 一旦变动，可能引入依赖树冲突或修复失效。
- 依赖版本升级，尤其是 `typescript`、`vite`、`bun` 相关工具链，可能触发构建或类型检查连锁问题。

简而言之，`package.json` 是这个项目的“工程控制台”：它不写业务，但决定业务怎么被构建、怎么被安装、怎么被调用，以及出问题时会在哪一层炸开。
