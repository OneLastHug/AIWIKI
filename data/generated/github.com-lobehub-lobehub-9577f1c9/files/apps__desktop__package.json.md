# 文件：apps/desktop/package.json

## 它负责什么

`apps/desktop/package.json` 是 LobeHub 桌面端子应用的包清单，主要负责三件事：

1. 定义 Electron 桌面应用的入口、身份和私有包属性。
2. 收口桌面端开发、构建、打包、校验、测试、i18n、依赖安装等命令。
3. 声明桌面端运行和构建所需的依赖，包括 Electron 生态、LobeHub workspace 内部包、原生模块、测试和构建工具。

这个文件本身不包含业务代码，但它决定了桌面应用如何被启动、如何被 `electron-vite` 构建、如何被 `electron-builder` 打成 macOS / Windows / Linux 安装包，以及哪些依赖会参与桌面端的运行时或构建时流程。

它的核心定位可以理解为：`apps/desktop` 这个 Electron 子工程的“任务入口”和“依赖边界”。

## 关键组成

首先是包基础信息：

```json
{
  "name": "lobehub-desktop-dev",
  "version": "0.0.0",
  "private": true,
  "description": "LobeHub Desktop Application",
  "main": "./dist/main/index.js"
}
```

`private: true` 表示这个包不是为了发布到 npm，而是 monorepo 内部的桌面应用工程。`main: "./dist/main/index.js"` 很关键，它告诉 Electron 在生产或预览时从构建后的主进程入口启动。这个路径和 `electron.vite.config.ts` 中的 `main.build.outDir: 'dist/main'` 对应。

`scripts` 是这个文件最重要的部分。

`dev`：

```json
"dev": "electron-vite dev"
```

这是桌面端开发入口。它会通过 `electron-vite` 同时处理 Electron main、preload 和 renderer 的开发构建。结合 `apps/desktop/electron.vite.config.ts` 看，renderer 并不是简单的单页入口，而是有多个 HTML 入口：

- `index.html`
- `overlay.html`
- `popup.html`

配置里还写了一个 `electronDesktopHtmlPlugin`，用于在开发服务器里把 `/popup/*`、`/overlay` 等路径重写到对应 HTML。这说明 `pnpm dev` / `npm run dev` 背后不仅启动主窗口，也服务桌面端的 popup、overlay 等 SPA 入口。

`build:main`：

```json
"build:main": "cross-env NODE_OPTIONS=--max-old-space-size=8192 electron-vite build"
```

这是生产构建入口。名字叫 `build:main`，但根据 `electron.vite.config.ts`，它实际会构建：

- main：输出到 `dist/main`
- preload：输出到 `dist/preload`
- renderer：输出到 `apps/desktop/dist/renderer`

所以不要被脚本名误导，它不是只构建 Electron main process。

`package:*` 系列是平台打包入口：

```json
"package:mac": "npm run build:main && electron-builder --mac --config electron-builder.mjs  --publish never",
"package:win": "npm run build:main && electron-builder --win --config electron-builder.mjs  --publish never",
"package:linux": "npm run build:main && electron-builder --linux --config electron-builder.mjs  --publish never"
```

它们先执行 `build:main`，再调用 `electron-builder`，并指定 `apps/desktop/electron-builder.mjs` 作为打包配置。`--publish never` 表示打包时不发布产物。

`package:local` 和 `package:local:reuse` 更适合本地验证：

```json
"package:local": "npm run build:main && electron-builder --dir --config electron-builder.mjs  --c.mac.notarize=false -c.mac.identity=null --c.asar=false",
"package:local:reuse": "electron-builder --dir --config electron-builder.mjs  --c.mac.notarize=false -c.mac.identity=null --c.asar=false"
```

`package:local` 会重新构建再打包目录产物；`package:local:reuse` 复用已有 `dist`，适合只想快速重跑 packaging 的场景。这里关闭了 macOS notarize、签名 identity，并关闭 `asar`，便于本地调试打包结果。

`build:cli`：

```json
"build:cli": "cd ../cli && cross-env MINIFY=1 bun run build"
```

这个脚本说明桌面端会嵌入 CLI。对应 `electron-builder.mjs` 的 `beforePack` hook：打包前会执行 `npm run build:cli`，再把 `../cli/dist/index.js` 复制到 `apps/desktop/resources/bin/lobe-cli.js`。因此桌面包不是孤立 Electron 壳，它还会携带 CLI bundle。

`download:agent-browser`：

```json
"download:agent-browser": "node scripts/download-agent-browser.mjs"
```

