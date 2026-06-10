# 目录：src/commands/passes

## 它负责什么

`src/commands/passes` 是 `/passes` 本地命令的命令入口目录，职责很轻：它不直接实现 guest passes 的完整业务，也不负责网络请求细节，而是把“命令是否可见、命令描述、命令执行时加载哪个 JSX 组件”这几件事接到命令系统里。

从当前代码看，`passes` 对应 Claude Code 的 “Guest passes” 功能：允许符合条件的用户分享 Claude Code 免费试用通行证，并在某些活动规则下获得额外用量奖励。这个目录只处理命令层的薄封装，实际 eligibility 缓存、referral link、redemption 状态、UI 绘制、复制链接等逻辑都放在邻近模块中。

它的核心边界可以这样理解：

- `src/commands/passes/index.ts`：声明 `/passes` 是一个 `local-jsx` 命令，并根据缓存状态控制是否隐藏。
- `src/commands/passes/passes.tsx`：命令执行入口，记录首次访问状态、埋点，然后渲染 `Passes` 组件。
- `src/components/Passes/Passes.tsx`：真正的交互 UI 和数据加载位置。
- `src/services/api/referral.ts`：guest passes eligibility、缓存、redemptions 等 API 辅助逻辑所在位置。

因此，这个目录更像“命令注册适配层”，不是 guest passes 功能的完整实现目录。

## 直接子目录地图

这个目录当前没有直接子目录，只有两个文件：

- `src/commands/passes/index.ts`：命令定义文件，导出默认 `Command` 对象。
- `src/commands/passes/passes.tsx`：本地 JSX 命令的 `call` 函数实现，负责进入 UI 前的轻量状态更新和埋点。

因为没有子目录，所以阅读时不需要做目录树分层。真正需要展开理解的模块在目录外部，主要是 `src/components/Passes/Passes.tsx` 和 `src/services/api/referral.ts`。

## 关键入口

最直接的入口是 `src/commands/passes/index.ts`。它导出一个满足 `Command` 类型的默认对象：

- `type: 'local-jsx'` 表示这是一个本地 JSX 渲染命令，会在终端 Ink UI 中展示交互界面。
- `name: 'passes'` 表示命令名是 `/passes`。
- `description` 是 getter，会根据 `getCachedReferrerReward()` 判断描述文案。如果缓存里存在 referrer reward，就显示包含“earn extra usage”的描述；否则只显示分享免费一周 Claude Code 的描述。
- `isHidden` 也是 getter，会调用 `checkCachedPassesEligibility()`，当用户不 eligible 或没有 cache 时隐藏命令。
- `load: () => import('./passes.js')` 表示命令真正执行时才动态加载 `passes.tsx` 编译后的模块。

这个入口被上层命令聚合文件 `src/commands.ts` 引入：`import passes from './commands/passes/index.js'`。这说明 `/passes` 属于常规命令集合，而不是通过 feature flag 条件 require 的实验命令。是否展示由 `isHidden` 和 referral 缓存决定，而不是在 `src/commands.ts` 中条件注册。

执行入口在 `src/commands/passes/passes.tsx` 的 `call(onDone)`。它会读取 `getGlobalConfig()`，判断 `hasVisitedPasses` 是否已经存在。如果是首次访问，就通过 `getCachedRemainingPasses()` 取当前剩余 passes 数，并调用 `saveGlobalConfig()` 写入：

- `hasVisitedPasses: true`
- `passesLastSeenRemaining: remaining ?? current.passesLastSeenRemaining`

随后它调用 `logEvent('tengu_guest_passes_visited', { is_first_visit: isFirstVisit })` 记录访问事件，最后返回 `<Passes onDone={onDone} />`。

## 主流程位置

主流程分为“启动预取”“命令可见性判断”“执行命令并展示 UI”三段。

第一段在启动阶段。`src/main.tsx` 中会调用 `prefetchPassesEligibility()`，它来自 `src/services/api/referral.ts`。根据当前片段推断，这一步用于提前填充 `GlobalConfig` 里的 passes eligibility cache，避免用户打开命令列表时再阻塞请求。依据是 `referral.ts` 中 `getCachedOrFetchPassesEligibility()` 的注释明确说明：无缓存时会后台 fetch 并返回 `null`，冷启动时命令本 session 可能不可用，要等下一次 session 使用缓存。

