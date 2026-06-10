# 文件：next/next-i18next.config.js

## 一句话定位

`next/next-i18next.config.js` 是前端 Next.js 应用的国际化中心配置文件，负责把“支持哪些语言、默认语言是什么、翻译资源从哪里加载、需要预加载哪些命名空间、React i18n 如何工作”等规则统一交给 `next-i18next`、Next.js 和页面级静态数据加载流程使用。

## 它暴露/定义了什么

这个文件通过 `module.exports` 暴露一个普通配置对象，核心字段包括：

`i18n` 定义 Next.js 级别的 locale 路由规则，`defaultLocale` 是 `en`，`locales` 列出 `en`、`zh`、`zhtw`、`ja`、`ko`、`fr`、`de` 等多语言代码。这个字段会被 `next.config.mjs` 读取后挂到 Next 配置上，从而影响 Next 的国际化路由、`locale` 参数和构建行为。

`localePath` 定义翻译 JSON 的读取路径。服务端环境使用 `./public/locales`，浏览器环境使用 `/locales`。这里通过 `typeof window === "undefined"` 区分运行端，避免服务端文件读取路径和客户端静态资源 URL 混用。

`defaultNS` 指定默认命名空间为 `common`。`ns` 列出应用会预加载的翻译命名空间，包括 `common`、`help`、`settings`、`chat`、`agent`、`errors`、`languages`、`drawer`、`indexPage`。这些名称对应 `next/public/locales/<language>/<namespace>.json` 这类资源文件。

`react.useSuspense: false` 关闭 React Suspense 式翻译加载，适合当前 Pages Router 和静态 props 注入的用法。`reloadOnPrerender` 在开发环境开启，用于预渲染时重新加载翻译资源。`saveMissing: true` 表示允许 i18next 记录缺失 key，仓库中能看到类似 `chat.missing.json`、`common.missing.json` 的文件，说明项目曾经或正在依赖缺失翻译收集能力。

## 谁调用它

直接调用者主要有三类。

第一类是 `next/next.config.mjs`。它导入 `nextI18NextConfig`，并把 `nextI18NextConfig.i18n` 传给 Next.js 的 `i18n` 配置。这让 Next 在路由层面认识这些语言代码，并在 `getStaticProps` 等上下文中提供 `locale`。

第二类是 `next/src/pages/_app.tsx`。它导入完整配置并传给 `appWithTranslation(MyApp, nextI18NextConfig)`，让整个 React 应用获得 `next-i18next` provider、`useTranslation` hook 的上下文和客户端语言切换能力。`_app.tsx` 还通过 `useTranslation()` 监听 `languageChanged`，同步更新 `document.documentElement.lang`。

第三类是多个页面的 `getStaticProps`，例如 `next/src/pages/index.tsx`、`next/src/pages/templates.tsx`、`next/src/pages/agent/index.tsx`、`next/src/pages/settings.tsx`。这些页面导入配置后，把 `nextI18NextConfig.ns` 传给 `serverSideTranslations(chosenLocale, nextI18NextConfig.ns)`，在构建或预渲染阶段把所需命名空间的翻译数据注入页面 props。

## 它调用谁

这个文件本身没有导入模块，也没有主动调用外部函数；它只是导出配置数据。运行时真正消费这些数据的是 `next-i18next`、`i18next`、`react-i18next` 和 Next.js。

根据当前片段推断，`localePath` 的服务端分支会被 `next-i18next/serverSideTranslations` 使用，用于从 `next/public/locales` 读取 JSON；客户端分支会被浏览器侧 i18next 资源加载逻辑使用，用于把 `/locales/<lng>/<ns>.json` 当作静态资源路径。依据是页面中直接调用 `serverSideTranslations`，而仓库存在完整的 `next/public/locales` 目录结构。

## 核心流程

应用启动或构建时，Next 先读取 `next.config.mjs`，其中的 `i18n: nextI18NextConfig.i18n` 把语言列表注册给 Next。这样 `/zh`、`/fr`、`/ja` 等 locale 维度会进入 Next 的路由和静态生成上下文。

页面预渲染时，`getStaticProps` 从上下文拿到 `locale`，再和项目自己的 `languages` 列表做一次校验，得到 `chosenLocale`。之后页面调用 `serverSideTranslations(chosenLocale, nextI18NextConfig.ns)`，按配置中的命名空间集合加载翻译资源，并作为 props 返回给页面。

客户端渲染时，`_app.tsx` 用 `appWithTranslation` 包装根组件，组件内就可以通过 `useTranslation("indexPage")`、`useTranslation("settings")` 或默认命名空间读取翻译文本。用户切换语言时，`useSettings.ts` 中的 `i18n.changeLanguage(language.code)` 会触发 `languageChanged`，`_app.tsx` 再把 HTML 根节点的 `lang` 属性同步为当前语言。

## 关键函数的高层作用

这个文件没有自定义函数，最关键的是几个配置字段背后的行为。

`i18n` 是路由层配置，决定 Next.js 认识哪些 locale，以及没有显式 locale 时落到哪个默认语言。它影响页面生成、路径匹配、`locale` 参数和语言前缀行为。

`localePath` 是资源定位策略，解决同一套翻译文件在服务端和浏览器端的访问差异。服务端需要本地文件系统路径，客户端需要公开静态路径。

`ns` 是翻译资源加载边界。页面的 `serverSideTranslations` 目前传入完整 `ns`，意味着相关页面会一次性预加载这些命名空间，而不是按页面精细拆分。这降低了页面缺 key 风险，但会增加初始翻译数据体积。

`react.useSuspense` 控制 React i18n 加载模式。当前关闭 Suspense，说明页面更依赖 SSR/SSG 阶段提前准备翻译数据，避免组件树因为翻译加载进入 Suspense 分支。

## 修改风险

修改 `locales` 风险较高。新增语言时，不仅要把语言代码加入这里，还要确保 `next/public/locales/<language>` 下存在所有 `ns` 对应的 JSON，并且项目自己的 `languages` 数据也包含同一 code。否则 Next 路由可能识别该语言，但页面 `chosenLocale` 校验会回退到 `en`，或运行时出现缺失翻译。

修改 `defaultLocale` 会影响默认路由、构建结果和未指定语言时的用户体验。若翻译资源或业务默认文案仍假设英文，切换默认语言可能带来 SEO、静态页面路径和 fallback 行为变化。

修改 `ns` 会直接影响 `serverSideTranslations` 预加载范围。删除命名空间可能导致组件中的 `useTranslation("drawer")`、`useTranslation("indexPage")` 等读不到 key；新增命名空间则需要补齐每个 locale 下的 JSON 文件。当前页面普遍加载完整 `nextI18NextConfig.ns`，所以命名空间变动属于全局影响。

修改 `localePath` 容易造成服务端构建正常但客户端加载失败，或反过来客户端能访问但服务端找不到文件。尤其是 `./public/locales` 和 `/locales` 分别服务于不同运行环境，不应简单合并。

开启 `debug` 或调整 `saveMissing` 主要影响开发诊断和缺失 key 收集。`saveMissing: true` 如果在生产环境没有配套后端保存策略，通常不会自动修复翻译缺失，但可能带来额外日志或请求行为；修改前应确认项目对 `.missing.json` 文件的维护方式。