这个脚本也会在 `electron-builder.mjs` 的 `beforePack` 中被调用，用于下载 `agent-browser` binary。根据当前片段推断，这个二进制用于桌面端内置的 agent/browser 自动化能力，依据是桌面打包阶段会主动下载并放入资源流程，同时依赖中有 `@lobechat/heterogeneous-agents`、`@lobechat/desktop-bridge` 等 agent/desktop 相关 workspace 包。

`lint` 系列脚本：

```json
"lint": "npm run lint:ts && npm run lint:style && npm run type-check && npm run lint:circular"
```

桌面端 lint 不只是 ESLint 和 stylelint，还包含：

- `type-check`：`tsgo --noEmit -p tsconfig.json`
- `lint:circular:main`：检查 `src/**/*.ts` 的循环依赖
- `lint:circular:packages`：检查 `packages/**/src/**/*.ts` 的循环依赖

这里的 `packages/**/src/**/*.ts` 是相对于 `apps/desktop` 的本地目录，不是仓库根目录下的 `packages`。这暗示 `apps/desktop` 下也有自己的桌面端内部 packages 结构。

`i18n`：

```json
"i18n": "tsx scripts/i18nWorkflow/index.ts && lobe-i18n"
```

桌面端有独立 i18n 工作流。它先运行本地脚本 `scripts/i18nWorkflow/index.ts`，再调用 `lobe-i18n`。结合 README 中“18+ 种语言的懒加载”描述，可以把它理解为桌面端本地化资源生成和同步入口。

`postinstall`：

```json
"postinstall": "electron-builder install-app-deps"
```

安装后自动让 `electron-builder` 安装或重建 Electron app 依赖，尤其是原生依赖。这个项目中有 `@napi-rs/canvas`、`node-screenshots`、`node-mac-permissions` 这类 native 或平台相关包，所以 postinstall 很重要。

依赖部分分为三类。

`dependencies` 是运行时依赖：

```json
"@lobehub/fluent-emoji"
"@napi-rs/canvas"
"electron-log"
"get-windows"
"node-screenshots"
```

这里没有把 `electron` 放在 `dependencies`，说明 Electron 本体主要作为构建/开发工具依赖存在。运行时功能依赖里比较醒目的是：

- `electron-log`：桌面端日志。
- `get-windows`：获取系统窗口信息。
- `node-screenshots`：屏幕截图能力。
- `@napi-rs/canvas`：原生 canvas 能力，可能服务截图、渲染或图像处理。
- `@lobehub/fluent-emoji`：emoji 资源能力。

`devDependencies` 承担了大量实际工程能力，不能简单理解为“只在开发时用”。在 Electron app 中，很多构建期依赖会影响最终包内容，例如：

- `electron`
- `electron-vite`
- `electron-builder`
- `electron-updater`
- `electron-store`
- `electron-is`
- `electron-window-state`
- `@electron-toolkit/*`

workspace 依赖也在这里声明：

```json
"@lobechat/desktop-bridge": "workspace:*",
"@lobechat/device-gateway-client": "workspace:*",
"@lobechat/electron-client-ipc": "workspace:*",
"@lobechat/electron-server-ipc": "workspace:*",
"@lobechat/file-loaders": "workspace:*",
"@lobechat/heterogeneous-agents": "workspace:*",
"@lobechat/local-file-shell": "workspace:*"
```

这些包构成桌面端和 monorepo 其他能力之间的桥：

- `desktop-bridge`：桌面桥接能力。
- `electron-client-ipc` / `electron-server-ipc`：Electron IPC 通信。
- `device-gateway-client`：设备网关客户端。
- `file-loaders`：本地文件读取/解析。
- `heterogeneous-agents`：异构 agent 能力。
- `local-file-shell`：本地文件 shell 能力。

`optionalDependencies` 里只有：

```json
"node-mac-permissions": "^2.5.0"
```

这说明 macOS 权限能力是可选安装的。`electron.vite.config.ts` 中也把 `node-mac-permissions` 放进了 main process external 列表，`electron-builder.mjs` 里还有 macOS 权限说明文案，例如 camera、microphone、screen capture、Documents、Downloads 等权限。

最后是 `pnpm` 定制：

```json
"onlyBuiltDependencies": [
  "@napi-rs/canvas",
  "electron",
  "electron-builder",
  "node-mac-permissions"
],
"overrides": {
  "react": "19.2.4",
  "react-dom": "19.2.4"
}
```

`onlyBuiltDependencies` 限制哪些依赖允许执行 build 脚本，通常是为了 pnpm 安装安全和可重复性。`react` / `react-dom` override 保证桌面端 renderer 使用固定的 React 19.2.4，避免 workspace 或间接依赖拉出不一致版本。

