# 文件：README.md

## 一句话定位

`README.md` 是仓库的入口级说明文档，用来向新用户和贡献者解释 `claude-code-best` 的项目定位、主要特性、安装运行方式、源码开发入口、调试方式以及进一步阅读路径。它不是运行时代码，但承担“项目门面”和“操作索引”的职责。

## 它暴露/定义了什么

该文件主要暴露五类信息。第一类是项目身份：标题 `Claude Code Best V5 (CCB)`、一句英文 slogan，以及“Anthropic 官方 Claude Code CLI 工具的源码反编译/逆向还原项目”这一核心定位。第二类是功能矩阵：列出 Claude 群控技术、ACP、Remote Control、Langfuse、Web Search、Poor Mode、Channels、自定义模型供应商、Voice Mode、Computer Use、Chrome Use、Sentry、GrowthBook、`/dream` 等能力，并将每项能力指向对应文档。第三类是使用入口：安装版通过 `npm i -g claude-code-best` 获得 `ccb`、`ccb-bun`、`ccb update` 等命令；源码版强调 Bun 环境、`bun install`、`bun run dev`、`bun run build`。第四类是开发者入口：Feature Flags、VS Code attach 调试、Teach Me 学习技能。第五类是社区与文档入口：在线文档、DeepWiki、贡献者、Star History、致谢。

## 谁调用它

`README.md` 不会被 TypeScript 源码直接 import，也不参与 `bun run dev`、`bun run build`、CLI 主流程或包运行逻辑。它的“调用者”主要是人和平台：Git 托管平台会默认渲染它作为仓库首页；npm 包页通常会读取它作为包说明；新贡献者会用它确定环境要求、安装步骤和调试入口；文档维护者会把它作为导航页同步到更完整的 `docs/` 体系。根据当前片段推断，`package.json` 中的 `homepage` 指向 README 语义上的项目主页，`repository`、`bugs` 与 README 中的社区入口共同构成对外入口链路。

## 它调用谁

作为 Markdown 文档，它不执行函数调用，但它“引用”和“转交”到多个项目组成部分。命令层面，它指向 `package.json` 中定义的脚本，例如 `dev` 对应 `scripts/dev.ts`，`dev:inspect` 对应 `scripts/dev-debug.ts`，`build` 对应 `build.ts`，`docs:dev` 对应 Mintlify 文档服务。功能文档层面，它指向 `docs/features/` 下的一组专题文档，例如 Remote Control、ACP、Computer Use、Chrome Use、Voice Mode、Web Search 等。运行入口层面，它描述安装包暴露的 bin：`ccb`、`ccb-bun`、`claude-code-best`，这些在 `package.json` 中分别映射到 `dist/cli-node.js`、`dist/cli-bun.js` 等构建产物。

## 核心流程

阅读这个文件的核心路径是从“认识项目”到“跑起来”再到“深入开发”。开头先用徽章和项目简介建立项目可信度与目标：这是一个复现 Claude Code CLI 工程能力的开源项目。随后用特性表把差异化能力集中展示，让读者快速判断是否需要群控、ACP、远程控制、监控、兼容模型供应商等能力。接着提供两条启动路线：安装版适合直接使用，源码版适合开发和调试。源码版流程先要求安装或升级 Bun，再进入仓库根目录执行 `bun install`，开发时运行 `bun run dev`，构建时运行 `bun run build`。首次进入 REPL 后，文档引导用户通过 `/login` 配置 Anthropic Compatible、OpenAI 或 Gemini 等服务。后续章节再补充 Feature Flags、VS Code attach 调试和 `/teach-me` 学习入口，形成从使用到贡献的完整引导。

## 关键函数的高层作用

`README.md` 本身没有函数、类或模块导出，因此这里的“关键函数”应理解为它强调的关键命令入口。`bun run dev` 是源码开发主入口，根据项目脚本会进入 `scripts/dev.ts` 并注入开发期宏定义与 feature 默认值。`bun run build` 是生产构建入口，执行 `build.ts`，README 明确说明它使用 code splitting 并输出到 `dist/`。`bun run dev:inspect` 是调试入口，通过 Bun inspect 服务让 VS Code 以 attach 模式连接 TUI 进程。`/login` 是运行时配置模型供应商的用户入口，用于写入 API 地址、密钥和模型映射。`/teach-me` 是学习型技能入口，用问答方式帮助理解架构或模块。`FEATURE_<FLAG_NAME>=1` 不是函数，但它是 README 暴露的重要控制面，用于让读者理解功能开关的启用方式。

## 修改风险

修改 `README.md` 的直接运行风险较低，因为它不参与编译和运行；真正风险来自信息不一致。第一，命令与 `package.json` 脚本不一致会误导新贡献者，例如 `bun run build`、`bun run dev:inspect`、`docs:dev` 的脚本名变更后必须同步。第二，安装版说明必须和 `package.json` 的 `bin`、发布产物、npm 包名保持一致，否则用户安装后找不到命令。第三，Feature Flags 说明必须和 `build.ts`、`scripts/dev.ts`、`docs/features/` 保持同步，否则用户会误判某功能是否默认可用。第四，外部链接和徽章容易失效；在对外发布或镜像环境中，还要注意不要暴露不希望出现的真实服务地址。第五，语气和项目定位变化会影响社区预期，尤其是“逆向还原”“企业版能力”“无需官方账号”等表述，修改时应确认法律、合规和维护边界。第六，文档中版本、Bun 最低版本、构建产物数量等信息具有时效性，代码或构建系统演进后应及时校准。
