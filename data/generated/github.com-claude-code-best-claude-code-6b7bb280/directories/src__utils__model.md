# 子系统：src/utils/model

## 解决什么问题

`src/utils/model` 是整个 CLI 的“模型语义层”。它不负责真正发请求，而是把用户输入、环境变量、订阅状态、provider 差异、模型别名、上下文窗口、价格展示和可用性校验统一起来，输出一个可供上层直接消费的模型字符串或展示文案。根据当前片段推断，它的目标不是单纯保存模型常量，而是把“选什么模型、怎么显示、能不能用、要不要升级、在不同 provider 下对应什么 ID”这些散落规则集中处理。

这一层直接服务于主对话模型、子 agent 模型、`/model` 选择器、命令行参数、技能里的 `model:` 覆盖、以及 Bedrock/Vertex/Foundry/OpenAI/Gemini/Grok 这些 provider 的兼容逻辑。

## 相关目录和文件

核心文件是 `src/utils/model/model.ts`，它聚合了默认模型选择、别名解析、展示名、营销名、`[1m]` 语义、legacy remap、技能模型覆盖等主逻辑。  
`src/utils/model/providers.ts` 决定当前 API provider，优先级是 `settings.modelType`，再看环境变量开关。  
`src/utils/model/modelStrings.ts` 维护 provider 维度的模型 ID 映射，并处理 Bedrock inference profile 的动态探测。  
`src/utils/model/configs.ts` 是 canonical model 配置表，定义 `opus47`、`sonnet46` 这类内部 key 到各 provider 真实 ID 的映射。  
`src/utils/model/modelOptions.ts` 生成 `/model` 菜单项。  
`src/utils/model/agent.ts` 处理子 agent 模型继承和 Bedrock region prefix。  
`src/utils/model/validateModel.ts` 做实际 API 验证。  
`src/utils/model/modelAllowlist.ts` 负责 `availableModels` 白名单。  
`src/utils/model/check1mAccess.ts`、`contextWindowUpgradeCheck.ts`、`deprecation.ts`、`bedrock.ts`、`chatgptModels.ts`、`modelCapabilities.ts` 则分别覆盖 1M 访问、升级提示、弃用提示、Bedrock 客户端、ChatGPT 兼容模式和模型能力缓存。

## 核心对象

这里最重要的几类类型是：

- `APIProvider`：`firstParty`、`bedrock`、`vertex`、`foundry`、`openai`、`gemini`、`grok`
- `ModelConfig` / `ALL_MODEL_CONFIGS`：canonical 模型到各 provider 字符串的映射
- `ModelStrings`：运行时已解析的 provider-specific 模型表
- `ModelAlias`：`sonnet`、`opus`、`haiku`、`best`、`opusplan`、`[1m]` 相关别名
- `ModelSetting`：用户可配置的模型值，允许 alias 或完整模型名
- `ModelOption`：`/model` 菜单展示结构
- `ModelCapability`：从 `/v1/models` 或缓存中读到的输入/输出 token 能力

`model.ts` 里的 `getDefaultOpusModel()`、`getDefaultSonnetModel()`、`getDefaultHaikuModel()`、`getMainLoopModel()`、`parseUserSpecifiedModel()`、`renderModelName()`、`getCanonicalName()` 是最常被上层调用的入口。

## 运行流程

常见路径是：先由 `providers.ts` 判定 provider，再由 `modelStrings.ts` 初始化该 provider 的模型 ID 表；随后 `model.ts` 根据订阅、环境变量、settings 和会话内 override 计算主模型，`parseUserSpecifiedModel()` 把别名展开成真实 ID，`renderModelName()` 再把它转成可读文本。

如果是用户在 `/model` 里选模型，`modelOptions.ts` 会先用 `getDefaultMainLoopModelSetting()`、`getDefaultOpusModel()` 等函数拼出菜单；如果是子 agent，则 `agent.ts` 会优先继承父线程模型，必要时保留 Bedrock 的 region prefix。  
如果用户输入了非法模型，`validateModel.ts` 会先查 allowlist，再必要时发一个最小 `sideQuery` 做真实校验。  
如果是 Bedrock，`modelStrings.ts` 还会异步拉 inference profile 列表，把本地默认字符串替换成可用的 region/profile ID。

## 上下游依赖

上游主要依赖 `bootstrap/state.ts`、`settings/settings.ts`、`auth.ts`、`context.ts`、`config.ts`、`envUtils.ts`、`modelCost.ts` 和 `services/api/client.ts`。这些模块提供订阅状态、用户设置、环境开关、上下文窗口能力和成本信息。

下游则非常广：`src/query.ts`、`src/QueryEngine.ts`、`src/components/ModelPicker.tsx`、`src/components/StatusLine.tsx`、`src/commands/model/*`、`src/services/api/claude.ts`、`packages/builtin-tools/src/tools/AgentTool/*`、`src/services/SessionMemory/*`、`src/services/MagicDocs/*`、`src/cli/print.ts` 等都在消费这里的结果。换句话说，这个目录是“模型决策的单一事实来源”。

## 修改时最容易踩的坑

第一，provider 优先级不能乱改：`settings.modelType` 会压过环境变量，而 Bedrock/Vertex/Foundry/OpenAI/Gemini/Grok 的分支顺序也有明确约束。  
第二，别名和真实模型名不是一回事，`opus` 这种别名在某些场景会解析到当前默认 Opus，而不是固定版本。  
第三，`[1m]` 不是纯展示后缀，它会影响上下文窗口和升级提示，`resolveSkillModelOverride()`、`getRuntimeMainLoopModel()`、`isOpus1mMergeEnabled()` 都会受它影响。  
第四，`modelAllowlist.ts` 对 family alias 有“被更具体版本项收窄”的逻辑，不能只做简单包含判断。  
第五，Bedrock 的模型字符串可能来自 inference profile，`getModelStrings()` 在它身上是异步初始化，不能假设启动瞬间就是最终值。  
第六，`model.ts` 里有 legacy remap 和用户可见文案逻辑，改动时要同步检查 `modelOptions.ts`、`deprecation.ts`、`validateModel.ts` 的联动。

## 推荐阅读顺序

1. `src/utils/model/providers.ts`
2. `src/utils/model/configs.ts`
3. `src/utils/model/modelStrings.ts`
4. `src/utils/model/model.ts`
5. `src/utils/model/modelOptions.ts`
6. `src/utils/model/agent.ts`
7. `src/utils/model/modelAllowlist.ts`
8. `src/utils/model/validateModel.ts`
9. `src/utils/model/check1mAccess.ts`、`contextWindowUpgradeCheck.ts`
10. `src/utils/model/bedrock.ts`、`deprecation.ts`、`modelCapabilities.ts`
