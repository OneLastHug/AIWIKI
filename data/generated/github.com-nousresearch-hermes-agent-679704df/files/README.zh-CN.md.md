# 文件：README.zh-CN.md

## 一句话定位

`README.zh-CN.md` 是仓库根目录的简体中文入口文档，用来向中文用户概览 Hermes Agent 的定位、安装方式、核心能力、常用命令、迁移路径、贡献方式和社区入口；它不是运行时代码，而是项目对外展示与新用户引导的一层本地化文档。

## 它暴露/定义了什么

这个文件主要定义了中文版本的项目首页内容。它暴露给读者的信息包括：Hermes Agent 是一个具备记忆、技能自改进、跨平台消息网关、定时任务、终端后端和研究轨迹能力的 AI agent；如何快速安装和启动；如何通过 `hermes model`、`hermes tools`、`hermes setup`、`hermes gateway` 等命令完成初始配置；如何使用 Nous Portal 简化模型与工具 API Key 配置；CLI 与消息平台中的常用斜杠命令；从 OpenClaw 迁移到 Hermes 的命令；贡献者如何本地安装开发环境。

它还定义了语言切换入口：文件顶部 badge 指向 `README.md`，对应英文 README 中指向 `README.zh-CN.md` 的中文入口。因此它承担的是“中文 README 镜像”的角色，而不是独立的产品规格源。

## 谁调用它

严格来说，没有业务代码调用 `README.zh-CN.md`。根据当前片段推断，它的直接消费者是 GitHub 或类似代码托管平台的 Markdown 渲染器、中文用户、贡献者，以及从英文 `README.md` 点击语言切换 badge 的读者。依据是仓库搜索结果中只有 `README.md` 明确引用 `README.zh-CN.md`，而 `pyproject.toml` 的 `readme` 字段仍指向 `README.md`，说明 Python 包元数据不会使用这个中文文件作为项目说明。

测试层面也没有直接保护该中文文件。现有 Windows 安装文档一致性测试读取的是 `README.md`，检查英文 README 不再声明原生 Windows 不支持，并确认它提到 `install.ps1`。这意味着中文 README 的同步质量更依赖人工维护或翻译流程，而不是自动化测试。

## 它调用谁

作为 Markdown 文件，它不会执行函数或导入模块。但它在内容层面“指向”多个项目能力和入口：安装脚本对应 `scripts/install.sh`，开发安装路径涉及 `setup-hermes.sh`、`pyproject.toml` 中的依赖与 extras，运行入口是安装后的 `hermes` 命令；模型与配置相关入口会落到 CLI、配置加载器和 provider 插件体系；消息平台入口会落到 `gateway/`；OpenClaw 迁移入口会落到 `hermes claw migrate` 对应的迁移命令；技能相关内容会落到 `skills/`、`optional-skills/` 和技能 Hub 机制。

文档中还引用了外部服务、文档站、社区和第三方平台，但这些只是超链接或文字说明，不构成代码依赖。维护时应把它们视为用户路径的一部分，而不是运行时调用链。

## 核心流程

这个文件的阅读流程是典型的新用户漏斗。开头先用 banner、项目名、badge 和一句定位建立品牌与语言入口；随后用两段文字解释 Hermes 的核心价值：自改进、跨会话记忆、任意模型接入、可在本地或云端运行。紧接着的表格把产品能力拆成终端界面、消息平台、闭环学习、定时自动化、委派并行、终端后端和研究用途。

中段进入操作路径：先给出快速安装，再列出安装后的基础命令，然后介绍 Nous Portal 作为低摩擦配置路径。之后的 CLI 与消息平台对照表把 `/new`、`/model`、`/personality`、`/retry`、`/compress`、`/skills` 等命令映射到两类入口，帮助用户理解同一 agent 能通过终端和网关复用会话能力。

后段转向文档导航、OpenClaw 迁移、贡献者开发安装、社区和许可证。整体上，它不是 API 参考，而是“从认识项目到能跑起来，再到知道去哪里深入”的中文索引页。

## 关键函数的高层作用

这个文件没有 Python、TypeScript 或 shell 函数，因此不存在可逐个解释的关键函数。若把文档中出现的命令视为用户可触发的功能入口，核心入口可以这样理解：`hermes` 启动交互式 CLI/TUI；`hermes model` 选择模型提供商和模型；`hermes tools` 配置工具启用状态；`hermes config set` 写入单项配置；`hermes gateway` 启动或配置消息平台网关；`hermes setup` 运行综合设置向导；`hermes setup --portal` 走 Nous Portal OAuth 和 Tool Gateway 配置；`hermes claw migrate` 迁移 OpenClaw 数据；`hermes update` 更新安装；`hermes doctor` 做诊断检查。

这些命令背后的实现分散在 CLI、配置、provider、gateway、迁移和工具系统中，README 只承担发现和引导职责，不承诺具体内部实现细节。

## 修改风险

最大风险是与英文 `README.md`、安装脚本和真实 CLI 行为发生漂移。当前中文文件已经能看出这类风险：英文 README 包含原生 Windows PowerShell 安装的早期 beta 说明和 `install.ps1` 路径，而中文 README 仍写“原生 Windows 不受支持”；英文 README 提到 NovitaAI，中文模型列表未同步；英文贡献者手动安装使用 `.venv` 和 `scripts/run_tests.sh`，中文版本仍出现 `venv` 和直接 `python -m pytest tests/ -q`。这些差异会误导中文用户，尤其是安装路径和平台支持这类高影响信息。

第二类风险是链接和外部服务名称失效。虽然本文档只是 Markdown，但它包含大量外部文档、服务、社区和 badge 引用；如果维护时只更新英文 README，中文入口会变成过期索引。

第三类风险是营销描述与实际能力不一致。README 会被新用户和贡献者首先看到，像“支持任意模型”“40+ 工具”“六种终端后端”“迁移内容”等表述需要跟 `toolsets.py`、provider 插件、`gateway/`、`scripts/`、文档站保持一致。修改时建议以 `README.md` 为上游源同步翻译，并额外检查安装脚本、测试中对 README 的断言、`pyproject.toml` 的项目描述和文档站首页，避免中文页面成为单独分叉的产品说明。
