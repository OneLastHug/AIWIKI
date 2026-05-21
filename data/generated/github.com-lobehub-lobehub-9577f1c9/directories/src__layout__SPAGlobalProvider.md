# 目录：src/layout/SPAGlobalProvider

## 它负责什么

这个目录定义的是整个 SPA 的“根级全局壳子”。它不是一个普通页面组件，而是把应用启动时必须先建立的全局环境一次性搭起来：主题、国际化、dayjs 语言、Ant Design 配置、服务端下发配置、查询层、认证态、全局弹层宿主、拖拽上传、分析埋点、开发态工具等，都在这里串起来。

从代码看，真正的入口是 [index.tsx](src/layout/SPAGlobalProvider/index.tsx:1)。它被 [src/utils/router.tsx](src/utils/router.tsx:131) 里的 `RouterRoot` 包裹全站路由，所以只要 SPA 启动，这个 provider 树就会先于所有业务页面加载。

## 关键组成

这个目录只有两个文件：

- [index.tsx](src/layout/SPAGlobalProvider/index.tsx:1)
- [Locale.tsx](src/layout/SPAGlobalProvider/Locale.tsx:1)

`index.tsx` 负责组装外层 provider，顺序很关键。它做了几件事：

1. `useLayoutEffect` 删除 `#loading-screen`，说明 SPA hydration 完成后要立刻清掉首屏占位。
2. 从 `window.__SERVER_CONFIG__` 读取服务端注入的 `SPAServerConfig`。
3. 从 `document.documentElement.lang` 取默认语言。
4. 计算 `isMobile`，根据服务端配置或全局编译常量决定移动端模式。
5. 逐层包裹：
   - `Locale`
   - `NextThemeProvider`
   - `AppTheme`
   - `ServerConfigStoreProvider`
   - `QueryProvider`
   - `AuthProvider`
   - `StoreInitialization`
   - `ServerVersionOutdatedAlert`（仅桌面端）
   - `FaviconProvider` / `DynamicFavicon`
   - `GroupWizardProvider`
   - `DragUploadProvider`
   - `LazyMotion`
   - `TooltipGroup`
   - `StyleProvider`
   - `LobeAnalyticsProviderWrapper`
   - `ModalHost` / `BaseModalHost` / `ToastHost` / `ContextMenuHost`
   - `ImportSettings`
   - 开发态的 `AgentMockDevtools`、`DevFeatureFlagPanel`

`Locale.tsx` 则专门处理语言相关的基础设施：

- 用 `createI18nNext(defaultLang)` 创建 i18n 实例。
- 通过 `getAntdLocale(lng)` 切换 Ant Design locale。
- 用 `normalizeDayjsLocale` 和动态加载器同步 dayjs locale。
- 用 `isRtlLang(lang)` 决定 `ConfigProvider.direction` 是 `ltr` 还是 `rtl`。
- 最后把所有子节点包到 `Editor` 和 `ConfigProvider` 里。

这里有一个很实用的细节：`Locale.tsx` 在 mount 时就会先执行一次 `updateDayjs(defaultLang)`，不等 i18n 初始化完成，目的是避免界面已经显示中文，但 dayjs 还在用英文相对时间。

## 上下游关系

上游输入主要有三类：

1. **HTML 模板注入的全局配置**
   - `src/app/spa/[variants]/[[...path]]/route.ts` 会把 `SPAServerConfig` 序列化后写进 `window.__SERVER_CONFIG__`。
   - [src/types/spaServerConfig.ts](src/types/spaServerConfig.ts:1) 定义了这个对象的结构。
   - [src/types/global.d.ts](src/types/global.d.ts:25) 让 TypeScript 认识 `window.__SERVER_CONFIG__`。

2. **路由根组件**
   - [src/utils/router.tsx](src/utils/router.tsx:131) 在 `RouterRoot` 里直接使用 `SPAGlobalProvider`。
   - 也就是说，它不是局部页面组件，而是应用级入口基础设施。

3. **语言和环境信息**
   - `document.documentElement.lang`
   - `__MOBILE__`
   - `isDesktop`
   - `__DEV__`

下游消费方也很明确：

