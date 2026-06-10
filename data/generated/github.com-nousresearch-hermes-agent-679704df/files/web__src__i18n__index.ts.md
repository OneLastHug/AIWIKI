# 文件：web/src/i18n/index.ts

## 一句话定位

`web/src/i18n/index.ts` 是 Web 前端国际化模块的公共出口文件，也就是 i18n 子系统的 barrel entry。它本身不实现翻译逻辑，而是把 `I18nProvider`、`useI18n`、`LOCALE_META` 以及核心类型 `Locale`、`Translations` 统一转发给业务页面、组件和插件层使用。

## 它暴露/定义了什么

该文件只包含两类导出：

```ts
export { I18nProvider, useI18n, LOCALE_META } from "./context";
export type { Locale, Translations } from "./types";
```

它暴露的运行时对象来自 `web/src/i18n/context.tsx`：

`I18nProvider` 是 React Context Provider，负责保存当前语言、提供翻译字典、持久化语言选择。

`useI18n` 是消费 i18n context 的 hook，业务组件通过它取得 `{ locale, setLocale, t }`。

`LOCALE_META` 是语言元数据表，当前主要提供每种语言的本地名称，例如 `English`、`简体中文`、`繁體中文` 等，用于语言选择器展示。

它暴露的类型来自 `web/src/i18n/types.ts`：

`Locale` 是受支持语言代码的联合类型，包括 `en`、`zh`、`zh-hant`、`ja`、`de`、`es`、`fr`、`tr`、`uk`、`af`、`ko`、`it`、`ga`、`pt`、`ru`、`hu`。

`Translations` 定义完整翻译对象结构，约束所有语言文件必须提供一致的 key，例如 `common`、`app`、`status`、`sessions`、`analytics`、`models`、`logs` 等分区。

## 谁调用它

最关键的调用点是 `web/src/main.tsx`，它从 `./i18n` 导入 `I18nProvider`，并把整个应用包在 provider 内：

`BrowserRouter` 之下、`ThemeProvider` 与 `SystemActionsProvider` 之外的应用树，都能读取当前语言上下文。

大量页面和组件通过别名入口 `@/i18n` 导入 `useI18n`，例如 `web/src/App.tsx`、`web/src/pages/AnalyticsPage.tsx`、`web/src/pages/ModelsPage.tsx`、`web/src/pages/ConfigPage.tsx`、`web/src/pages/SessionsPage.tsx`、`web/src/pages/LogsPage.tsx`、`web/src/pages/ChatPage.tsx`、`web/src/components/ThemeSwitcher.tsx`、`web/src/components/OAuthLoginModal.tsx` 等。

`web/src/components/LanguageSwitcher.tsx` 同时使用了 `LOCALE_META` 和 `Locale`，用于渲染语言列表、标记当前语言、调用 `setLocale` 切换语言。它的 `useI18n` 当前直接从 `@/i18n/context` 导入，但 `LOCALE_META` 和 `Locale` 仍通过本文件导出。

插件相关代码也会用到它，例如 `web/src/plugins/registry.ts` 导入 `useI18n`，`web/src/plugins/PluginPage.tsx` 导入 `useI18n` 和 `Translations`。这说明该入口不只是应用内部页面使用，也参与插件 UI 的本地化能力暴露。

## 它调用谁

`index.ts` 自身只调用 TypeScript/ES Module 的 re-export 机制，不执行函数、不创建对象、不访问浏览器 API。

它依赖两个邻近模块：

`web/src/i18n/context.tsx` 提供运行时国际化上下文。该文件进一步导入 React 的 `createContext`、`useContext`、`useState`、`useCallback`，以及各语言包 `en`、`zh`、`zh-hant`、`ja`、`de`、`es`、`fr`、`tr`、`uk`、`af`、`ko`、`it`、`ga`、`pt`、`ru`、`hu`。

`web/src/i18n/types.ts` 提供类型约束。它不参与运行时 bundle 的实际逻辑，但通过 `export type` 让调用方能拿到统一的语言代码和翻译结构定义。

