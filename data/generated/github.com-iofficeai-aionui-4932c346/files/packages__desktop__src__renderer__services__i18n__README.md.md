# 文件：packages/desktop/src/renderer/services/i18n/README.md

## 一句话定位
这是 renderer 进程里多语言能力的说明页，用来解释 `i18next` 在桌面端是怎么初始化、切换语言、加载语言包并与主进程保持同步的。根据当前片段推断，它更像是 `index.ts` 的配套说明，而不是单纯的“使用示例文档”。

## 它暴露/定义了什么
这份 README 本身不输出运行时代码，但它定义了这个服务的对外认知边界：支持哪些语言、如何在组件里通过 `useTranslation()` 取文案、如何通过 `changeLanguage()` 切换语言、以及新增翻译时应该遵守的键命名规则。结合 `index.ts` 看，真实暴露的能力包括默认 `i18n` 实例、`changeLanguage()`、`clearTranslationCache()`、`getLoadedLanguages()`，以及 `normalizeLanguageCode`、`SupportedLanguage` 等类型和工具导出。

## 谁调用它
严格说，README 不会被业务代码调用，但它服务的对象很明确：所有在 renderer 里使用 `react-i18next` 的页面、组件和 hook 都是它的阅读者。实际入口是 `packages/desktop/src/renderer/main.tsx`，这里直接 `import './services/i18n'`，说明 i18n 初始化会在渲染器启动时执行。语言切换交互主要来自 `packages/desktop/src/renderer/components/settings/LanguageSwitcher.tsx`、`packages/desktop/src/renderer/pages/login/index.tsx`，以及大量通过 `useTranslation()` 读取文案的组件。

## 它调用谁
README 主要引用并解释了外部依赖，而真正执行逻辑的是 `index.ts`。从代码看，它依赖 `i18next`、`react-i18next`、`@/common/config/configService`、`@/common/config/i18n-config.json`、`@/common/config/i18n` 和 `ipcBridge`。其中 `configService` 提供后端保存的语言配置，`ipcBridge.systemSettings.languageChanged` 用来接收主进程广播，`ensureAndSwitch()` 负责“先加载资源再切语言”的统一流程。

## 核心流程
初始化流程是这份文档最该关注的部分。渲染器启动时先同步加载默认语言和首选语言资源，避免首屏闪烁，然后 `initLanguage()` 等待 `configService.whenReady()`，拿到后端权威语言设置后再调用 `ensureAndSwitch()`。如果语言切换发生，`languageChanged` 事件会触发懒加载并补齐资源包，再同步写回 `localStorage`，保证下一次启动能快速命中。根据当前片段推断，这套设计同时兼顾了桌面端和 WebUI 场景，因为代码里明确避免使用 `i18next-browser-languagedetector`，而是改用 `localStorage`、注入语言和 `navigator.language` 作为启动提示。

## 关键函数的高层作用
`changeLanguage()` 是最重要的对外动作，它把切换语言、更新 `configService`、同步 `localStorage`、通知主进程这几步串起来。`ensureAndSwitch()` 是公共底座，负责按需加载资源并切换到目标语言，避免重复写同类逻辑。`getInitialLanguage()` 决定首次渲染时用什么语言，优先级会受后端启动状态影响。`loadLocaleModules()` 和 `getLocaleModules()` 负责缓存与回退合并，确保缺失键还能从默认语言补齐。`clearTranslationCache()`、`getLoadedLanguages()` 更偏开发与调试用途。

## 修改风险
这里的风险主要不是代码运行，而是文档和实现脱节。README 里仍停留在早期的 `src/renderer/i18n/`、双文件语言包示例，但当前实现已经变成多模块、多语言、按需加载的结构，真实路径是 `packages/desktop/src/renderer/services/i18n/`。如果后续新增语言、调整 `DEFAULT_LANGUAGE`、修改主进程同步协议，文档不更新就会误导维护者。另一类风险是语言包结构不一致：`mergeWithFallback()` 依赖对象层级稳定，缺键或模块名变更会直接影响回退行为和翻译完整性。
