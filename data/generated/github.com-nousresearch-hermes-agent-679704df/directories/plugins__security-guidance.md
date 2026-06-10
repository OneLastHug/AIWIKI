# 目录：plugins/security-guidance

## 它负责什么

`plugins/security-guidance` 是 Hermes 的安全提示插件目录，职责是在 agent 写入代码内容时做一层本地、快速、基于规则的安全扫描。它不新增一个可被模型主动调用的工具，而是接入 Hermes 插件 hook：当 `write_file`、`patch`、`skill_manage` 等写入类工具准备或已经处理新内容时，插件扫描参数里的待写入文本，匹配到危险模式后给模型返回安全提醒。

默认行为是“警告而不阻断”：文件仍会写入，插件把 `Security guidance` 警告块追加到工具结果字符串中，下一轮模型能看到这段警告并自行修正或说明为何安全。若设置 `SECURITY_GUIDANCE_BLOCK=1`，它会在工具执行前通过 `pre_tool_call` 直接拒绝本次写入。若设置 `SECURITY_GUIDANCE_DISABLE=1`，插件加载后不执行扫描。这个目录代表的是“轻量安全护栏”，不是完整 SAST、依赖扫描、LLM 审计或渗透测试替代品。

## 直接子目录地图

当前 `plugins/security-guidance` 没有直接子目录，只有少量顶层文件：

`plugin.yaml` 是插件元数据和 hook 声明，说明插件名、版本、作者、描述，以及它注册 `transform_tool_result`、`pre_tool_call` 两类 hook。

`__init__.py` 是 Hermes 侧的实际入口，包含配置读取、规则预编译、工具参数提取、扫描、警告格式化、hook 回调和 `register(ctx)` 注册函数。

`patterns.py` 是安全规则数据集，包含 `SECURITY_PATTERNS`，每条规则定义 `ruleName`、`reminder`、可选 `regex`、`substrings`、`path_filter`、`path_check`。它尽量保持纯数据和无 I/O，便于独立导入。

`README.md` 是面向用户和维护者的说明，解释覆盖范围、启用方式、环境变量模式、限制和授权来源。

`LICENSE`、`NOTICE` 用于记录规则数据来源和授权。根据当前片段推断，规则数据来自外部项目的 Apache-2.0 授权拷贝，Hermes 侧的集成逻辑在本目录自己实现；依据是 `patterns.py` 顶部注释和 README 的授权说明。

## 关键入口

最关键的入口是 `plugins/security-guidance/__init__.py` 的 `register(ctx)`。插件系统加载该目录后会调用这个函数，函数内部执行：

`ctx.register_hook("pre_tool_call", _on_pre_tool_call)`

`ctx.register_hook("transform_tool_result", _on_transform_tool_result)`

`_on_pre_tool_call()` 负责阻断模式。默认情况下它直接返回 `None`，表示不干预工具执行；只有 `SECURITY_GUIDANCE_BLOCK` 开启时，它才调用 `_scan_args()` 扫描写入内容。如果发现命中项，则返回 `{"action": "block", "message": ...}`，由插件框架解释为拒绝工具调用。

`_on_transform_tool_result()` 负责默认警告模式。它在工具已经执行并产生结果后运行，重新扫描本次工具参数里的待写入内容。如果有命中且结果是字符串，它会把 `_format_warning_block()` 生成的 Markdown 警告块追加到原结果后面。若工具结果是简短错误 JSON，它会避免追加安全提示，以免掩盖更直接的工具错误。

`plugins/security-guidance/patterns.py` 的核心入口是 `SECURITY_PATTERNS`。这些规则覆盖不安全反序列化、命令注入、代码注入、XSS sink、TLS 校验关闭、AES ECB、XML 解析风险、远程 script 缺 SRI、GitHub Actions 注入等类别。规则不是复杂的数据流分析，而是 regex 与 substring 的混合匹配，并借助文件路径后缀减少误报。

## 主流程位置

主流程横跨插件目录和 Hermes 工具调度层。

第一步是插件发现。`model_tools.py` 会导入并触发 `hermes_cli.plugins.discover_plugins()`，插件管理器读取 `plugin.yaml` 并加载 `plugins/security-guidance/__init__.py`。插件被启用后，`register(ctx)` 把两个 hook 挂到全局插件管理器。

第二步是工具执行前检查。`model_tools.py` 的 `handle_function_call()` 在真正 dispatch 工具前调用 `hermes_cli.plugins.get_pre_tool_call_block_message()`。这个函数内部会 `invoke_hook("pre_tool_call", ...)`，收集插件返回值。如果 `security-guidance` 处于 block 模式，并且本次工具属于目标写入工具且内容命中规则，就返回阻断消息；`handle_function_call()` 随后返回一个 JSON 错误结果，实际写入不会发生。

