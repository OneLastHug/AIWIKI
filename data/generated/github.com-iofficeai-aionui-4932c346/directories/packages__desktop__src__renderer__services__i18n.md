# 目录：packages/desktop/src/renderer/services/i18n

## 它负责什么

这个目录是渲染层的国际化服务中心，负责把 `i18next`、`react-i18next`、配置服务和本地语言包串起来，让界面在启动、切换语言、跨窗口同步时都能拿到正确的翻译资源。根据当前片段推断，它不仅提供“翻译读取”的能力，还负责“语言状态管理”：决定初始语言、按需加载语言模块、写回 `configService`，并把语言变化同步给主进程和其他渲染端。

它的角色不是简单放几份翻译文件，而是渲染层 i18n 的运行时入口。也就是说，这里是“语言包数据”“初始化逻辑”“切换逻辑”“同步逻辑”四件事的汇合点。

## 直接子目录地图

这个目录本身很小，核心分两类内容：

1. `locales/`  
   这里是语言资源聚合区，每种语言一个子目录，例如 `en-US`、`zh-CN`、`ja-JP`、`ko-KR`、`tr-TR`、`ru-RU`、`uk-UA`、`pt-BR`、`zh-TW`。  
   每个语言目录里不是单一大 JSON，而是按业务域拆成多个模块文件，例如 `common.json`、`conversation.json`、`settings.json`、`codex.json`、`agent.json`、`tools.json` 等，再由该语言目录下的 `index.ts` 统一导出。

2. 目录级文件  
   `index.ts`、`i18n-keys.d.ts`、`README.md`。  
   其中 `index.ts` 是真正的运行入口，`i18n-keys.d.ts` 是自动生成的类型声明，`README.md` 是旧式说明文档。

从结构上看，这里没有再往下分“功能子系统”目录，重点是语言维度，而不是业务维度。

## 关键入口

最关键的入口是 `index.ts`。它做了几件事：

- 静态导入所有语言的 `locales/*/index.ts`，确保打包后仍然能切换语言；
- 从 `i18n-config.json` 读取支持语言列表；
- 从 `@/common/config/i18n` 引入 `DEFAULT_LANGUAGE`、`normalizeLanguageCode`、`mergeWithFallback`、`ensureAndSwitch` 等通用能力；
- 用 `i18next.use(initReactI18next).init(...)` 完成初始化；
- 暴露 `changeLanguage()` 给业务代码调用；
- 暴露 `clearTranslationCache()`、`getLoadedLanguages()` 这类维护性 API。

另一个关键文件是 `locales/<lang>/index.ts`。它不做业务逻辑，只负责把该语言下各个 JSON 模块聚合成一个对象，供 `index.ts` 统一装配进 `i18next`。

`i18n-keys.d.ts` 也是重要入口之一，但它属于类型层而不是运行层。它由脚本生成，用来约束翻译键，避免组件里随手拼错 key。

## 主流程位置

主流程可以按“启动 -> 定位初始语言 -> 初始化资源 -> 监听变化 -> 切换同步”理解：

1. 模块加载时，`index.ts` 先把默认语言和其他语言包静态引入。
2. `getInitialLanguage()` 负责决定首屏语言。它会综合 `localStorage`、`window.__initialLanguage`、`navigator.language`，并且在后端启动失败时切换一套优先级。这里体现了它对 Electron/WebUI 双环境的兼容。
3. `i18n.init(...)` 用初始语言和 fallback 资源先跑起来，目标是避免首屏闪烁和资源缺失。
4. `initLanguage()` 等 `configService.whenReady()` 后，再拿后端保存的语言作为权威值，调用 `ensureAndSwitch()` 完成正式切换。
5. `i18n.on('languageChanged', ...)` 监听语言变化，若资源未加载则调用 `loadLocaleModules()` 动态补齐。
6. `ipcBridge.systemSettings.languageChanged.on(...)` 监听主进程广播，保证其他窗口或 WebUI 也能同步更新。
7. `changeLanguage()` 是业务层最常用的改语言接口，它会同时更新 i18n、配置服务、`localStorage`，并通知主进程。

如果把它理解成流水线，入口是 `index.ts`，语言资源装配在 `locales/<lang>/index.ts`，权威状态则由 `configService` 和 IPC 共同维持。

## 推荐阅读顺序

1. 先读 `index.ts`，看初始化和切换闭环。
2. 再读 `locales/en-US/index.ts`，理解每种语言的模块拼装方式。
3. 然后看 `i18n-keys.d.ts`，建立“翻译键是如何被类型化”的印象。
4. 最后看 `README.md`，但要带着“文档可能滞后”的意识阅读。

如果你想继续往上追，下一步应当去看 `@/common/config/i18n` 和 `configService`，因为这个目录本身只是渲染层外壳，真正的规范和辅助函数大概率在公共配置层。

## 常见误区

1. 把它当成单纯的翻译文件夹。  
   实际上它同时承担运行时初始化、懒加载、缓存、跨窗口同步和配置落盘。

2. 以为语言切换只改 `i18next` 就够了。  
   这里明确还要同步 `configService`、`localStorage` 和 `ipcBridge`，否则桌面端、WebUI、其他窗口可能不同步。

3. 误读 `README.md`。  
   当前片段里，README 仍写着 `src/renderer/i18n/`、`zh-CN.json`、`en-US.json` 这种旧结构；而实际目录已经是 `locales/<lang>/` 加多模块 JSON 的组织方式。根据当前片段推断，这是历史文档未同步更新。

4. 只关注默认语言。  
   这里显式静态导入了多种语言，不只是中英文。支持语言列表由 `i18n-config.json` 决定，实际可用范围要以配置为准。

5. 低估 `i18n-keys.d.ts` 的作用。  
   它不是装饰性文件，而是约束翻译键正确性的类型边界；改了语言模块后，类型生成链路往往也要一起看。