## 上下游关系

上游主要来自 monorepo 和桌面端配置文件。

`apps/desktop/package.json` 被包管理器和脚本系统读取。开发者在 `apps/desktop` 目录下执行 `pnpm dev`、`pnpm package:mac`、`pnpm type-check` 等命令时，实际入口就是这里的 `scripts`。

它的构建上游是：

- `apps/desktop/electron.vite.config.ts`
- `apps/desktop/electron-builder.mjs`
- `apps/desktop/tsconfig.json`
- `apps/desktop/vitest.config.mts`
- `apps/desktop/stylelint.config.mjs`
- `apps/desktop/.i18nrc.js`

其中 `electron.vite.config.ts` 读取了当前 `package.json` 的 `version`：

```ts
const desktopPackageJson = JSON.parse(
  readFileSync(path.resolve(__dirname, 'package.json'), 'utf8'),
) as { version: string };
```

然后把版本注入 renderer：

```ts
__MAIN_VERSION__: JSON.stringify(desktopPackageJson.version)
```

所以 `package.json` 的 `version` 不只是 npm 元数据，也会进入桌面 renderer 构建时常量。当前版本是 `0.0.0`，说明这个源码片段可能处于开发态，真实发布版本可能由 CI 或发布流程改写。根据当前片段推断，renderer 里可以通过 `__MAIN_VERSION__` 感知桌面应用版本。

`electron-builder.mjs` 也读取了同一个 `package.json`：

```js
const packageJSON = JSON.parse(await fs.readFile(path.join(__dirname, 'package.json'), 'utf8'));
```

并用于输出构建版本日志：

```js
console.info(`Build Version ${packageJSON.version}, Channel: ${channel}`);
```

同时 `electron-builder` 的产物命名中使用 `${version}`，因此 `package.json.version` 会影响安装包文件名、更新文件和发布产物标识。

下游则包括：

- Electron 主进程启动入口：`main` 指向 `dist/main/index.js`。
- 开发服务器：`electron-vite dev`。
- 构建产物：`dist/main`、`dist/preload`、`dist/renderer`。
- 打包产物：`release` 目录，配置来自 `electron-builder.mjs`。
- CLI 嵌入资源：`resources/bin/lobe-cli.js`。
- 自动更新配置：`electron-builder.mjs` 中的 `publish`、`detectUpdateChannel`、`generateUpdatesFilesForAllChannels`。
- 原生模块复制和 asar unpack：由 `native-deps.config.mjs`、`external-runtime-deps.config.mjs` 配合打包流程完成。

和仓库根的关系上，`apps/desktop` 是 monorepo 中的一个应用子包。它通过 `workspace:*` 消费内部包，但又带有自己的 `pnpm-workspace.yaml` 和 `install-isolated` 脚本，说明它支持相对隔离地安装和开发桌面端依赖。

## 运行/调用流程

开发流程通常是：

1. 进入 `apps/desktop`。
2. 安装依赖，README 中推荐 `pnpm install-isolated`，对应脚本实际是 `pnpm install`。
3. 执行 `pnpm dev` 或 `npm run dev`。
4. `electron-vite dev` 读取 `electron.vite.config.ts`。
5. main、preload、renderer 进入开发构建。
6. Electron 启动桌面应用。
7. renderer 通过 `index.html`、`overlay.html`、`popup.html` 等入口加载不同窗口或页面。

构建流程是：

1. 执行 `pnpm build:main`。
2. 设置 `NODE_OPTIONS=--max-old-space-size=8192`，给构建过程更大的 Node.js 内存。
3. `electron-vite build` 构建 main、preload、renderer。
4. 主进程输出到 `dist/main`，preload 输出到 `dist/preload`，renderer 输出到 `dist/renderer`。
5. `package.json.main` 指向的 `./dist/main/index.js` 成为 Electron app 的入口。

本地打包流程以 `package:local` 为例：

1. 执行 `npm run build:main`。
2. 执行 `electron-builder --dir --config electron-builder.mjs`。
3. `electron-builder.mjs` 的 `beforePack` 运行：
   - 复制 native modules 到源码侧准备打包。
   - 复制 external runtime modules。
   - 下载 `agent-browser` binary。
   - 执行 `npm run build:cli` 构建 CLI。
   - 复制 `../cli/dist/index.js` 到 `resources/bin/lobe-cli.js`。
   - 生成 `resources/cli-package.json`。
4. `electron-builder` 按平台配置组织文件、协议、图标、权限、更新信息。
5. `afterPack` 运行：
   - 把 native modules 复制到 `app.asar.unpacked/node_modules`。
   - macOS 下处理 `Assets.car` 和 Electron Framework localization。