第三步是工具正常 dispatch。若未阻断，`model_tools.py` 调用 `registry.dispatch(...)` 执行真实工具，比如写文件或应用 patch。此时插件默认不会改变写入动作本身。

第四步是工具结果转换。工具执行完成后，`model_tools.py` 先触发 `post_tool_call`，再触发 `transform_tool_result`。`security-guidance` 的 `_on_transform_tool_result()` 在这里扫描同一份工具参数。如果命中，它返回一个新的结果字符串；`model_tools.py` 采用第一个字符串型 hook 返回值替换原结果。这个结果随后进入对话上下文，模型下一轮可以看到警告并修复代码。

扫描内部的主线是：`_extract_path_and_content()` 根据 `_TARGET_TOOLS` 从工具参数提取路径和文本；`_scan_content()` 遍历预编译后的 `_COMPILED` 规则；路径规则先执行 `path_check` 或 `path_filter`；内容规则再检查 `substrings` 和 `regex`；命中后形成 `(ruleName, reminder)`；最后 `_format_warning_block()` 把多条命中合并成一个可读警告块。

## 推荐阅读顺序

建议先读 `plugins/security-guidance/README.md`，建立对插件目标、覆盖范围、启用方式和限制的整体认识。这里会先说明为什么默认只警告、不阻断，以及它没有移植哪些更重的审计层。

然后读 `plugins/security-guidance/plugin.yaml`，确认它作为 Hermes 插件暴露出的最小外形：名字、描述、作者和声明的 hooks。这个文件能帮助你理解它为什么不出现在普通工具列表里。

第三步读 `plugins/security-guidance/__init__.py`。重点看 `_TARGET_TOOLS`、`_MAX_SCAN_BYTES`、`_block_mode_enabled()`、`_plugin_disabled()`、`_scan_content()`、`_on_pre_tool_call()`、`_on_transform_tool_result()`、`register(ctx)`。这些函数串起来就是完整执行路径。

第四步再读 `plugins/security-guidance/patterns.py`。不要一开始逐条背规则，先看规则结构：哪些规则靠路径触发，哪些规则按后缀过滤，哪些规则靠 substring，哪些规则靠 regex。之后再按风险类别查具体 reminder。

最后按需查看邻近框架代码：`model_tools.py` 中工具执行前的 `get_pre_tool_call_block_message()` 调用，以及工具执行后的 `invoke_hook("transform_tool_result", ...)`；`hermes_cli/plugins.py` 中 `discover_plugins()`、`invoke_hook()`、`get_pre_tool_call_block_message()`。这些位置能解释插件回调为何能影响工具结果。

## 常见误区

第一个误区是把它理解成“安全扫描器”。它只是写入阶段的规则提示层，不做跨文件数据流追踪，也不保证发现所有漏洞。它的价值在于低成本、低延迟地提醒模型常见危险写法。

第二个误区是以为默认会阻止危险代码落盘。默认模式下不会阻止写入，只会追加警告。要阻断必须显式设置 `SECURITY_GUIDANCE_BLOCK=1`。这也是为了避免 `eval(`、`yaml.load`、测试 fixture、文档片段等场景造成误报后中断工作流。

第三个误区是以为它扫描最终文件内容。根据当前实现，它扫描的是工具调用参数中的新内容字段，例如 `write_file` 的 `content`、`patch` 的 `new_string` 或 `patch`、`skill_manage` 的 `file_content` 或 `new_string`。它不是读取磁盘上的完整文件再分析。

第四个误区是忽略 `_MAX_SCAN_BYTES`。超过 256 KiB 的内容会跳过扫描，这是为了避免大文件或二进制式文本拖慢 agent 循环。因此大规模生成文件不一定会触发提示。

第五个误区是认为 `patterns.py` 里的所有规则对所有文件生效。很多规则带 `path_filter`，例如 Python 规则偏向 `.py`、`.pyi`、`.ipynb`，JS/TS 规则偏向前端后缀，文档类文件会跳过某些代码注入规则。路径过滤是误报控制的一部分。

第六个误区是直接修改 `patterns.py` 当成本地策略系统。这个文件标注为外部规则数据的拷贝，Hermes 侧适配逻辑在 `__init__.py`。如果要扩展项目本地策略，根据 README 当前说明，还没有 `.hermes/security-guidance.md` 这类项目规则文件支持；贸然改规则数据会增加后续同步和授权维护成本。
