# 目录：src/routes/onboarding

## 它负责什么

`src/routes/onboarding` 是 Web / Mobile SPA 的新用户引导入口目录，承担 `/onboarding`、`/onboarding/agent`、`/onboarding/classic` 这组路由的页面分段、共享布局、分流判断和部分步骤组件。它不是单纯的“薄路由”目录：根据当前片段推断，这里仍保留了一些历史迁移中的业务 UI，例如 `features/FullNameStep.tsx`、`features/InterestsStep.tsx`、`features/AgentPickerStep`、`components/KlavisServerList` 等；而主页面编排已经迁到 `src/features/Onboarding/*`。

整体职责可以理解为三段式 onboarding：

第一段是共享前缀 `/onboarding`，由 `src/routes/onboarding/index.tsx` 转交给 `src/features/Onboarding/Common`。它处理通用引导步骤，例如遥测确认 `TelemetryStep` 和回复语言 `ResponseLanguageStep`，并在完成后根据环境和开关分流到 agent 或 classic。

第二段是智能体式引导 `/onboarding/agent`，由 `src/routes/onboarding/agent/index.tsx` 做路由门禁，再进入 `src/features/Onboarding/Agent`。这个流程以对话为核心，依赖内置 web onboarding agent、topic、message、follow-up extract、bootstrap state 等上下文。

第三段是传统表单式引导 `/onboarding/classic`，由 `src/routes/onboarding/classic/index.tsx` 转交给 `src/features/Onboarding/Classic`。它按用户信息、兴趣、Pro 设置、推荐 agent 选择等步骤推进。

## 直接子目录地图

`src/routes/onboarding/_layout` 是共享外壳。`index.tsx` 定义 `OnBoardingContainer`，负责品牌 Logo、语言按钮、主题按钮、居中内容区，以及 agent/classic 分支之间的底部切换和跳过逻辑；`style.ts` 放布局样式；测试文件覆盖不同路径下 footer 是否出现。

`src/routes/onboarding/agent` 是 `/onboarding/agent` 的路由入口目录。它不直接实现完整聊天 UI，而是做可达性判断：构建期开关 `AGENT_ONBOARDING_ENABLED`、桌面环境 `isDesktop`、服务端 feature flag、用户状态初始化、共享步骤是否完成。通过后才渲染 `src/features/Onboarding/Agent`。

`src/routes/onboarding/classic` 是 `/onboarding/classic` 的路由入口目录，目前只把页面导出为 `src/features/Onboarding/Classic`，属于很薄的 route segment。

`src/routes/onboarding/components` 存放仍被 onboarding 专用步骤复用的局部组件。`LobeMessage.tsx` 是引导页中的消息展示组件；`KlavisServerList` 及其子目录负责 Klavis 服务列表、图标、状态控制和 OAuth / action hooks，主要服务传统流程里的 Pro 或集成设置步骤。

`src/routes/onboarding/features` 存放 onboarding 的步骤级 UI。这里包括 `TelemetryStep`、`ResponseLanguageStep`、`FullNameStep`、`InterestsStep`、`ModeSelectionStep`、`ProSettingsStep`，以及更复杂的 `AgentPickerStep` 子目录。虽然目录名叫 `features`，但它位于 `src/routes` 下，按当前 `spa-routes` 约定看更像尚未完全迁出的旧结构。

## 关键入口

`src/routes/onboarding/index.tsx` 是 `/onboarding` 的页面入口，只导出 `CommonOnboardingPage`。真正流程在 `src/features/Onboarding/Common/index.tsx`：等待 user state 初始化，处理 `?step=1/2`，预加载 agent/classic 路由，迁移旧版 classic step，然后在共享步骤完成后调用 `deriveOnboardingBranchPath` 决定去 `/onboarding/agent` 还是 `/onboarding/classic`。

`src/routes/onboarding/agent/index.tsx` 是 agent 分支入口。它的关键价值是路由保护，而不是页面实现：未开启 agent onboarding、桌面端、服务端配置未初始化、用户通用步骤未完成时都会分别 loading 或 redirect。真正聊天式 onboarding 在 `src/features/Onboarding/Agent/index.tsx`。

`src/routes/onboarding/classic/index.tsx` 是 classic 分支入口，直接导出 `ClassicOnboardingPage`。主逻辑在 `src/features/Onboarding/Classic/index.tsx`，通过 `onboardingSelectors.currentStep` 渲染不同步骤，并处理 Klavis 不可用时跳过 Pro 设置步骤。

`src/routes/onboarding/_layout/index.tsx` 是所有分支共享的视觉入口。Common、Classic、Agent 三个页面都通过 `OnboardingContainer` 包裹内容，因此布局、语言切换、主题切换、agent/classic 切换提示的行为都集中在这里。

`src/routes/onboarding/branch.ts` 是分流规则入口。`deriveOnboardingBranchPath` 将构建期开关、桌面环境、运行时 feature flag 统一折叠成目标路径，避免 Common 页面自己散落判断。

