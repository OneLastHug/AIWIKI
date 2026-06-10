# 目录：examples

## 它负责什么

`examples` 是 AionUi 仓库里的扩展样例集合，用来展示 AionUi 扩展系统的不同能力组合。它不是主应用源码，也不是通用运行时库，而是一组可被主应用或测试流程加载的示例扩展包。根据当前片段推断，扩展包的最小组织单元是一个目录，每个扩展目录通常以 `aion-extension.json` 作为描述入口，再通过 `contributes`、`channels`、`settings`、`skills`、`themes`、`assistants`、`agents`、`assets` 等子目录声明具体能力。

这个目录的价值主要有三类：第一，给开发者提供扩展包结构参考；第二，覆盖端到端测试场景，例如 `e2e-full-extension`；第三，提供真实集成样例，例如飞书、企业微信机器人、Star Office 等外部或业务型扩展。学习这里时应把它理解为“扩展协议样板库”，而不是核心业务代码入口。

## 直接子目录地图

`examples/acp-adapter-extension` 是一个较轻量的 ACP adapter 示例。当前片段显示它包含 `aion-extension.json` 和 `assets/codebuddy.svg`，重点应在扩展元信息与图标资产上。根据当前片段推断，它用于说明如何声明一个和 ACP adapter 相关的扩展，但具体能力配置可能主要写在 manifest 中。

`examples/e2e-full-extension` 是覆盖面最完整的端到端扩展示例。它包含 `channels`、`contributes`、`assistants`、`settings`、`skills`、`themes`、`i18n`、`assets` 等目录，适合作为理解扩展能力总览的主样本。它的命名也表明该扩展可能服务于自动化测试，验证扩展加载、贡献点、主题、设置页、多语言、技能和通道等功能是否能串起来。

`examples/ext-feishu` 是飞书相关扩展示例。它包含 `channels/ext-feishu-channel.js` 和 `webui/collector.js`，说明它不仅有扩展声明，还包含一个通信通道脚本和 Web UI 侧脚本。根据当前片段推断，它用于展示外部服务消息收集、通道桥接或网页侧采集逻辑。

`examples/ext-wecom-bot` 是企业微信机器人扩展示例。它比 `ext-feishu` 更完整，除了 `channels`、`webui`、`assets`、`aion-extension.json` 外，还有 `README.md` 与 `dist` 目录。`dist` 下保留构建后产物结构，如 `dist/channels`、`dist/webui`、`dist/assets`。学习时应区分源文件与分发产物，优先读源目录，再用 `dist` 对照最终打包形态。

`examples/hello-world-extension` 是最适合入门的综合样例。它包含 `agents`、`assistants`、`contributes`、`settings`、`skills`、`themes`、`scripts`、`i18n`、`assets` 等目录，几乎覆盖扩展常见能力，但命名和内容更偏教学。这里的 `scripts/activate.js`、`scripts/deactivate.js` 很可能展示扩展生命周期钩子。

`examples/star-office-extension` 是一个面向 Star Office 场景的设置页样例。它包含 `contributes/settings-tabs.json`、`settings/star-office.html`、`settings/star-office.css`、`settings/star-office.js` 和图标资产。根据当前片段推断，它重点展示“扩展贡献设置页”以及设置页前端资源如何组织。

## 关键入口

每个扩展目录下的 `aion-extension.json` 是最关键入口。它承担类似扩展 manifest 的角色，通常负责描述扩展身份、名称、版本、图标、贡献点、脚本、设置页或其他扩展能力。阅读任何一个样例时，都应先从该文件开始，而不是直接跳到某个 `.js` 或 `.html`。

`contributes` 是第二层入口，用来承载扩展对宿主应用的贡献声明。当前片段里可以看到 `hello-world-extension/contributes/agents.json`、`assistants.json`、`skills.json`、`themes.json`、`settings-tabs.json`、`mcp-servers.json`、`acp-adapters.json`，以及其他样例里的 `settings-tabs.json`。这些文件大概率是 manifest 中引用或由扩展加载器扫描的贡献点清单。

`channels` 是消息或集成通道入口，例如 `e2e-full-extension/channels/test-channel.js`、`ext-feishu/channels/ext-feishu-channel.js`、`ext-wecom-bot/channels/ext-wecom-bot-channel.js`。如果目标是理解扩展如何与外部服务或宿主通信，应该从这些文件切入。

