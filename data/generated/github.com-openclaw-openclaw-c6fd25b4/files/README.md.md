# 文件：README.md

## 一句话定位

`README.md` 是 OpenClaw 仓库的入口级产品与开发者导览文档：它面向首次访问仓库的用户、安装者、贡献者和维护者，概括 OpenClaw 是什么、如何安装启动、默认安全边界、主要能力、源码开发流程以及后续文档入口。

## 它暴露/定义了什么

这个文件不定义运行时代码或 API，而是定义仓库对外的第一层叙事和操作约定。核心暴露内容包括：OpenClaw 的产品定位是运行在用户自有设备上的 personal AI assistant；Gateway 是控制平面，不是产品本身；支持的 channel 列表覆盖 WhatsApp、Telegram、Slack、Discord、Signal、iMessage 等大量消息入口；推荐安装路径是全局安装 `openclaw@latest` 后运行 `openclaw onboard --install-daemon`；运行时要求是 Node 24 推荐或 Node 22.19+；源码开发使用 `pnpm` workspace，不支持在仓库根目录用普通 `npm install` 作为源码环境。

它还暴露几类关键用户契约：DM 默认安全策略、pairing 审批流程、`openclaw doctor` 风险检查、stable/beta/dev 发布渠道、agent workspace 和 skills 文件布局、最小配置文件形态，以及贡献入口 `CONTRIBUTING.md`。这些不是实现逻辑，但会影响用户预期和维护者判断。

## 谁调用它

`README.md` 不是被代码调用，而是被多个外部和内部场景“消费”。GitHub 仓库首页会渲染它；npm 包元数据中 `homepage` 指向仓库 README，且 `package.json` 的 `files` 明确包含 `README.md`，因此发布包也会携带它；新用户会通过它进入安装、getting started、updating、安全、配置和 channel 文档；贡献者会从它跳转到 `CONTRIBUTING.md` 和源码开发流程；维护者在发布、安装说明、安全默认值、channel 支持范围变化时也会以它作为对外入口的一致性检查面。

## 它调用谁

作为 Markdown 文档，它主要“调用”三类资源。第一类是本仓库资源，如 `VISION.md`、`CONTRIBUTING.md`、`LICENSE`、`docs/assets/...`、`docs/assets/sponsors/...`。第二类是 OpenClaw 文档站的主题页，原文中包括 getting started、updating、onboarding、models、security、configuration、channels、gateway、sandboxing、apps、tools、skills、architecture、logging 等入口；这里不展开真实网址。第三类是 CLI 命令和配置契约，包括 `openclaw onboard`、`openclaw gateway status`、`openclaw gateway --port 18789 --verbose`、`openclaw message send`、`openclaw agent`、`openclaw pairing approve`、`openclaw doctor`、`openclaw update --channel stable|beta|dev`、`pnpm openclaw setup`、`pnpm gateway:watch`、`pnpm build`、`pnpm ui:build`。

根据 `package.json` 推断，README 中的安装与开发命令最终会落到 npm 包暴露的 `openclaw` bin，即 `openclaw.mjs`，以及构建产物 `dist/index.js`、plugin SDK exports、`extensions/*` 开发期插件加载机制。

## 核心流程

README 的核心阅读流程是从“产品是什么”进入“如何跑起来”。开头先用品牌、徽章和简短描述建立定位：OpenClaw 是本地优先、多 channel、单用户导向的 AI assistant。随后给出推荐新装流程：安装全局 CLI，运行 `openclaw onboard --install-daemon`，让 Onboard 引导设置 gateway、workspace、channels 和 skills，并把 Gateway 安装成 daemon。

第二段流程是快速启动与验证：用户先启动 daemon 或以前台 debug 模式启动 Gateway，再用 `openclaw message send` 或 `openclaw agent --message ...` 触发一次消息/agent 调用，确认控制平面和 channel/agent 能工作。

第三段流程是安全建模：README 明确把真实消息入口视为不可信输入，强调默认 DM pairing 策略、allowlist、公开 DM 显式 opt-in、sandbox 模式和 `openclaw doctor`。这部分把“能连很多 channel”与“默认不能随便处理陌生人输入”绑定在一起，是仓库对外最重要的安全预期之一。

第四段流程是开发者路径：源码 checkout 必须用 `pnpm install`，首次运行 `pnpm openclaw setup`，需要 Control UI 时运行 `pnpm ui:build`，日常开发用 `pnpm gateway:watch`。README 还区分 TypeScript 直跑、`dist/` 构建和 UI 构建产物，避免贡献者误以为所有命令都自动重建所有表面。

## 关键函数的高层作用

本文件没有函数、类或模块导出。可以把其中的关键“操作入口”视为文档级流程节点：`openclaw onboard --install-daemon` 负责推荐安装和初始设置；`openclaw gateway status` 负责确认 Gateway daemon 状态；`openclaw gateway --port 18789 --verbose` 负责前台调试；`openclaw message send` 负责验证 outbound message；`openclaw agent --message` 负责验证 assistant 调用；`openclaw pairing approve` 负责把未知 DM sender 通过 pairing 变为允许对象；`openclaw doctor` 负责检查配置和安全风险；`pnpm gateway:watch` 负责源码开发循环；`pnpm build` 和 `pnpm ui:build` 分别负责 runtime/package 构建和 Control UI 构建。

辅助内容如 sponsors、star history、community 和 clawtributors 墙主要承担展示、归因和社区入口作用，不影响运行时流程。

## 修改风险

修改 `README.md` 的最大风险不是编译失败，而是用户契约漂移。安装命令、Node 版本、package manager 说明、daemon 行为、channel 列表、DM 默认策略、sandbox 默认描述、配置键名、发布渠道和源码开发命令都必须与 `package.json`、CLI 实现、docs 目录和当前发布状态一致。尤其是安全默认值，如果 README 写得比实际行为更开放或更收紧，都会误导用户暴露真实 messaging surface。

第二类风险是 docs IA 和链接漂移。README 是入口页，任何 docs 路径变化都需要同步这里；但按本任务要求不输出真实网址。第三类风险是“extensions”措辞：仓库规则要求面向用户使用 plugin/plugins，`extensions/` 是内部目录概念，所以用户可见段落不应把实现目录名当产品概念。第四类风险是发布包风险：`package.json` 发布文件包含 `README.md`，所以 README 的错误会随 npm 包传播。第五类风险是长 contributors 区块和自动生成区块，手工编辑容易破坏生成标记，应避免在 `clawtributors:start/end` 和 hidden 区域内做无关改动。
