# 目录：examples/hello-world-extension

## 它可能负责什么
这个目录包含 39 个被抽样展示的文件。请从文件命名、子目录和关键源码入手理解它在项目中的职责。

## 文件列表节选
```text
examples/hello-world-extension/aion-extension.json
examples/hello-world-extension/scripts/activate.js
examples/hello-world-extension/scripts/deactivate.js
examples/hello-world-extension/settings/hello-settings.html
examples/hello-world-extension/contributes/skills.json
examples/hello-world-extension/contributes/assistants.json
examples/hello-world-extension/contributes/themes.json
examples/hello-world-extension/contributes/mcp-servers.json
examples/hello-world-extension/contributes/settings-tabs.json
examples/hello-world-extension/contributes/agents.json
examples/hello-world-extension/contributes/acp-adapters.json
examples/hello-world-extension/themes/sunset-glow.css
examples/hello-world-extension/themes/ocean-breeze.css
examples/hello-world-extension/assistants/hello-assistant-context.md
examples/hello-world-extension/assets/sunset-glow-cover.svg
examples/hello-world-extension/assets/ocean-breeze-cover.svg
examples/hello-world-extension/agents/hello-researcher-context.md
examples/hello-world-extension/agents/hello-coder-context.md
examples/hello-world-extension/skills/quick-summary.md
examples/hello-world-extension/skills/issue-breakdown.md
examples/hello-world-extension/i18n/zh-CN/assistants.json
examples/hello-world-extension/i18n/zh-CN/themes.json
examples/hello-world-extension/i18n/zh-CN/settings.json
examples/hello-world-extension/i18n/zh-CN/agents.json
examples/hello-world-extension/i18n/zh-CN/extension.json
examples/hello-world-extension/i18n/ko-KR/extension.json
examples/hello-world-extension/i18n/ja-JP/extension.json
examples/hello-world-extension/i18n/en-US/assistants.json
examples/hello-world-extension/i18n/en-US/themes.json
examples/hello-world-extension/i18n/en-US/settings.json
examples/hello-world-extension/i18n/en-US/agents.json
examples/hello-world-extension/i18n/en-US/extension.json
examples/hello-world-extension/i18n/tr-TR/extension.json
examples/hello-world-extension/i18n/zh-TW/extension.json
examples/hello-world-extension/i18n/ru-RU/assistants.json
examples/hello-world-extension/i18n/ru-RU/themes.json
examples/hello-world-extension/i18n/ru-RU/settings.json
examples/hello-world-extension/i18n/ru-RU/agents.json
examples/hello-world-extension/i18n/ru-RU/extension.json
```

## 小白阅读建议
- 先看项目说明、`index` 入口、路由、业务服务、类型/结构定义等文件。英文文件名只是代码命名，不要求先理解英文语义。
- 暂时跳过构建产物、测试快照和重复样板。
- 如果这里是业务目录，优先找“谁调用它”和“它调用谁”。
