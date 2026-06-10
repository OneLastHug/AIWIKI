# 目录：src/commands/logout

## 它负责什么

`src/commands/logout` 是 Claude Code 中“登出当前账号/清理认证状态”的核心目录。它的职责不是展示登录状态，也不是执行 OAuth 登录流程，而是提供一套可复用的登出清理函数，并把它包装成 `/logout` 斜杠命令可调用的本地 JSX 命令。

这个目录的核心边界可以概括为三层：

第一层是命令声明：`src/commands/logout/index.ts` 定义命令元信息，包括命令名 `logout`、说明文案、启用条件和懒加载入口。

第二层是登出执行：`src/commands/logout/logout.tsx` 中的 `performLogout()` 承担真正的清理工作，会移除 API key、ChatGPT/OpenAI 认证状态、secure storage、OAuth 账号信息，并刷新或清空一系列与认证相关的缓存。

第三层是 UI 命令回调：同一个文件里的 `call()` 是 `/logout` 命令加载后执行的入口。它调用 `performLogout({ clearOnboarding: true })`，返回 Ink 的 `<Text>` 成功提示，并在短暂延迟后通过 `gracefulShutdownSync(0, 'logout')` 退出进程。

从目录定位看，这里属于 `src/commands` 下的斜杠命令体系，同时也被 CLI 认证子命令复用：`src/cli/handlers/auth.ts` 会直接导入 `performLogout()` 和 `clearAuthRelatedCaches()`，用于 `claude auth logout` 以及 OAuth token 安装前后的认证状态切换。

## 直接子目录地图

`src/commands/logout` 当前没有直接子目录，只有两个文件：

`src/commands/logout/index.ts`：命令注册描述文件。它导出一个满足 `Command` 类型的对象，声明这是一个 `local-jsx` 命令，命令名为 `logout`，并通过 `load: () => import('./logout.js')` 延迟加载实现模块。

`src/commands/logout/logout.tsx`：命令实现文件。这里集中放置登出主流程、认证缓存清理逻辑、ChatGPT/OpenAI 设置清理逻辑，以及 `/logout` 的 Ink 返回节点。

因此，这不是一个多层功能目录，而是一个“小目录承载共享认证清理能力”的结构。理解它时不需要按子模块拆分阅读，重点是看清 `index.ts` 如何暴露命令，以及 `logout.tsx` 如何被多个入口复用。

## 关键入口

最直接的入口是 `src/commands/logout/index.ts` 的默认导出。它定义：

`type: 'local-jsx'` 表示该命令在本地以 JSX/Ink 组件结果形式执行。

`name: 'logout'` 表示用户在交互式 CLI 中使用 `/logout` 触发。

`isEnabled: () => !isEnvTruthy(process.env.DISABLE_LOGOUT_COMMAND)` 表示当环境变量 `DISABLE_LOGOUT_COMMAND` 为真值时，该命令会被隐藏或禁用。

`load: () => import('./logout.js')` 表示真正执行逻辑在 `logout.tsx`，并且是懒加载。这符合 `src/commands` 体系中减少启动加载成本的常见做法。

实现侧的关键入口有三个：

`call()`：斜杠命令执行入口。它调用 `performLogout({ clearOnboarding: true })`，显示 `Successfully logged out.`，随后触发优雅退出。

`performLogout({ clearOnboarding })`：登出主函数。它是目录中最重要的复用函数，被 `/logout` 和 `claude auth logout` 共享，也被登录流程在安装新 OAuth tokens 前调用，用于先清掉旧状态。

`clearAuthRelatedCaches()`：认证状态变化后的缓存失效函数。它既服务于登出，也服务于登录后刷新状态，因此不应把它理解成“只属于登出”的函数，而是“认证上下文变化后的统一缓存刷新点”。

## 主流程位置

`/logout` 的主流程从 `src/commands.ts` 开始被纳入斜杠命令集合。该文件导入 `src/commands/logout/index.ts`，并在 `COMMANDS` 数组中加入 `logout`。不过这里还有一个重要条件：`logout` 和 `login()` 只在 `!isUsing3PServices()` 时加入命令集合。也就是说，当当前运行模式使用第三方服务提供商时，内置的 Claude 账号登录/登出命令可能不会出现在斜杠命令列表中。

斜杠命令触发后，命令系统根据 `index.ts` 的 `load()` 加载 `logout.tsx`，再执行其中的 `call()`。`call()` 的流程很短：先 `performLogout({ clearOnboarding: true })`，再返回成功提示，最后延迟退出。这里的 `clearOnboarding: true` 说明交互式 `/logout` 会把 onboarding 状态也清掉，使用户下次进入时可能重新走初始化/引导状态。

