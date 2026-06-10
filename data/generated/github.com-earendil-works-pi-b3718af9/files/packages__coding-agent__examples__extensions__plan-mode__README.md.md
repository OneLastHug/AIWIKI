# 文件：packages/coding-agent/examples/extensions/plan-mode/README.md

## 一句话定位

`packages/coding-agent/examples/extensions/plan-mode/README.md` 是 `coding-agent` 扩展示例中 “plan mode” 的说明页，面向想学习或复用扩展机制的开发者，解释如何通过一个示例 extension 给 agent 增加计划模式相关能力。

## 它暴露/定义了什么

这个文件本身是 Markdown 文档，不是运行时代码；它不导出 TypeScript 函数、类或类型，也不会被 `coding-agent` 在执行任务时直接加载。它“定义”的主要是示例的使用约定：plan-mode extension 的目的、如何安装或启用、如何触发计划模式、以及该示例与扩展 API 的关系。

根据当前片段推断，这个 README 所属目录通常会同时包含扩展清单、入口脚本或示例实现文件。README 的职责是把这些文件组织成可理解的学习路径：用户先读说明，再查看 extension 的 manifest/entry，再运行示例验证行为。

它对仓库的价值不在于提供业务逻辑，而在于作为扩展系统的参考实现文档。对于贡献者来说，它说明“一个 plan-mode 扩展应该长什么样”；对于使用者来说，它说明“怎样把该扩展接入 `pi` 或 `coding-agent` 的运行环境”。

## 谁调用它

没有代码调用这个 README。它的直接消费者是人：阅读 examples 的开发者、维护扩展系统的贡献者、以及需要验证 plan mode 行为的测试或文档作者。

间接上，它会被文档索引、包发布内容、GitHub 文件浏览器或示例目录引用。若仓库有 examples 汇总页或 npm 包包含该目录，则用户可能从这些入口进入本文件。

运行时链路中，真正被 `coding-agent` 调用的应是同目录下的 extension 入口文件或 manifest 指向的模块，而不是 README。README 只解释这些文件如何组合。

## 它调用谁

README 不调用任何模块。它最多通过文字引用相邻文件、CLI 命令、extension API 名称或配置字段。

根据当前片段推断，它描述的 plan-mode 示例可能会依赖 `packages/coding-agent` 的扩展加载机制、工具注册机制、会话状态或计划模式相关 UI/交互能力。若文档中出现类似 extension manifest、hook、command、tool 或 prompt 配置，它们才是实际和核心系统发生关系的地方。

因此要区分两层关系：README 的“调用谁”为空；README 描述的示例实现，才会调用或被调用于 `coding-agent` 的 extension runtime。

## 核心流程

核心流程可以理解为四步。

第一，开发者阅读本 README，理解 plan-mode extension 的目标：它不是修改 agent 主流程，而是通过扩展机制给 agent 增加一种面向计划、确认、分解任务的交互方式。

第二，开发者按 README 指示启用该扩展。通常这会涉及把示例目录作为 extension 注册到本地配置，或通过 CLI 参数指向 extension 路径。具体命令应以 README 原文为准。

第三，`coding-agent` 启动时读取扩展配置，加载 plan-mode 示例的 manifest 和入口模块。此时扩展会把自己的能力挂接到 agent 可识别的扩展点上，例如命令、工具、模式切换、提示词片段或交互钩子。这里是运行时真正发生调用关系的位置。

第四，用户在会话中触发 plan mode。agent 根据扩展提供的规则进入计划优先的交互：先收集目标、拆解步骤、必要时向用户确认，再进入执行阶段。README 负责说明这个行为应该如何观察和验证。

## 关键函数的高层作用

本文件没有关键函数。它是文档页，核心“结构单元”是章节和示例命令，而不是代码符号。

如果同目录下存在 extension 入口函数，根据当前片段推断，其高层作用大概率是注册 plan-mode 行为：把 plan mode 的命令、提示词或 hook 暴露给 `coding-agent`。manifest 或配置文件则负责声明扩展名称、入口路径、权限或能力边界。辅助脚本如果存在，通常只用于本地演示或安装，不应承担核心运行逻辑。

阅读本 README 时，重点不是逐行理解 Markdown，而是抓住它对扩展边界的说明：哪些东西属于示例扩展自身，哪些东西由 `coding-agent` 框架提供，哪些行为需要用户在会话中触发。

## 修改风险

主要风险是文档与实现漂移。plan mode 这种示例文档通常会写 CLI 命令、目录结构、配置字段和交互预期；一旦扩展加载机制、manifest schema、命令名称或运行方式变化，README 如果不同步更新，就会误导使用者。

第二类风险是把示例说成正式 API。如果 README 的措辞过于绝对，用户可能误以为 plan-mode 示例代表稳定接口。修改时应明确它是 example，避免承诺未稳定的扩展点。

第三类风险是遗漏安全和权限边界。plan mode 涉及“先计划后执行”，如果文档没有说明何时只读、何时会执行命令、是否需要用户确认，就可能让使用者误判 agent 的行为范围。

第四类风险是路径和命令错误。这个文件位于 `packages/coding-agent/examples/extensions/plan-mode/README.md`，相对路径一旦写错，示例就很难被复现。修改 README 时应同时核对相邻 manifest、入口文件和 `packages/coding-agent` 的扩展加载代码，确保文档描述和实际可运行路径一致。
