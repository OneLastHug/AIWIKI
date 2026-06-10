# 子系统：src/agents/schema

## 解决什么问题

`src/agents/schema` 是 OpenClaw agent 工具参数 schema 的“兼容性与便捷构造”层。它不负责定义某一个具体工具的完整参数，而是提供一组可复用的 TypeBox schema helper，并在工具 schema 被交给不同模型 provider 前，处理各 provider 对 JSON Schema 支持不一致的问题。

这个目录解决的核心矛盾是：OpenClaw 内部和插件侧希望用较完整、表达力较强的 TypeBox/JSON Schema 描述工具参数；但 Gemini、xAI、OpenAI Responses 等 provider 对工具 schema 的可接受子集并不完全相同。例如 Gemini 会拒绝 `$ref`、`$defs`、`pattern`、`minLength`、`anyOf`/`oneOf` 的部分形态、空 `required` 等字段；xAI 会拒绝部分长度和数组约束关键字。`src/agents/schema` 通过“生成更保守的 schema”和“发送前清理 schema”两条路径降低工具调用失败率。

## 相关目录和文件

`src/agents/schema/string-enum.ts` 提供 `stringEnum` 和 `optionalStringEnum`。它故意不使用 `Type.Union([Type.Literal(...)])`，而是生成扁平的 `{ type: "string", enum: [...] }`，因为部分 provider 会拒绝 `anyOf` 形式的枚举。

`src/agents/schema/typebox.ts` 是面向内部工具和 SDK 暴露的轻量入口。它重新导出枚举 helper，并提供 `channelTargetSchema`、`channelTargetsSchema`，把 channel target 的说明文字接入通用工具 schema。

`src/agents/schema/clean-for-gemini.ts` 是目录中最重的逻辑，负责把输入 schema 递归清理成 Gemini/Cloud Code Assist API 更容易接受的形态，包括删除不支持关键字、展开本地 `$ref`、折叠 nullable union、修正 `required`、处理 malformed `properties`。

`src/agents/schema/clean-for-gemini.test.ts` 和 `src/agents/schema/clean-for-xai.test.ts` 是兼容性回归测试。前者直接验证 Gemini 清理规则；后者通过 `src/plugin-sdk/provider-tools.ts` 的通用 `stripUnsupportedSchemaKeywords` 验证 xAI 类 provider 的关键字剥离行为。

邻近调用方主要在 `src/plugin-sdk/provider-tools.ts`、`src/agents/pi-tools-parameter-schema.ts`、`src/agents/tools/*`。插件侧还会通过 `openclaw/plugin-sdk/channel-actions`、`openclaw/plugin-sdk/core`、`openclaw/plugin-sdk` 间接使用这些 helper。

## 核心对象

`stringEnum(values, options)` 是最基础的 schema 构造器。它接收字符串数组和可选的 `description`、`title`、`default`、`deprecated`，输出 TypeBox 可接受的 unsafe schema。其关键价值不是类型复杂度，而是 provider 兼容性：避免产生 `anyOf`。

`optionalStringEnum(values, options)` 在 `stringEnum` 外包一层 `Type.Optional`，用于大量工具的可选枚举参数，例如动作、模式、输出格式、优先级等。

`channelTargetSchema` 和 `channelTargetsSchema` 把 `src/infra/outbound/channel-target.js` 中的描述常量接入工具参数，统一 `target` / `targets` 的参数说明。它们只是字符串和字符串数组 schema，不负责解析或校验 target 的业务语义。

`GEMINI_UNSUPPORTED_SCHEMA_KEYWORDS` 是 Gemini 清理规则的关键配置，列出需要删除的 JSON Schema/OpenAPI 关键字，例如 `$schema`、`$id`、`$ref`、`$defs`、`additionalProperties`、长度/数量约束、`pattern`、`format`、`not` 等。

`cleanSchemaForGemini(schema)` 是对外主入口。它递归遍历 schema，调用内部的引用解析、union 简化、元数据复制、required 修正和 fallback flatten 逻辑，最终返回 `TSchema`。

## 运行流程

常规路径是：工具代码在 `src/agents/tools/*` 或插件目录中用 TypeBox 定义参数；遇到枚举时优先使用 `stringEnum` / `optionalStringEnum`，使源头 schema 尽量扁平；工具集合进入 provider 适配层后，由 `src/plugin-sdk/provider-tools.ts` 根据 provider 类型做二次 normalize。

