# 目录：docs/.i18n

## 它负责什么

`docs/.i18n` 是 OpenClaw 文档国际化的源端辅助目录，不是完整的多语言文档目录。根据 `docs/AGENTS.md` 的规则，当前仓库只维护英文文档与 glossary 文件，外语正文不在这个仓库维护；生成后的多语言发布产物位于独立的 publish repo。也就是说，`docs/.i18n` 的核心职责是给翻译流水线提供“固定术语、导航标签、翻译流程说明”等控制材料，而不是存放 `docs/zh-CN/**`、`docs/fr/**` 这类成套译文页面。

从当前目录结构看，`docs/.i18n` 下面没有直接子目录，全部是少量 Markdown 与 JSON 文件。它更像一个国际化配置与协作说明层：`glossary.<locale>.json` 约束特定语言的术语译法，`*-navigation.json` 约束导航文案或导航结构相关翻译，`README.md` 与 `translation-workflow.md` 负责解释维护流程。根据 `docs/AGENTS.md`，英文文档更新后，需要按需更新这里的 glossary，然后由 publish repo 的同步与 `scripts/docs-i18n` 流水线生成外语输出；翻译记忆则是 publish repo 中生成的 `docs/.i18n/*.tm.jsonl`，不是这里的主要维护对象。

## 直接子目录地图

这个目标目录没有直接子目录。可以按文件族来理解它的“地图”：

`docs/.i18n/README.md` 是目录说明入口。根据当前片段推断，它用于解释这个目录内哪些文件应人工维护、哪些由翻译流水线消费，依据是 `docs/AGENTS.md` 明确写到“See `docs/.i18n/README.md`”。

`docs/.i18n/translation-workflow.md` 是翻译协作流程入口。根据文件名和上层规则推断，它应说明从英文源文档、术语表、publish repo 到生成译文之间的操作顺序。

`docs/.i18n/glossary.*.json` 是各 locale 的术语表，例如 `glossary.zh-CN.json`、`glossary.zh-TW.json`、`glossary.ja-JP.json`、`glossary.pt-BR.json` 等。它们用于固定产品名、技术名词、短标签、页面标题等不能自由翻译或必须统一翻译的词。`scripts/check-docs-i18n-glossary.mjs` 当前只直接检查 `docs/.i18n/glossary.zh-CN.json`，说明中文简体 glossary 是英文文档变更检查中的关键样本或当前强制覆盖对象。

`docs/.i18n/*-navigation.json` 是导航翻译相关文件，例如 `zh-Hans-navigation.json`、`pt-BR-navigation.json`、`ja-navigation.json`、`fr-navigation.json`、`de-navigation.json` 等。它们看起来不承载正文翻译，而是服务文档站点导航、短标题或语言选择可见标签。

## 关键入口

维护者首先应看 `docs/AGENTS.md` 的 “Docs i18n” 小节，因为它定义了本目录的边界：外语文档不在当前仓库维护，不要新增或编辑 `docs/<locale>/**`；英文文档与 glossary 是当前仓库的事实源头；publish repo 才运行最终的翻译生成流程。

目录内入口是 `docs/.i18n/README.md`。它是理解本目录文件约定的第一站，尤其适合确认哪些 JSON 是手写维护，哪些是流水线输入或输出。由于当前任务只做 overview，没有逐行读取该文件，关于其详细字段规则应以文件正文为准。

流程入口是 `docs/.i18n/translation-workflow.md`。它应连接术语表更新、翻译生成、人工审阅和 publish repo 产物之间的操作顺序。根据上层规则，真实生成动作不在当前 repo 的 `docs` 目录完成，而是在 publish repo 中通过 `scripts/docs-i18n` 执行。

校验入口是 `package.json` 中的 `docs:check-i18n-glossary`，其命令指向 `node scripts/check-docs-i18n-glossary.mjs`。完整 docs 检查 `check:docs` 会串联格式、lint、MDX、i18n glossary 和链接检查，其中 i18n glossary 检查是文档国际化质量门之一。

## 主流程位置

