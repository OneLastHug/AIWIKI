# 文件：packages/coding-agent/package.json

## 一句话定位

`packages/coding-agent/package.json` 是 `@earendil-works/pi-coding-agent` 这个工作区包的发布、构建、CLI 暴露和依赖边界清单；它不实现业务逻辑，但决定外部用户安装后拿到的 `pi` 命令、SDK 入口、随包发布的资源，以及本包如何参与 monorepo 构建和发布。

## 它暴露/定义了什么

这个文件定义了 npm 包名 `@earendil-works/pi-coding-agent`、版本 `0.79.1`、ESM 模块类型、Node 引擎要求 `>=22.19.0`，以及 `piConfig.configDir` 为 `.pi`，说明该 CLI 的用户级配置目录与 Pi 运行环境绑定。

对外暴露分两类：一类是命令行入口，`bin.pi` 指向 `dist/cli.js`，安装后用户执行 `pi` 实际进入编译后的 CLI；另一类是 SDK/API 入口，`main`、`types`、`exports["."]` 都指向 `dist/index.js` 和 `dist/index.d.ts`，供扩展、SDK 示例或外部 Node 项目通过 `@earendil-works/pi-coding-agent` 导入类型和运行时 API。

它还定义发布内容：`dist`、`docs`、`examples`、`containerization.md`、`CHANGELOG.md`、`npm-shrinkwrap.json`。这意味着该包不仅发布可执行代码，也把文档、示例扩展和锁定依赖快照作为产品接口的一部分。

## 谁调用它

根仓库的 `package.json` 通过 workspaces 纳入 `packages/coding-agent`，并在根级 `build` 中按 `tui`、`ai`、`agent`、`coding-agent` 顺序进入本包执行 `npm run build`。根级 `check:shrinkwrap` 和 `shrinkwrap:coding-agent` 也围绕本包的 `npm-shrinkwrap.json` 工作。

npm、Node、Bun 和发布流水线也会读取它：npm 根据 `bin`、`exports`、`files`、`dependencies` 打包；用户全局安装后通过 `pi` 调用 `dist/cli.js`；外部扩展和 SDK 示例通过包名导入 `ExtensionAPI`、`createAgentSession`、`SessionManager` 等导出。仓库内 `docs/sdk.md`、`docs/extensions.md`、`examples/extensions/*` 多处引用 `@earendil-works/pi-coding-agent`，说明它同时服务 CLI 用户和扩展开发者。

## 它调用谁

`package.json` 本身不会“调用”代码，但它的脚本和依赖声明把调用链固定下来。运行时依赖包括内部包 `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai`、`@earendil-works/pi-tui`，分别承接 agent 核心抽象、模型/Provider 层和终端 UI 能力。外部依赖中，`chalk` 负责终端样式，`cross-spawn`、`proper-lockfile`、`glob`、`ignore`、`minimatch` 支撑命令执行、文件遍历和并发安全，`typebox`、`yaml`、`undici` 支撑 schema、配置和 HTTP，`@silvia-odwyer/photon-node` 用于图片处理；`@mariozechner/clipboard` 是可选剪贴板能力。

构建脚本还调用相邻工作区：`build:binary` 会先构建 `../tui`、`../ai`、`../agent`，再构建本包，并用 `bun build --compile` 生成 `dist/pi` 二进制。

## 核心流程

开发构建流程是：`clean` 删除 `dist`；`build` 使用 `tsgo -p tsconfig.build.json` 编译 TypeScript，再给 `dist/cli.js` 加可执行权限，最后执行 `copy-assets` 把交互主题、图片资源和 HTML 导出模板复制到 `dist`。这对应源码中的 `src/cli.ts`、`src/main.ts`、`src/modes/interactive/*`、`src/core/export-html/*` 等运行入口和资源目录。

二进制构建流程是：先确保 `tui`、`ai`、`agent` 三个内部包已构建，再构建 coding-agent 自身，然后把 `dist/bun/cli.js` 和 `src/utils/image-resize-worker.ts` 编译成 `dist/pi`，最后执行 `copy-binary-assets`，复制 `package.json`、`README.md`、`CHANGELOG.md`、主题、图片、导出模板、docs、examples 和 photon wasm。根据当前片段推断，二进制发布需要更扁平的资源布局，所以 `copy-binary-assets` 复制到 `dist/theme`、`dist/assets`、`dist/export-html`，而普通 Node 包保留接近源码目录的 `dist/modes/interactive/*`、`dist/core/export-html/*`。

发布前流程是：`prepublishOnly` 依次执行 `clean`、`build`、`shrinkwrap`，确保产物干净、可编译，并生成本包专用 `npm-shrinkwrap.json`。

## 关键函数的高层作用

目标文件没有 TypeScript 函数；这里的“关键函数”应理解为关键脚本入口。

`build` 是普通 npm 包产物入口，负责从源码生成 `dist` 并补齐运行所需静态资源。它直接影响 `bin` 和 `exports` 指向的文件是否存在。

`build:binary` 是单文件可执行产物入口，额外依赖 Bun 编译和内部包构建顺序，适合本地 release 或二进制分发场景。

`copy-assets` 和 `copy-binary-assets` 是资源装配入口，保证交互模式主题、图片和 HTML 导出模板在运行时可被找到。它们不是业务逻辑，但资源路径一旦错位，CLI 可能编译成功却在运行时缺主题、图片或导出页面模板。

`shrinkwrap` 调用根目录脚本生成 `packages/coding-agent/npm-shrinkwrap.json`，用于锁定发布包依赖树。`prepublishOnly` 把清理、构建、锁定依赖串成发布门禁。

## 修改风险

最高风险是改动 `bin`、`main`、`types`、`exports`。这些字段是外部契约：`bin.pi` 错会导致安装后 `pi` 不可执行；`exports` 错会破坏扩展、SDK 示例和第三方项目的导入；`types` 错会让 TypeScript 用户失去类型或拿到旧类型。

其次是 `files` 和资源复制脚本。若遗漏 `docs`、`examples`、`npm-shrinkwrap.json` 或 HTML/主题/图片资源，包仍可能发布成功，但用户运行扩展、查看文档、使用交互主题或导出 HTML 时才暴露问题。`copy-assets` 与 `copy-binary-assets` 的目标目录不同，修改时要同时理解 Node 包运行路径和 Bun 二进制运行路径。

依赖版本风险也高。内部包版本需要与 lockstep release 保持一致；外部直接依赖在本仓库规则下应精确锁定。新增运行时依赖不仅影响安装体积，也可能要求更新 `package-lock.json` 和 `npm-shrinkwrap.json`。可选依赖 `@mariozechner/clipboard` 不能随意改成强依赖，否则会改变跨平台安装失败模式。

脚本风险集中在发布链路。`prepublishOnly` 是发布前门禁，移除 `shrinkwrap` 或 `clean` 可能让脏产物、未锁定依赖进入 npm 包。`build:binary` 的内部包构建顺序体现了 coding-agent 对 `tui`、`ai`、`agent` 的产物依赖，调整顺序或删掉前置构建可能造成二进制包含旧代码。