当 provider 是 Gemini 相关实现时，`normalizeGeminiToolSchemas` 会遍历每个 tool，把 `tool.parameters` 交给 `cleanSchemaForGemini`。清理过程先收集当前 schema 的 `$defs` / `definitions`，遇到本地 `$ref` 时尝试解析并递归清理；遇到 `anyOf` / `oneOf` 时先尝试把 literal union 压成 `enum`，再剥离 null variant；若仍无法表达，则用 fallback 选取代表性 `type`，优先保证 provider 接受工具声明。

清理对象字段时，Gemini 不支持的关键字会被跳过；`const` 会转成单值 `enum`；空 `required` 会被删除；`type: ["string", "null"]` 会折叠为 `type: "string"`；`properties` 如果不是普通对象，会被规范化为空对象，避免下游 validator 崩溃。最后 `sanitizeRequiredFields` 会确保 `required` 里只保留 `properties` 中真实存在的字段。

xAI 的路径不在本目录实现专门函数，而是通过 `src/plugin-sdk/provider-tools.ts` 的 `stripUnsupportedSchemaKeywords` 递归删除指定关键字。`clean-for-xai.test.ts` 放在这里，是因为它验证的是同一类 schema provider 兼容策略。

## 上下游依赖

上游依赖主要是 `typebox`，以及 channel target 的描述常量 `src/infra/outbound/channel-target.js`。这个目录不依赖具体 provider SDK，也不直接发起模型请求。

下游首先是 agent 内置工具，例如 `src/agents/tools/message-tool.ts`、`src/agents/tools/cron-tool.ts`、`src/agents/tools/gateway-tool.ts`、`src/agents/tools/sessions-spawn-tool.ts` 等，它们用这里的 helper 构建参数 schema。其次是插件 SDK 暴露面：`src/plugin-sdk/core.ts`、`src/plugin-sdk/channel-actions.ts`、`src/plugin-sdk/index.ts`、`src/plugin-sdk/compat.ts` 会把 `stringEnum` 等导出给插件使用。再往下是 provider 工具 normalize：`src/plugin-sdk/provider-tools.ts` 会把这里的 Gemini 清理函数纳入 provider 发送前流程。

根据当前片段推断，这个目录位于“工具定义”和“provider 请求”之间的稳定边界：工具作者看到的是简洁的 TypeBox helper，provider 适配层看到的是可递归清理的 JSON Schema 对象。

## 修改时最容易踩的坑

第一，不要把枚举重新改回 `Type.Union([Type.Literal(...)])`。这会让 schema 重新生成 `anyOf`，破坏部分 provider 的兼容性。

第二，Gemini 清理不是普通格式化，删除关键字会降低校验表达力。新增剥离规则时要确认是 provider 合约或实际 400 行为需要，而不是为了让任意 malformed schema 静默通过。

第三，`$ref` 处理只支持本地 `#/$defs/...` 和 `#/definitions/...` 形态，并有递归引用保护。不要假设它是完整 JSON Schema resolver。

第四，`required` 必须和 `properties` 同步。Gemini 会拒绝引用不存在属性的 `required`，测试里已经覆盖了 inherited key、空数组、缺失 properties 等边界。

第五，清理逻辑会复制 `description`、`title`、`default` 等元信息。改 union flatten 或 `$ref` 展开时要保留这些面向模型的提示信息，否则工具可用性会下降。

第六，provider 差异要放在正确层次。通用关键字剥离在 `src/plugin-sdk/provider-tools.ts`，Gemini 特化在 `clean-for-gemini.ts`；不要把 xAI/OpenAI 的规则混入 Gemini 专用函数，除非它们确实共享同一 provider contract。

## 推荐阅读顺序

1. 先读 `src/agents/schema/string-enum.ts`，理解为什么 OpenClaw 偏好扁平字符串枚举。
2. 再读 `src/agents/schema/typebox.ts`，看这个目录向工具作者暴露的最小 API。
3. 然后读 `src/plugin-sdk/provider-tools.ts` 的 `normalizeGeminiToolSchemas`、`stripUnsupportedSchemaKeywords`，理解 schema helper 如何进入 provider normalize 流程。
4. 接着读 `src/agents/schema/clean-for-gemini.ts`，重点看不支持关键字集合、`$ref` 展开、union 简化、`required` 修正。
5. 最后读 `src/agents/schema/clean-for-gemini.test.ts` 和 `src/agents/schema/clean-for-xai.test.ts`，用测试用例反推哪些行为是已经固化的兼容性合同。
