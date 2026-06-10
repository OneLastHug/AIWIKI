# 文件：plugins/security-guidance/README.md

## 一句话定位

`plugins/security-guidance/README.md` 是 `security-guidance` 插件的使用与设计说明页，负责告诉开发者这个插件如何在文件写入工具结果中追加安全告警、覆盖哪些危险模式、如何启用、如何切换阻断模式，以及当前没有实现哪些更重的安全审查层。

## 它暴露/定义了什么

这个文件本身不暴露 Python API，也不参与运行时执行；它定义的是插件的高层契约和使用边界。核心信息包括：插件会在 agent 调用 `write_file`、`patch`、`skill_manage` 写入内容时，对新内容做本地模式匹配；命中危险模式后默认不阻止写入，而是把 `Security guidance` 警告追加到工具结果中，让模型在下一轮看到并修复或解释。

README 还定义了三个运行模式：默认 warn 模式、`SECURITY_GUIDANCE_BLOCK=1` 的阻断模式、`SECURITY_GUIDANCE_DISABLE=1` 的禁用模式。它列出 25 条规则分类，包括不安全反序列化、命令注入、代码注入、XSS sink、加密误用、XXE、供应链风险和 GitHub Actions 注入风险。文末说明 `patterns.py` 来源于 Anthropic 的插件规则集，`__init__.py`、`plugin.yaml`、README 和测试属于 Hermes 侧移植工作。

## 谁调用它

运行时没有代码“调用”这个 README。实际调用链是插件系统读取 `plugins/security-guidance/plugin.yaml` 和 `plugins/security-guidance/__init__.py`，而不是读取 README。README 的调用者主要是人：插件使用者、维护者、评审者，以及需要理解插件安全边界的开发者。

根据当前片段推断，用户通过 `hermes plugins enable security-guidance` 或在 `config.yaml` 的 `plugins.enabled` 中加入 `security-guidance` 启用插件；启用后由 `hermes_cli.plugins.PluginManager` 发现并加载该插件。依据是 `plugin.yaml` 声明了 `pre_tool_call`、`transform_tool_result` 两个 hook，`__init__.py` 的 `register(ctx)` 也注册了这两个 hook。

## 它调用谁

README 不调用任何模块。它描述的插件实现会调用或依赖这些内部对象：`plugins/security-guidance/__init__.py` 导入 `patterns.py` 中的 `SECURITY_PATTERNS`，预编译正则规则；通过 `ctx.register_hook()` 接入 Hermes 插件系统；运行时由 `model_tools.handle_function_call()` 在工具执行前后触发 `pre_tool_call` 与 `transform_tool_result`。

从职责上看，README 指向三层关系：文档页解释插件行为；`__init__.py` 实现扫描、格式化警告、hook 注册；`patterns.py` 提供规则数据和路径过滤函数。README 不涉及工具注册，因为这个插件不提供新工具，只增强已有文件写入工具的结果处理。

## 核心流程

启用插件后，`PluginManager` 加载 `security-guidance` 并执行 `register(ctx)`。当 agent 准备执行工具时，`model_tools.handle_function_call()` 先触发 `pre_tool_call`。如果设置了 `SECURITY_GUIDANCE_BLOCK=1`，插件会扫描工具参数里的待写入内容；一旦命中规则，就返回 `{"action": "block", "message": ...}`，工具不会继续执行，调用方收到错误结果。

默认 warn 模式下，`pre_tool_call` 不阻断。工具实际执行并完成写入后，`handle_function_call()` 触发 `transform_tool_result`。插件再次从参数中抽取路径和内容，按 `patterns.py` 的规则进行子串和正则匹配。如果命中且工具结果是字符串、不是简单错误 JSON，就把格式化后的安全提醒追加到原始结果末尾。这样文件已经写入，但模型下一轮会在 tool message 中看到警告，有机会自我修正。

扫描范围受到 `_TARGET_TOOLS` 和 `_MAX_SCAN_BYTES` 控制：只关注 `write_file`、`patch`、`skill_manage` 的内容字段；超过 256KB 的内容跳过，避免大文件扫描拖慢 agent loop。

## 关键函数的高层作用

README 自身没有函数。相关实现中，`register(ctx)` 是插件入口，把 `_on_pre_tool_call` 和 `_on_transform_tool_result` 注册到插件系统。

`_on_pre_tool_call()` 只在 block 模式承担策略执行：发现危险模式就拒绝本次写入。`_on_transform_tool_result()` 是默认模式的核心：在工具结果返回给模型前追加警告文本。`_scan_args()`、`_extract_path_and_content()`、`_scan_content()` 构成扫描管线，分别负责从工具参数取内容、应用路径过滤、执行子串和正则匹配。`_format_warning_block()` 只负责把命中规则渲染成模型可读的 Markdown 警告块。`_block_mode_enabled()` 和 `_plugin_disabled()` 是环境变量开关辅助函数。

## 修改风险

修改 README 的风险主要是文档与实现漂移。比如 README 写“25 rules”，但 `patterns.py` 规则数量变化后未同步，会误导使用者；新增或删除 `SECURITY_GUIDANCE_BLOCK`、`SECURITY_GUIDANCE_DISABLE` 行为后不更新 README，会让部署人员选错安全模式。

更高风险来自描述运行语义时过度承诺。这个插件默认是提示层，不是 SAST、依赖扫描、审计代理或提交门禁；如果 README 把它描述成“保证阻止漏洞”，会造成安全误用。反过来，如果实现从 warn 改成默认 block，也必须同步 README，因为这会改变 agent 写文件时的可用性和失败模式。

规则覆盖说明也要谨慎。`patterns.py` 使用正则和字面子串，存在误报和漏报；README 已明确 false-positive rate 一般但可接受。修改规则分类、路径过滤说明、授权来源或许可证段落时，需要同时核对 `patterns.py`、`LICENSE`、`NOTICE` 和 `plugin.yaml`，否则容易产生合规或维护风险。
