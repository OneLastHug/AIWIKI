# 文件：web/src/plugins/index.ts

## 一句话定位

`web/src/plugins/index.ts` 是 Dashboard 前端插件系统的统一出口文件，也就是 `@/plugins` 这个模块别名背后的聚合入口；它本身不承载业务逻辑，而是把插件注册、插件页面渲染、插件发现加载、slot 注入和类型定义集中转出，供 `main.tsx`、`App.tsx` 以及各内置页面以稳定 API 使用。

## 它暴露/定义了什么

这个文件只做 re-export，暴露内容可以分成五组：

第一组来自 `web/src/plugins/registry.ts`：`exposePluginSDK`、`getPluginComponent`、`onPluginRegistered`、`getRegisteredCount`。这些是插件全局 SDK 和注册表相关能力。插件 bundle 通过浏览器全局对象注册自身组件，宿主应用再通过 registry 查询和订阅。

第二组来自 `web/src/plugins/PluginPage.tsx`：`PluginPage`。它是插件路由页面的渲染容器，负责在插件组件尚未注册时显示 loading，在加载失败或未调用 register 时显示错误文案，在注册成功后渲染插件组件。

第三组来自 `web/src/plugins/usePlugins.ts`：`usePlugins`。它是 Dashboard 插件发现和加载的 React hook，负责拉取插件 manifest、注入 CSS、加载 JS bundle，并把已注册组件与 manifest 配对成运行时插件列表。

第四组来自 `web/src/plugins/slots.ts`：`PluginSlot`、`KNOWN_SLOT_NAMES`、`registerSlot`、`getSlotEntries`、`onSlotRegistered`、`unregisterPluginSlots`，以及类型 `KnownSlotName`。这是插件向应用壳和内置页面插入局部 UI 的 slot 系统。

第五组来自 `web/src/plugins/types.ts`：类型 `PluginManifest`、`RegisteredPlugin`。它们描述后端返回的插件 manifest 结构，以及 manifest 与 React component 绑定后的运行时插件对象。

因此，`index.ts` 定义的是模块边界，而不是算法边界。

## 谁调用它

最核心调用者是 `web/src/main.tsx` 和 `web/src/App.tsx`。

`web/src/main.tsx` 从 `./plugins` 导入 `exposePluginSDK`，并在 React 应用渲染前调用它。这个顺序很关键，因为外部插件 bundle 是通过 `<script>` 注入执行的，它们需要在执行时能访问 `window.__HERMES_PLUGINS__` 和 `window.__HERMES_PLUGIN_SDK__`。

`web/src/App.tsx` 从 `@/plugins` 导入 `PluginPage`、`PluginSlot`、`usePlugins`，并导入 `PluginManifest` 类型。`App` 用 `usePlugins()` 获取插件 manifest 和加载状态，用 manifest 构造侧边栏导航和路由；插件路由最终渲染为 `<PluginPage name={...} />`；应用壳中的多个位置通过 `<PluginSlot name="..." />` 允许插件注入内容。

此外，大量页面也通过 `@/plugins` 使用 `PluginSlot`，例如 `web/src/pages/AnalyticsPage.tsx`、`ModelsPage.tsx`、`LogsPage.tsx`、`ChatPage.tsx`、`DocsPage.tsx`、`SessionsPage.tsx`、`PluginsPage.tsx`、`SkillsPage.tsx`、`ConfigPage.tsx`、`EnvPage.tsx`、`CronPage.tsx`。这些页面不关心插件加载细节，只暴露插槽位置。

## 它调用谁

`index.ts` 自身没有运行时调用，只静态转发以下模块：

`./registry` 提供全局插件 SDK、插件组件注册表和注册事件订阅。

`./PluginPage` 提供插件 tab 页面渲染容器。

`./usePlugins` 提供插件 manifest 拉取、资源注入和组件解析流程。

`./slots` 提供 slot 注册表、slot 渲染组件和 slot 事件订阅。

`./types` 提供插件系统共享类型。

根据当前片段推断，这种聚合入口的目的，是让应用其他部分只依赖 `@/plugins` 这个稳定门面，而不是直接散落依赖插件系统内部文件。依据是 `App.tsx`、多个页面和 `main.tsx` 都通过 `@/plugins` 或 `./plugins` 导入，而不是直接导入 `registry.ts`、`slots.ts` 等内部模块。

## 核心流程

插件系统的启动流程大致如下：

1. `web/src/main.tsx` 启动时调用 `exposePluginSDK()`。该函数会在 `window` 上挂载 `__HERMES_PLUGINS__` 和 `__HERMES_PLUGIN_SDK__`。前者包含 `register`、`registerSlot`；后者包含 React、常用 hooks、API client、UI 组件、工具函数和 `useI18n`。

2. `App` 渲染时调用 `usePlugins()`。该 hook 首先通过 `api.getPlugins()` 拉取 Dashboard 插件 manifest 列表。manifest 包括插件名、标签、图标、tab 路径、entry、CSS、integrity 等信息。