6. 输出目录式本地包，且 `package:local` 会禁用签名、公证和 asar，便于调试。

正式平台包流程类似，只是 `package:mac`、`package:win`、`package:linux` 会生成对应平台安装包，并默认不发布。

自动更新相关流程由环境变量影响：

- `UPDATE_CHANNEL`
- `UPDATE_SERVER_URL`
- `RELEASE_NOTES`

`electron-builder.mjs` 会根据 `UPDATE_CHANNEL` 判断 stable、nightly、canary，并决定 protocol scheme：

- stable：`lobehub`
- nightly：`lobehub-nightly`
- canary：`lobehub-canary`

如果存在 `UPDATE_SERVER_URL`，更新发布配置使用 generic provider；否则回退到 GitHub provider。这个逻辑不是写在 `package.json`，但由 `package:*` 脚本触发。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `apps/desktop/package.json` 的基础字段  
   重点看 `main`、`scripts`、`dependencies`、`devDependencies`。先建立“它是 Electron 子应用入口”的概念。

2. 再读 `scripts.dev` 和 `scripts.build:main`  
   明白开发时用 `electron-vite dev`，构建时用 `electron-vite build`。不要急着看业务代码。

3. 接着读 `apps/desktop/electron.vite.config.ts`  
   对照 `package.json` 理解 `electron-vite` 到底构建了什么。特别注意 main、preload、renderer 三段配置，以及 `index.html`、`popup.html`、`overlay.html` 三个 renderer 入口。

4. 然后读 `scripts.package:*` 和 `apps/desktop/electron-builder.mjs`  
   理解从 `dist` 到安装包的过程。重点看 `beforePack`、`afterPack`、`files`、`asarUnpack`、`mac`、`win`、`linux`、`publish`。

5. 再看 workspace 内部依赖  
   从 `@lobechat/electron-client-ipc`、`@lobechat/electron-server-ipc`、`@lobechat/desktop-bridge` 这些名字入手，理解桌面端如何和内部包协作。

6. 最后再进入 `apps/desktop/src`  
   先找 main process 的应用入口、窗口管理、IPC、服务注册，再看 renderer 和 preload。这样不会一开始就陷入细节。

## 常见误区

第一个误区是以为 `build:main` 只构建主进程。实际上它执行的是 `electron-vite build`，根据 `electron.vite.config.ts`，main、preload、renderer 都在这个构建流程里。脚本名更像历史命名或简写，不代表真实构建范围。

第二个误区是以为 `devDependencies` 都不会影响最终桌面包。Electron 项目里很多构建和打包关键能力都在 `devDependencies`，例如 `electron`、`electron-builder`、`electron-vite`、`electron-updater`、`electron-store`。尤其打包流程会把部分 native/runtime 模块复制到最终资源里，所以要结合 `electron-builder.mjs` 判断，而不是只看依赖字段名。

第三个误区是忽略 `postinstall`。`electron-builder install-app-deps` 对原生模块非常重要。如果跳过安装后处理，`@napi-rs/canvas`、`node-screenshots`、`node-mac-permissions` 这类模块在 Electron 环境里可能出现 ABI 或缺文件问题。

第四个误区是把 `version: "0.0.0"` 当成无意义字段。这个版本会被 `electron.vite.config.ts` 注入为 `__MAIN_VERSION__`，也会被 `electron-builder.mjs` 读取并参与产物版本。当前值看起来是开发态占位，但发布流程中它会变得关键。

第五个误区是只看 `package.json` 就判断打包内容。真实打包内容由 `electron-builder.mjs` 的 `files`、`extraResources`、`asarUnpack`、`beforePack`、`afterPack` 共同决定。比如 CLI bundle 和 `agent-browser` binary 都不是从 `dependencies` 字段直接看出来的，而是在打包 hook 里准备的。

第六个误区是认为桌面端只有一个 renderer 页面。`electron.vite.config.ts` 明确配置了 `main`、`overlay`、`popup` 三个 HTML input，并有开发服务器路径重写逻辑。也就是说桌面端包含多入口 renderer，可能对应主窗口、浮层窗口、弹窗窗口等不同 UI 场景。

第七个误区是 README 版本信息一定等于当前源码依赖。当前 `package.json` 中 Electron 是 `41.3.0`，Vite 是 `8.0.12`，TypeScript 是 `^5.9.3`；而 README.zh-CN 中技术栈段落写的是 Electron `37.1.0`、Vite `6.2+`、TypeScript `5.7+`。学习时应以 `package.json` 和 lockfile / 实际配置为准，README 更适合理解意图和架构概览。