## 核心流程

应用启动时，`web/src/main.tsx` 从 `./i18n` 取得 `I18nProvider`，把 React 应用树包起来。`I18nProvider` 初始化时会调用 `getInitialLocale`，优先从 `localStorage` 的 `hermes-locale` 读取语言；如果读取失败、浏览器隐私模式阻止访问，或存储值不是 `Locale` 支持范围内的语言，则回退到 `en`。

运行过程中，页面组件通过 `useI18n` 拿到 `t`，也就是当前语言对应的 `Translations` 对象。组件不需要知道具体语言文件在哪里，只需要访问 `t.common.save`、`t.app.nav.sessions` 之类的稳定 key。

当用户在 `LanguageSwitcher` 中选择语言时，组件调用 `setLocale(code)`。`context.tsx` 中的 `setLocale` 更新 React state，并把语言代码写回 `localStorage`。state 更新后，provider 的 `value.t` 改为 `TRANSLATIONS[locale]`，依赖 `useI18n` 的组件随 React 重新渲染，界面文本切换到新语言。

因此，`index.ts` 处在这个流程的入口层：它不参与状态更新，但决定外部模块通过哪个稳定路径拿到 provider、hook、元数据和类型。

## 关键函数的高层作用

`I18nProvider` 是国际化系统的核心边界。它维护 `locale` 状态，计算当前语言的 `t`，并通过 React Context 向下游组件提供。它还负责把用户语言偏好写入 `localStorage`，使刷新页面后仍保留选择。

`useI18n` 是业务层最常用的读取接口。它隐藏了 `I18nContext` 的实现细节，让页面组件只关心当前语言、切换函数和翻译对象。

`getInitialLocale` 是初始化辅助逻辑。它负责从持久化存储读取语言并做合法性校验，失败时回退英文。

`isLocale` 是类型守卫，用 `SUPPORTED_LOCALES` 校验任意字符串是否属于受支持语言集合。

`LOCALE_META` 不是函数，但对 UI 很关键。它把语言选择器展示文案和翻译内容分开维护，避免语言列表依赖当前界面语言；根据当前片段推断，这也是为了让用户即使看不懂当前 UI，也能通过本地语言名识别目标语言。

## 修改风险

`index.ts` 看似只有两行，但它是 i18n 模块的公共 API。删除或改名导出会影响大量 `@/i18n` 调用点，尤其是页面、组件、插件注册层和 `main.tsx`。这类破坏通常会在 TypeScript 编译阶段暴露，但如果路径别名或插件代码未被完整类型检查覆盖，可能延迟到运行时才发现。

新增语言时，不能只改 `index.ts`。需要同步更新 `Locale` 联合类型、对应语言文件、`context.tsx` 中的语言包 import、`TRANSLATIONS` 映射和 `LOCALE_META`。如果 `Locale` 包含某语言但 `TRANSLATIONS` 没有对应项，provider 取 `TRANSLATIONS[locale]` 时会出现不完整或未定义翻译；如果 `LOCALE_META` 漏项，语言选择器也会出现类型或展示问题。

修改 `Translations` 类型风险较高，因为它约束所有语言文件。新增必填字段会要求每个语言包同步补齐；删除或重命名字段会影响所有访问 `t.xxx` 的组件。这里的类型约束是维护翻译一致性的主要防线，但也意味着结构调整的影响面很大。

不建议让业务组件绕过 `@/i18n` 直接依赖具体语言文件。当前设计把 `index.ts` 作为稳定门面，能减少模块路径扩散，并让未来重构 `context.tsx` 或语言包组织方式时保留外部 API。对于 `LanguageSwitcher` 当前直接从 `@/i18n/context` 导入 `useI18n` 的情况，根据当前片段推断是局部实现选择；若要统一入口，可以改为从 `@/i18n` 导入，但需要确认是否存在循环依赖或历史打包原因。