3. manifest 到达后，`usePlugins()` 为声明了 CSS 的插件插入 `<link>`，再为每个插件 entry 插入 `<script>`。生产环境会避免重复加载同一个 base URL；开发环境会加 cache bust 参数，并在 cleanup 时移除脚本，方便重新执行。

4. 插件脚本执行后，应该调用 `window.__HERMES_PLUGINS__.register(name, Component)` 注册主页面组件，或调用 `registerSlot(pluginName, slotName, Component)` 注册插槽组件。registry 或 slot registry 更新后会通知订阅者。

5. `usePlugins()` 监听 `onPluginRegistered`，把 manifest 与 `getPluginComponent(manifest.name)` 取到的组件配对，形成 `RegisteredPlugin[]`。当所有 manifest 都解析成功，或等待超时后，加载状态结束。

6. `App` 使用 manifest 构建导航和路由。普通插件会新增 route；带 `tab.override` 的插件可以替换内置 route；`tab.hidden` 的插件可以不显示在侧边栏但仍保留可访问路由。路由元素通过 `PluginPage` 延迟读取插件组件。

7. 内置页面和应用壳中的 `<PluginSlot name="..." />` 会从 slot registry 读取对应组件并按注册顺序渲染。这样插件可以增强页面局部区域，而不必替换整个页面。

## 关键函数的高层作用

`exposePluginSDK` 是插件宿主和外部插件 bundle 之间的桥。它把宿主 React、UI 组件、API client、工具函数和注册函数挂到 `window` 上，避免插件各自打包 React 或重复实现基础组件，也保证插件注册协议统一。

`usePlugins` 是插件生命周期的前端调度器。它连接后端 manifest、浏览器资源加载和 registry 状态，将“可发现的插件”转化为“已注册、可渲染的插件”。它还处理 CSS 注入、JS 加载错误、未注册错误、SRI integrity 和加载超时。

`PluginPage` 是路由层的安全渲染壳。它通过 `useSyncExternalStore` 订阅 registry，避免脚本在 effect 之前完成注册时错过更新；它把插件组件可用、加载中、加载失败、脚本未注册这几种状态统一表现给用户。

`registerSlot` 和 `PluginSlot` 构成局部扩展机制。`registerSlot` 将某插件的组件放入指定 slot，并保证同一插件同一 slot 重复注册时后者替换前者；`PluginSlot` 订阅 slot registry，并在宿主页面对应位置渲染所有注册组件。

`getPluginComponent`、`onPluginRegistered`、`getRegisteredCount` 属于 registry 的基础查询和订阅工具。`getRegisteredCount` 当前从导出看更偏诊断或状态展示用途。

`KNOWN_SLOT_NAMES` 和 `KnownSlotName` 是 slot 名称约定。registry 接受任意字符串，但宿主只会在实际放置了 `<PluginSlot name="..." />` 的位置渲染内容；因此这个常量更多是文档化和类型提示边界。

## 修改风险

`index.ts` 的直接修改风险看似很低，因为它只是导出列表；但它是 `@/plugins` 的公共门面，风险主要来自导出兼容性。

删除或重命名导出会影响多个层级。`main.tsx` 依赖 `exposePluginSDK`，如果导出中断，插件全局 SDK 不会初始化，所有外部插件脚本可能无法注册。`App.tsx` 依赖 `PluginPage`、`PluginSlot`、`usePlugins` 和 `PluginManifest`，导出变化会直接破坏路由、导航和 slot 渲染。各内置页面大量依赖 `PluginSlot`，改动会造成页面级扩展点失效。

新增导出通常安全，但要注意不要把内部实现细节过度暴露成公共 API。一旦插件或页面开始依赖这些导出，后续重构成本会上升。

调整 `registry.ts` 相关导出时风险最高。插件 bundle 与宿主通过 `window.__HERMES_PLUGINS__.register`、`registerSlot` 形成运行时协议，这部分不是普通 TypeScript 编译期 API，错误可能只在浏览器加载插件后暴露。

调整 `usePlugins` 或 `PluginPage` 的导出关系时，要特别注意异步加载窗口。`App.tsx` 中对 `/chat` override 的处理依赖 `pluginsLoading`，如果插件加载状态过早结束，可能导致内置 chat host 先挂载，随后又被插件 override 替换，引发 PTY、WebSocket 或终端实例被意外销毁。

调整 slot 相关导出时，要检查所有页面中的 `<PluginSlot>` 是否仍能正常订阅更新。slot 机制允许插件晚于页面挂载后注册组件，如果订阅或重新渲染链路断开，表现会是插件已加载但 UI 不出现。

总体上，`web/src/plugins/index.ts` 应被视为 Dashboard 插件系统的稳定公共入口。修改它时优先保持向后兼容；如果必须改名或迁移导出，应同步更新 `main.tsx`、`App.tsx`、所有页面级 `PluginSlot` 使用点，以及任何依赖 `window.__HERMES_PLUGINS__` 协议的插件 bundle。
