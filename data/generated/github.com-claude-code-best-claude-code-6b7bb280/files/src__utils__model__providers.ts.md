# 文件：src/utils/model/providers.ts

## 一句话定位
这是整个代码库里“当前会走哪个模型服务提供方”的判定入口。它把 `settings.json`、环境变量和少量基础 URL 判断收拢成统一的 `APIProvider`，供请求构造、鉴权、统计和一些迁移逻辑复用。

## 它暴露/定义了什么
这个文件主要暴露 3 个东西：`APIProvider` 联合类型，`getAPIProvider()` 以及两个派生判断 `getAPIProviderForStatsig()`、`isFirstPartyAnthropicBaseUrl()`。其中 `APIProvider` 只覆盖当前仓库已经显式支持的几类后端：`firstParty`、`bedrock`、`vertex`、`foundry`、`openai`、`gemini`、`grok`。

## 谁调用它
从当前仓库片段能直接看到，它被大量上层模块引用，属于“横切判断”而不是局部工具。典型调用者包括 `src/query.ts`、`src/services/api/claude.ts`、`src/services/api/client.ts`、`src/services/api/logging.ts`、`src/utils/auth.ts`、`src/utils/fastMode.ts`、`src/utils/thinking.ts`、`src/commands/provider.ts`、若干迁移脚本，以及 `packages/builtin-tools/src/tools/WebSearchTool` 和 `AgentTool` 相关实现。根据当前片段推断，这些调用点分别把 provider 用在请求分流、能力开关、日志埋点、模型名映射和兼容性判断上。

## 它调用谁
这个文件自身依赖很少，核心只读两个来源：`getInitialSettings()` 用来拿默认设置，`isEnvTruthy()` 用来统一解释环境变量真假值。`isFirstPartyAnthropicBaseUrl()` 还会用原生 `URL` 解析 `ANTHROPIC_BASE_URL`。此外 `getAPIProviderForStatsig()` 只是把 `getAPIProvider()` 的结果做一次类型转换，不引入新逻辑。

## 核心流程
`getAPIProvider()` 的流程非常明确：先看 `settings.modelType`，如果用户显式选择了 `openai`、`gemini` 或 `grok`，就直接返回对应 provider，这一层优先级最高。若没有显式设置，再按环境变量判断 `CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_VERTEX`、`CLAUDE_CODE_USE_FOUNDRY`，然后才看 `CLAUDE_CODE_USE_OPENAI`、`CLAUDE_CODE_USE_GEMINI`、`CLAUDE_CODE_USE_GROK`。都不命中时退回 `firstParty`。也就是说，它是一个“设置优先于环境，3P 云优先于兼容层，最后回落到 Anthropic 官方”的分发器。

`isFirstPartyAnthropicBaseUrl()` 则是一个补充判断：只要 `ANTHROPIC_BASE_URL` 没设，就认为是 first-party；如果设了，就检查 host 是否是 `api.anthropic.com`，在 `USER_TYPE === 'ant'` 时额外允许 `api-staging.anthropic.com`。根据当前片段推断，它主要被拿来区分是否还属于 Anthropic 原生接口域名。

## 关键函数的高层作用
`getAPIProvider()` 是最核心的单点决策函数。它让上层代码不用重复写“从设置、环境变量里猜后端”的逻辑，只要拿到 provider 字符串，就能继续走模型名映射、请求参数组装、统计埋点或功能开关。`getAPIProviderForStatsig()` 的作用很窄，只是给分析系统一个类型上兼容的 provider 标签。`isFirstPartyAnthropicBaseUrl()` 则用于某些路径里判断“是不是 Anthropic 官方基址”，通常会影响认证头、请求策略或兼容分支。

## 修改风险
这个文件改动面很大，但代码本身很短，风险集中在“全局契约”而不是实现复杂度。第一，`getAPIProvider()` 的判断顺序一旦改动，可能改变整个产品的后端路由，尤其是 settings 与环境变量冲突时的优先级。第二，新增 provider 时必须同步更新 `APIProvider`、相关模型映射、统计埋点和各处 `switch`/分支；仓库里 `src/utils/auth.ts` 已明确提示要和这里保持一致。第三，`isFirstPartyAnthropicBaseUrl()` 里已经有 TODO，说明对只配置 OpenAI 协议但未显式设置 `ANTHROPIC_BASE_URL` 的场景可能误判，修改这块要特别小心回归。