`src/routes/onboarding/config.ts` 和 `src/routes/onboarding/interestCategoryMap.ts` 是配置型入口，分别服务兴趣区域、图标、分类映射等步骤展示。

## 主流程位置

路由注册在 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/mobileRouter.config.tsx` 中都能看到 `/onboarding`、`/onboarding/agent`、`/onboarding/classic`。桌面 Electron 专用配置 `src/spa/router/desktopRouter.config.desktop.tsx` 比较特殊：它把这些 Web onboarding 路径 redirect 到 `/desktop-onboarding`，并由 `src/routes/(desktop)/desktop-onboarding` 负责桌面端引导。`src/spa/router/desktopRouter.sync.test.tsx` 还记录了 `/desktop-onboarding` 与 `/onboarding` 的对应关系。

入口触发位置在 `src/layout/GlobalProvider/useUserStateRedirect.ts`：当用户状态显示需要 onboarding 时，会把非 onboarding 页面导向 `/onboarding`。注释显示桌面 onboarding redirect 现在由主进程 `BrowserManager` 处理，因此 Web 端和 Electron 端入口并不完全相同。

共享前缀主流程位于 `src/features/Onboarding/Common/index.tsx`：第一步 `TelemetryStep`，第二步 `ResponseLanguageStep`，完成后按 `deriveOnboardingBranchPath` 分支。它还负责把旧版 5 步 classic 流程中的 persisted `currentStep` 映射到当前 classic 流程，避免老用户恢复到错误步骤。

classic 主流程位于 `src/features/Onboarding/Classic/index.tsx`：`currentStep=1` 渲染 `FullNameStep`，`2` 渲染 `InterestsStep`，`3` 渲染 `ProSettingsStep`，`MAX_ONBOARDING_STEPS` 渲染 `AgentPickerStep`。如果服务端配置显示 Klavis 不可用，会跳过 Pro 设置相关步骤。

agent 主流程位于 `src/features/Onboarding/Agent/index.tsx`：它围绕 web onboarding agent 构建聊天式引导，读取 bootstrap state、topic、message map、agent onboarding finished 状态，首条消息会走 `userService.sendOnboardingFirstMessage` 的编排，assistant 回合结束后同步 onboarding context，并在完成后生成跳转到正式会话的目标地址。

## 推荐阅读顺序

1. 先读 `src/spa/router/desktopRouter.config.tsx`、`src/spa/router/mobileRouter.config.tsx`、`src/spa/router/desktopRouter.config.desktop.tsx`，确认三个 onboarding 路径在 Web、Mobile、Electron 下的注册差异。

2. 再读 `src/layout/GlobalProvider/useUserStateRedirect.ts`，理解为什么用户会进入 `/onboarding`，以及桌面端为什么走另一套路由。

3. 接着读 `src/routes/onboarding/index.tsx`、`src/features/Onboarding/Common/index.tsx`、`src/routes/onboarding/branch.ts`，掌握共享步骤和分流规则。

4. 然后读 `src/routes/onboarding/_layout/index.tsx`，理解所有 onboarding 页面共同的外壳、语言/主题入口、agent/classic 切换和 skip 行为。

5. 最后按分支选择阅读：传统流程看 `src/routes/onboarding/classic/index.tsx` 和 `src/features/Onboarding/Classic/index.tsx`；智能体流程看 `src/routes/onboarding/agent/index.tsx` 和 `src/features/Onboarding/Agent/index.tsx`。步骤细节再回到 `src/routes/onboarding/features` 和 `src/routes/onboarding/components` 查。

## 常见误区

不要把 `src/routes/onboarding/features` 误认为符合当前推荐结构的新 feature 目录。根据 `spa-routes` 约定，真正的业务 feature 应在 `src/features` 下；这里更像历史遗留或渐进迁移中的步骤组件存放点。

不要只看 `src/routes/onboarding/*.tsx` 就判断流程很简单。三个路由入口大多很薄，真正主流程分散在 `src/features/Onboarding/Common`、`src/features/Onboarding/Classic`、`src/features/Onboarding/Agent`。

不要忽略桌面端差异。普通 desktop router 中有 `/onboarding` 动态入口，但 `.desktop.tsx` 配置会把 `/onboarding`、`/onboarding/agent`、`/onboarding/classic` redirect 到 `/desktop-onboarding`；因此 Electron 桌面 onboarding 的主体不在这个目录。

不要把 agent 分支是否可用只理解为一个服务端开关。`/onboarding/agent` 同时受 `AGENT_ONBOARDING_ENABLED` 构建期开关、`isDesktop`、`serverConfigInit`、`featureFlags.enableAgentOnboarding` 和 `commonStepsCompleted` 约束。

不要跳过共享前缀。`/onboarding/agent` 和 `/onboarding/classic` 都依赖 `/onboarding` 已完成的通用步骤；如果 `commonStepsCompleted` 为 false，分支入口会回到 `/onboarding`。