`performLogout()` 的内部主线更关键。它先懒加载并执行 `flushTelemetry()`，注释说明原因是先 flush telemetry，避免清凭据后造成组织数据泄漏或归属混乱。随后依次执行 `removeApiKey()`、`removeChatGPTAuth()`、`clearChatGPTSettingsAuthMode()`，再调用 `getSecureStorage().delete()` 清掉 secure storage。接着执行 `clearAuthRelatedCaches()`，最后用 `saveGlobalConfig()` 移除 `oauthAccount`，并在 `clearOnboarding` 为真时重置 onboarding、订阅提示和自定义 API key approval 相关状态。

另一路主流程是顶层 CLI 子命令：`src/main.tsx` 注册 `auth logout`，其 action 调用 `src/cli/handlers/auth.ts` 中的 `authLogout()`。`authLogout()` 不走 JSX 命令，而是直接调用 `performLogout({ clearOnboarding: false })`，然后向 stdout 输出成功信息并 `process.exit(0)`。这说明 `/logout` 和 `claude auth logout` 的体验不同，但底层清理核心一致。

## 推荐阅读顺序

建议先读 `src/commands/logout/index.ts`。这个文件很短，可以快速确认它属于 `local-jsx` 命令，知道 `/logout` 是怎样被声明、怎样被环境变量禁用、怎样懒加载实现的。

第二步读 `src/commands/logout/logout.tsx`，优先看导出的三个函数：`performLogout()`、`clearAuthRelatedCaches()`、`call()`。阅读时应先从 `call()` 倒推，因为它是斜杠命令的用户入口；然后深入 `performLogout()`，理解登出到底清理了哪些状态；最后看 `clearAuthRelatedCaches()`，理解认证状态变化后哪些缓存必须失效。

第三步读 `src/commands.ts` 中 `logout` 的导入和 `COMMANDS` 数组附近逻辑。重点关注 `...(!isUsing3PServices() ? [logout, login()] : [])`，这解释了为什么某些 provider 模式下可能看不到 `/logout`。

第四步读 `src/cli/handlers/auth.ts` 的 `authLogout()` 和 `installOAuthTokens()`。前者说明 `claude auth logout` 如何复用 `performLogout()`；后者说明登录安装新 token 前也会先调用 `performLogout({ clearOnboarding: false })` 清理旧状态。根据当前片段推断，这种设计是为了让账号切换和登出共享一致的认证清理语义，依据是 `installOAuthTokens()` 中的注释 “Clear old state before saving new credentials”。

最后如果需要扩展理解，可以再看 `src/utils/auth.ts`、`src/utils/secureStorage/index.ts`、`src/services/remoteManagedSettings/index.ts`、`src/services/policyLimits/index.ts` 等被调用模块，但 overview 层面不必展开。

## 常见误区

第一个误区是把 `src/commands/logout` 只理解成 `/logout` 的 UI 命令目录。实际上它还提供共享函数，`src/cli/handlers/auth.ts` 的 `authLogout()` 和登录 token 安装流程都会复用这里的 `performLogout()` 或 `clearAuthRelatedCaches()`。

第二个误区是认为登出只删除 Anthropic API key。实际清理范围更大，包括 ChatGPT/OpenAI 认证、`OPENAI_AUTH_MODE` 设置、secure storage、OAuth 账号信息、trusted device token cache、beta cache、tool schema cache、用户缓存、Grove 配置缓存、remote managed settings 缓存和 policy limits 缓存。

第三个误区是忽略 `/logout` 和 `claude auth logout` 的 `clearOnboarding` 差异。`/logout` 调用 `performLogout({ clearOnboarding: true })`，会重置 onboarding 相关全局配置；`claude auth logout` 调用 `performLogout({ clearOnboarding: false })`，更像纯认证退出，不重置引导状态。

第四个误区是把 `clearAuthRelatedCaches()` 当作登出专用函数。它的注释和调用位置都表明，它服务于所有认证状态变化，包括登录、登出和账号切换。修改这里时要考虑登录后刷新状态的需求，而不只是清空状态。

第五个误区是忽略命令可见性。`index.ts` 里有 `DISABLE_LOGOUT_COMMAND` 开关，`src/commands.ts` 里还有 `isUsing3PServices()` 条件。因此命令不存在不一定代表目录未注册，也可能是当前环境或 provider 模式让它不可用。