- `AuthProvider`、`QueryProvider`、`StoreInitialization` 依赖这里先把上下文、配置和认证基础打好。
- `ServerConfigStoreProvider` 把服务端配置灌进 zustand store，后续很多功能会从这里读 feature flags 和 server config。
- `Locale` 影响整个应用的 `antd` 语言、文本方向和日期库表现。
- `ModalHost`、`ToastHost`、`ContextMenuHost` 是全局弹层出口，业务代码通常只负责触发，不负责自己挂宿主。
- `LobeAnalyticsProviderWrapper` 也会读取 `window.__SERVER_CONFIG__`，说明分析配置是通过这个全局配置流进来的。

根据当前片段推断，`src/layout/SPAGlobalProvider` 的定位就是“SPA 启动时的最外层运行时装配点”，而不是承载业务逻辑的地方。它的职责是把平台级能力统一初始化，保证后续页面只关心业务本身。

## 运行/调用流程

1. 服务端在生成 SPA HTML 时，把 `SPAServerConfig` 写入 `window.__SERVER_CONFIG__`。
2. 浏览器加载 SPA 入口后，`RouterRoot` 渲染 `SPAGlobalProvider`。
3. `SPAGlobalProvider` 先删除加载遮罩，避免首屏残留。
4. 它从 `window.__SERVER_CONFIG__`、`document.documentElement.lang` 等读取运行时环境。
5. `Locale` 先按默认语言启动：
   - 初始化 i18n
   - 同步 dayjs locale
   - 设置 Ant Design `ConfigProvider`
   - 设置 `direction`
6. 再进入外层主题和配置注入：
   - `NextThemeProvider` / `AppTheme`
   - `ServerConfigStoreProvider`
7. 接着初始化数据、认证和全局状态：
   - `QueryProvider`
   - `AuthProvider`
   - `StoreInitialization`
8. 最后挂上所有全局宿主和工具：
   - `TooltipGroup`
   - `LazyMotion`
   - `ModalHost` / `ToastHost` / `ContextMenuHost`
   - 开发态面板和导入设置

这个顺序不是随便排的。像 `Locale`、`ServerConfigStoreProvider`、`AuthProvider`、`QueryProvider` 这种基础上下文必须在业务组件之前完成，否则后续页面会拿不到语言、配置或认证状态。

## 小白阅读顺序

1. 先看 [index.tsx](src/layout/SPAGlobalProvider/index.tsx:1)，把整棵 provider 树认出来。
2. 再看 [Locale.tsx](src/layout/SPAGlobalProvider/Locale.tsx:1)，理解语言、dayjs、Antd 方向这三件事是怎么绑定的。
3. 接着看 [src/types/spaServerConfig.ts](src/types/spaServerConfig.ts:1)，弄清楚 `window.__SERVER_CONFIG__` 到底装了什么。
4. 然后回到 [src/app/spa/[variants]/[[...path]]/route.ts](src/app/spa/[variants]/[[...path]]/route.ts:212)，看这个配置是如何注入 HTML 的。
5. 最后看 [src/utils/router.tsx](src/utils/router.tsx:131)，确认它在路由根部如何被挂载。

## 常见误区

1. **把它当成普通页面组件**
   这不是某个页面的布局，而是 SPA 级别的启动壳。改动会影响全站。

2. **只看 `index.tsx` 不看 `Locale.tsx`**
   语言切换、dayjs locale 和 `antd` locale 都在 `Locale.tsx`，只看外层会漏掉最关键的国际化行为。

3. **忽略 `window.__SERVER_CONFIG__` 的来源**
   这里读取的是 HTML 模板注入值，不是前端自己“凭空生成”的。上游在 `route.ts`，类型在 `spaServerConfig.ts`。

4. **随意调整 provider 顺序**
   这个目录的顺序是有依赖关系的。比如 `AuthProvider`、`QueryProvider`、`ServerConfigStoreProvider` 往后挪，后面的组件可能拿不到上下文。

5. **误以为 `Locale` 只管翻译**
   它同时管 `ConfigProvider`、`direction`、dayjs locale 和 i18n 初始化，影响比表面上的文案切换大得多。

6. **忽略开发态分支**
   `AgentMockDevtools`、`DevFeatureFlagPanel` 只在 `__DEV__` 下出现，而且注释已经说明它们依赖 `node:fs`，不能简单搬到纯 SPA 环境里。