主流程可以概括为：英文源文档变更 -> 更新 `docs/.i18n/glossary.<locale>.json` 中必要术语 -> 运行或等待 docs 检查 -> 同步到 publish repo -> 在 publish repo 中运行 `scripts/docs-i18n` 生成外语文档与翻译记忆 -> 发布文档站点。

在当前仓库内，源头是 `docs/**` 的英文文档，规则层是 `docs/AGENTS.md`，术语与导航控制层是 `docs/.i18n/**`，本地检查层是 `scripts/check-docs-i18n-glossary.mjs` 与 `package.json` 的 `docs:check-i18n-glossary`。发布触发层可从 `.github/workflows/docs-translate-trigger-release.yml` 看起；根据文件名和搜索片段，它负责向 publish repo 触发翻译协调事件。根据当前片段推断，真正把英文页面复制、翻译、写入各 locale 页面、维护 translation memory 的脚本位于 publish repo，而不是当前仓库。

需要特别区分 docs i18n 与 Control UI i18n。`ui/src/i18n/**`、`scripts/control-ui-i18n.ts`、`.github/workflows/control-ui-locale-refresh.yml` 属于 Web Control UI 的运行时界面翻译；`docs/.i18n` 只服务文档站点翻译。两条线支持的 locale 集合可能相近，但文件位置、校验命令、生成产物和维护责任不同。

## 推荐阅读顺序

1. 先读 `docs/AGENTS.md`，只看 “Mintlify Rules” 与 “Docs i18n”。这一步建立边界：当前 repo 不维护外语正文，链接规则也要服从 Mintlify 的 root-relative 约定。

2. 再读 `docs/.i18n/README.md`，确认目录内文件的人工维护规则、命名约定和哪些文件是翻译流水线输入。

3. 接着读 `docs/.i18n/translation-workflow.md`，把术语表、导航翻译、publish repo、生成脚本之间的顺序串起来。

4. 然后看一个主目标 locale 的 glossary，例如 `docs/.i18n/glossary.zh-CN.json`。如果处理的是其他语言，再对照对应的 `glossary.<locale>.json`，不要直接从中文推导所有语言规则。

5. 最后看 `scripts/check-docs-i18n-glossary.mjs` 与 `package.json` 里的 `docs:check-i18n-glossary`、`check:docs`，理解 CI 或本地检查如何发现新增英文标题、短标签缺少 glossary 覆盖。

## 常见误区

第一，把 `docs/.i18n` 当成外语文档目录。这里不是 `docs/zh-CN` 或 `docs/fr` 的替代品，也不应该在当前仓库新增成套 locale 页面。上层规则明确说外语文档由 publish repo 生成并维护。

第二，直接手改生成产物。`docs/AGENTS.md` 提到 translation memory 位于 publish repo 的生成 `docs/.i18n/*.tm.jsonl` 文件；当前目录中的 glossary 才是应优先维护的术语源。若某个译法不稳定，通常应加 glossary，而不是在生成译文里反复修补。

第三，混淆 docs i18n 和 UI i18n。`docs/.i18n` 的变化不等于 `ui/src/i18n/locales/*.ts` 的变化；`pnpm docs:check-i18n-glossary` 与 `pnpm ui:i18n:check` 也不是同一条校验线。

第四，只改英文文档标题或导航短标签，却忘记 glossary。`scripts/check-docs-i18n-glossary.mjs` 会针对变更的英文 doc labels 检查 `docs/.i18n/glossary.zh-CN.json` 是否缺项；新增技术术语、页面标题、短导航名时，应同步考虑 glossary。

第五，认为 `*-navigation.json` 是完整导航定义。根据当前片段推断，它们更像导航翻译辅助文件，而不是 docs 站点主导航源；主导航与页面组织还应去 `docs` 的站点配置或 publish repo 配置中确认。

第六，把本仓库的英文 docs 同 publish repo 的生成译文做双向编辑。正确心智模型是单向：当前仓库英文文档和 glossary 是源，publish repo 生成多语言输出。若译文质量需要改，优先回到 glossary、英文源表达或翻译流程配置中修正。
