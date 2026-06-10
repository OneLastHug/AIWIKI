# 文件：package.json

## 一句话定位

`package.json` 是 AionUi 仓库的根级工程清单：它定义项目身份、Bun workspace、Electron/Vite 启动与打包入口、质量检查命令、测试命令、核心运行依赖、构建依赖，以及若干依赖版本约束策略。

## 它暴露/定义了什么

这个文件主要暴露四类信息。第一类是包元数据，包括 `name`、`version`、`description`、`license`、`author`、`productName`、`main`，其中 `main` 指向 `./out/main/index.js`，说明最终桌面应用主进程产物会落到 `out/main`。第二类是工作区定义：`workspaces: ["packages/*"]` 将 `packages` 下的子包纳入统一依赖解析，当前根依赖中也通过 `@aionui/web-host: workspace:*` 引用了本仓库子包。第三类是脚本命令，例如 `dev`、`package`、`dist`、`build-*`、`lint`、`format`、`test`、`i18n:types`、`test:e2e`。第四类是依赖治理，包括 `dependencies`、`devDependencies`、`optionalDependencies`、`resolutions`、`overrides`、`patchedDependencies`、`electronRebuild` 和 `engines`。

## 谁调用它

直接调用者主要是包管理器和项目自动化工具。开发者运行 `bun run dev`、`bun run test`、`bun run lint:fix` 等命令时，Bun 会读取这里的 `scripts`、依赖和 workspace 配置。CI、pre-commit、`justfile` 中的质量门禁也会间接依赖这些脚本名。Electron 打包链路会读取项目元数据、`main`、`productName`、依赖版本和 native 模块相关配置。根据当前片段推断，`husky`、`lint-staged` 在安装或提交阶段也会读取这里的 `prepare`、`postinstall`、`lint-staged` 配置，依据是文件中同时定义了 `prepare: husky`、`postinstall: node scripts/postinstall.js` 和 lint-staged 规则。

## 它调用谁

`package.json` 本身不执行代码，但它把命令分发给外部工具和仓库脚本。开发模式调用 `electron-vite dev --config packages/desktop/electron.vite.config.ts`；普通构建调用 `electron-vite build`；发行构建统一进入 `scripts/build-with-builder.js`，再按 `--mac`、`--win`、`--linux`、`--arm64`、`--x64` 等参数分流。Web UI 相关命令进入 `scripts/webui.ts`，密码重置进入 `scripts/resetpass.ts`，i18n 类型生成进入 `scripts/generate-i18n-types.js`，安装后处理进入 `scripts/postinstall.js`。测试侧分别调用 `vitest`、`playwright`、`bun test`，格式和 lint 侧调用 `oxfmt`、`oxlint`。

## 核心流程

日常开发流程以 `dev` 或 `start` 为入口，加载 `packages/desktop/electron.vite.config.ts`，启动 Electron 主进程、preload 与 renderer 的开发构建。若需要多实例调试，`start:multi` 会通过 `AIONUI_MULTI_INSTANCE=1` 改变运行时行为。Web UI 模式绕过 Electron 开发命令，进入 `scripts/webui.ts`，并可通过 `--remote` 或 `NODE_ENV=production` 切换远程/生产形态。

构建流程分两层：`package`/`make` 只做 `electron-vite build`，偏向生成基础产物；`dist`、`build`、`build-mac`、`build-win`、`build-deb` 等进入 `scripts/build-with-builder.js`，偏向真正发行包。平台和架构由脚本参数控制，因此修改这些命令会直接影响产物矩阵。

质量流程由 `lint`、`format:check`、`test`、`test:coverage`、`test:e2e`、`i18n:types` 组成。根目录约定中还要求推送前通过 `just push` 串联这些能力；因此这里的脚本名既是本地入口，也是自动化契约。

## 关键函数的高层作用

这个文件没有 JavaScript/TypeScript 函数，所谓“关键函数”在这里应理解为关键脚本入口。`dev`/`start` 负责启动桌面开发环境，是本地调试主入口。`package`/`make` 负责基础构建，验证 Electron/Vite 编译链路是否可用。`dist` 和各 `build-*` 命令负责发行包生成，封装平台、架构参数。`i18n:types` 负责从 i18n 配置生成类型，支撑前端文案键的类型安全。`test`、`test:coverage`、`test:e2e` 分别覆盖单元/集成、覆盖率和端到端测试。`postinstall` 用于依赖安装后的仓库修补或准备动作；结合 `patchedDependencies` 可推断它与补丁、native 依赖或安装环境修复有关，但具体行为需继续阅读 `scripts/postinstall.js`。

## 修改风险

风险最高的是依赖版本和版本约束。`dependencies` 中同时包含 Electron 桌面、React 19、AI SDK、数据库、文档解析、MCP、Web 服务、i18n、Markdown 渲染等运行时依赖；任意升级都可能影响主进程、renderer、Web UI 或打包体积。`resolutions` 与 `overrides` 明确锁定了若干传递依赖版本，通常用于安全修复或兼容性修复，删除或改错可能重新引入漏洞或破坏构建。

脚本名也是稳定接口。CI、`justfile`、贡献文档、开发者习惯都可能引用 `lint:fix`、`format`、`test`、`i18n:types`、`dist` 等名称；重命名会产生连锁失败。构建脚本参数风险也很高，例如 `build-mac` 同时构建 `arm64` 和 `x64`，而 `build-mac:arm64`、`build-mac:x64` 是单架构入口，误改会影响发布产物。

`engines` 限定 `node >=22 <25`，如果放宽或收紧，可能改变依赖安装解析、native 模块编译和 Electron 工具链兼容性。`electronRebuild.electronVersion` 与 `electron` 依赖版本不完全相同，修改时需要核对 native 模块重编译行为，尤其是 `better-sqlite3`、`sharp` 这类依赖。`workspaces` 目前只覆盖 `packages/*`，新增顶层包或移动子包时必须同步调整，否则本地包不会被 workspace 管理，`workspace:*` 依赖也可能解析失败。