`settings` 是设置页入口，常见组合是 `.html`、`.js`、`.css`。例如 `hello-world-extension/settings/hello-settings.html`、`e2e-full-extension/settings/e2e-settings.html`、`star-office-extension/settings/star-office.html`。设置页是否暴露给宿主，通常还要回到 `contributes/settings-tabs.json` 查声明关系。

`scripts` 是生命周期脚本入口，目前主要出现在 `hello-world-extension/scripts/activate.js` 和 `hello-world-extension/scripts/deactivate.js`。根据当前片段推断，它们用于演示扩展启用与停用时的执行点。

## 主流程位置

扩展加载主流程可以按“声明到实现”的方向理解：先读取扩展根目录的 `aion-extension.json`，确认扩展基本信息和能力声明；再进入 `contributes` 读取具体贡献点；随后宿主按贡献点加载对应资源，例如 settings tab 指向 `settings` 下的 HTML 页面，theme 贡献指向 `themes` 下的 CSS，skill 贡献指向 `skills` 下的 Markdown，assistant 或 agent 贡献指向对应上下文文件，channel 贡献则进入 `channels` 下的 JavaScript。

`hello-world-extension` 展示的是最完整的日常开发主流程：manifest 声明扩展，`contributes` 分拆不同能力，`scripts` 提供生命周期，`settings` 提供配置界面，`skills`、`assistants`、`agents` 提供 AI 行为上下文，`themes` 和 `assets` 提供视觉资源，`i18n` 提供多语言文本。

`e2e-full-extension` 的主流程更偏测试验证：它把通道、设置页、主题、技能、多语言等组合在一个扩展中，用来证明宿主扩展系统能完整识别和加载这些能力。阅读时不必把每个叶子文件都当成业务逻辑，重点看它覆盖了哪些扩展协议面。

`ext-feishu` 与 `ext-wecom-bot` 的主流程更偏外部集成：manifest 声明扩展，`channels` 负责通道逻辑，`webui` 负责网页侧交互或 webhook 相关逻辑，`assets` 提供扩展展示资源。`ext-wecom-bot/dist` 则像是构建输出，用来观察发布包结构。

## 推荐阅读顺序

1. 先读 `examples/hello-world-extension/aion-extension.json`，建立扩展包的整体概念。
2. 再读 `examples/hello-world-extension/contributes`，理解 agents、assistants、skills、themes、settings-tabs、mcp-servers、acp-adapters 这些贡献点如何拆分。
3. 接着看 `examples/hello-world-extension/scripts/activate.js`、`examples/hello-world-extension/scripts/deactivate.js`，理解生命周期入口。
4. 然后横向比较 `examples/e2e-full-extension`，重点看它比 hello world 多覆盖或更测试化的部分，例如 `channels/test-channel.js`、`settings/e2e-settings.html`、`themes`、`i18n`。
5. 如果关注外部平台集成，再看 `examples/ext-feishu` 和 `examples/ext-wecom-bot`，尤其是 `channels` 与 `webui` 的配合。
6. 最后看 `examples/star-office-extension`，把它作为设置页型扩展的较小样本来理解。

## 常见误区

不要把 `examples` 当成生产主流程入口。主应用的运行逻辑应在 `packages` 等目录中寻找，`examples` 主要是扩展样例、测试样例和集成参考。

不要只看 `.js` 文件就判断扩展行为。扩展能力通常先由 `aion-extension.json` 和 `contributes/*.json` 声明，再由脚本、页面、主题或 Markdown 文件实现。跳过声明层会看不清资源为何被加载。

不要把 `dist` 和源目录混为一谈。`examples/ext-wecom-bot/dist` 看起来是构建产物，适合用来对照发布形态，但学习实现应优先看 `examples/ext-wecom-bot/channels`、`examples/ext-wecom-bot/webui` 等源路径。

不要逐个叶子文件死读。这个目录的重点是扩展结构和贡献点地图：manifest、contributes、channels、settings、skills、themes、i18n、assets 之间的关系，比单个 SVG、单个语言文件或单个 Markdown 内容更重要。

不要忽略 `i18n`。多个样例都包含 `i18n/en-US`、`i18n/zh-CN`、`i18n/zh-TW`、`i18n/ja-JP`、`i18n/ko-KR`、`i18n/ru-RU`、`i18n/tr-TR` 等语言目录，说明扩展示例也遵循多语言组织方式。涉及用户可见文本时，应从贡献声明和对应语言资源一起理解。