第二段是命令可见性判断，位置在 `src/commands/passes/index.ts` 的 `isHidden` getter。它调用 `checkCachedPassesEligibility()`，只有 `eligible === true` 且 `hasCache === true` 时才显示 `/passes`。`checkCachedPassesEligibility()` 本身还会先检查用户是否满足基础条件：存在 organization UUID、是 Claude.ai subscriber、订阅类型为 `max`。如果这些条件不满足，直接返回不可用。

第三段是用户执行 `/passes` 后的 UI 主流程。`src/commands/passes/passes.tsx` 的 `call()` 只做首次访问标记和埋点，然后把控制权交给 `src/components/Passes/Passes.tsx`。`Passes` 组件加载时会调用 `getCachedOrFetchPassesEligibility()` 检查 eligibility；如果不可用，显示 “Guest passes are not currently available.”；如果可用，则读取 referral link、referrer reward，并继续调用 `fetchReferralRedemptions(campaign)` 获取兑换情况。之后它根据 redemptions 和 limit 构造 `passStatuses`，按可用优先排序，渲染最多 3 张票券，并支持按 Enter 复制 referral link，Esc 或相关 keybinding 退出。

也就是说，`src/commands/passes` 自身不拥有主业务状态机，它只把命令生命周期接入系统；完整状态机在 `src/components/Passes/Passes.tsx` 与 `src/services/api/referral.ts` 之间完成。

## 推荐阅读顺序

建议先读 `src/commands/passes/index.ts`。这个文件最短，但能确定 `/passes` 的命令类型、名称、动态加载方式，以及为什么命令有时不可见。

然后读 `src/commands/passes/passes.tsx`。这里能看到命令执行时的副作用：首次访问标记、剩余 passes 记录、analytics 事件，以及最终渲染 `Passes` 组件。

第三步读 `src/services/api/referral.ts` 中和 passes 相关的几个函数：`checkCachedPassesEligibility()`、`getCachedReferrerReward()`、`getCachedRemainingPasses()`、`fetchAndStorePassesEligibility()`、`getCachedOrFetchPassesEligibility()`、`prefetchPassesEligibility()`。这些函数解释了缓存为什么重要，以及为什么 `/passes` 可能在没有缓存时被隐藏。

第四步读 `src/components/Passes/Passes.tsx`。这里是用户真正看到的界面，包括 loading、不可用、可用票券列表、referral link、reward 文案、复制链接和退出行为。

最后可以回到 `src/commands.ts` 和 `src/main.tsx` 看整体接线：前者说明命令如何进入命令集合，后者说明 passes eligibility 预取在启动流程中的位置。

## 常见误区

一个常见误区是把 `src/commands/passes` 当成 guest passes 的完整业务目录。实际上这里没有 API 请求实现，也没有完整 UI 状态管理；它只是命令层入口。业务数据在 `src/services/api/referral.ts`，界面在 `src/components/Passes/Passes.tsx`。

第二个误区是认为 `/passes` 的可见性来自 feature flag。当前片段中 `passes` 在 `src/commands.ts` 是直接 import 的，不像某些命令通过 `feature('...')` 条件加载。它是否隐藏主要由 `checkCachedPassesEligibility()` 的缓存结果和用户资格决定。

第三个误区是忽略缓存语义。`getCachedOrFetchPassesEligibility()` 的设计是“不阻塞网络”：没有缓存时触发后台 fetch 但返回 `null`，因此命令可能本次 session 不出现。这个行为不是 UI bug，而是当前实现为了避免命令列表或渲染阶段等待网络请求。

第四个误区是以为 `passes.tsx` 里的 `hasVisitedPasses` 会影响 eligibility。它主要用于控制 upsell 展示和记录用户是否访问过 `/passes`，不是资格判断来源。资格判断仍然来自 referral eligibility cache。

第五个误区是把剩余 passes 数的展示逻辑放到命令目录理解。`passes.tsx` 只在首次访问时保存 `passesLastSeenRemaining`；真正展示剩余数量、票券状态和 redemption 信息的是 `src/components/Passes/Passes.tsx`。
