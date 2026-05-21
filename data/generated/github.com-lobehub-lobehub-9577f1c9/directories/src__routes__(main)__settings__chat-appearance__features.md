# 目录：src/routes/(main)/settings/chat-appearance/features

## 它负责什么

`src/routes/(main)/settings/chat-appearance/features` 负责“聊天外观”设置页里的具体交互组件。它不是一个通用业务域目录，而是当前设置路由下的局部 feature，核心入口是：

`src/routes/(main)/settings/chat-appearance/features/ChatAppearance/index.tsx`

这个组件把用户可配置的聊天展示偏好组织成多个 `FormGroup`：

- 消息出现动画：`transitionMode`
- AI 回复流式输出时是否自动滚动：`enableAutoScrollOnStreaming`
- 聊天 Markdown 字号：`fontSize`
- 代码高亮主题：`highlighterTheme`
- Mermaid 图表主题：`mermaidTheme`

它同时提供对应的即时预览区域，让用户调整设置时能直接看到效果。例如字号变化会展示一段聊天 Markdown，代码主题变化会展示 TypeScript 高亮代码，Mermaid 主题变化会展示一张 sequence diagram。

从职责边界看，这个目录主要做 UI 表单、预览和用户设置写入，不直接处理数据库、服务端接口或路由注册。

## 关键组成

`ChatAppearance/index.tsx` 是总控组件。它使用 `useUserStore(settingsSelectors.currentSettings, isEqual)` 读取当前用户设置里的 `general` 配置，并通过 `useUserStore((s) => [s.setSettings, s.isUserStateInit])` 获取写入方法和初始化状态。

如果 `isUserStateInit` 还没完成，它返回 `Skeleton`，避免设置未加载时渲染空值或错误默认值。初始化完成后，它渲染五组设置项。

`handleChange` 是所有设置控件共用的保存逻辑：

```ts
const handleChange = async (key: string, value: any) => {
  setLoadingStates((prev) => ({ ...prev, [key]: true }));
  await setSettings({ general: { [key]: value } });
  setLoadingStates((prev) => ({ ...prev, [key]: false }));
};
```

这里的 `loadingStates` 是按字段名维护的局部 loading 状态。每个控件旁边都会在对应字段保存中显示 `Loader2Icon`。`setSettings({ general: { [key]: value } })` 表示它只更新 `general` 下的一个字段，而不是替换整个设置对象。

`ChatTransitionPreview.tsx` 负责动画模式预览。它内置一段 Markdown 文本 `data`，用 `setInterval` 模拟流式输出。`mode` 类型来自 `UserGeneralConfig['transitionMode']`，说明它和用户设置类型绑定。`mode === 'none'` 时初始内容会随机截取一段，并用更大的 chunk 更新；其他模式则从空字符串开始，每次追加 3 个字符。最终渲染到 `Markdown enableStream`，并在 `mode === 'fadeIn'` 时打开 `animated`。

`ChatPreview.tsx` 负责字号预览。它接收 `MarkdownProps['fontSize']`，用 `Markdown variant="chat"` 展示欢迎文案。文案来自 `welcome` namespace 的 `guide.defaultMessageWithoutCreate`，并注入 `BRANDING_NAME`。

`HighlighterPreview.tsx` 负责代码高亮主题预览。它使用 `Highlighter`，语言固定为 `ts`，关闭复制按钮和语言标签：

```tsx
<Highlighter copyable={false} language={'ts'} showLanguage={false} theme={theme}>
  {code}
</Highlighter>
```

`MermaidPreview.tsx` 负责 Mermaid 主题预览。它使用 `Mermaid` 渲染一段 sequence diagram，并用 `Center`、`Flexbox` 控制预览区域尺寸。

这个目录没有单独的 `index.ts` 聚合导出，默认通过 `ChatAppearance/index.tsx` 的 default export 被外部页面直接引用。

## 上下游关系

上游调用方主要有两个：

`src/routes/(main)/settings/chat-appearance/index.tsx` 是聊天外观设置页。它引入 `SettingHeader` 和 `ChatAppearance`，页面标题使用 `t('tab.chatAppearance')`，主体就是 `<ChatAppearance />`。

`src/routes/(main)/settings/appearance/index.tsx` 也引用了 `../chat-appearance/features/ChatAppearance`。根据当前片段推断，这说明聊天外观设置可能也被整合进更大的“外观”设置页中，用于复用同一套表单和预览逻辑。

状态上游是 `@/store/user`：

- `settingsSelectors.currentSettings` 提供当前用户设置
- `s.setSettings` 写入设置
- `s.isUserStateInit` 表示用户设置是否初始化完成

类型上游是 `@/types/user/settings`，其中 `UserGeneralConfig['transitionMode']` 限定了动画模式的合法类型。

UI 下游主要依赖 `@lobehub/ui` 和 `@lobehub/ui/base-ui`：

- `FormGroup`：每一项设置的容器
- `Segmented`：动画模式选择
- `SliderWithInput`：字号调整
- `Select`：高亮主题和 Mermaid 主题选择
- `Switch`：自动滚动开关
- `Markdown`：聊天文本预览和流式动画预览
- `Highlighter`：代码高亮预览
- `Mermaid`：图表预览
- `highlighterThemes`、`mermaidThemes`：主题选项来源

文案下游依赖 i18n：

- 设置页文案来自 `setting` namespace，例如 `settingChatAppearance.fontSize.title`
- 字号预览文案来自 `welcome` namespace 的 `guide.defaultMessageWithoutCreate`

这些设置的真正消费方不在目标目录内。根据当前片段和字段名推断，聊天页渲染 Markdown、代码块、Mermaid 图表、流式消息和自动滚动逻辑时，会读取 `userGeneralSettingsSelectors` 或 `currentSettings.general` 中的这些字段来决定最终表现。

## 运行/调用流程

用户进入聊天外观设置页后，页面组件先渲染 `SettingHeader`，再渲染 `ChatAppearance`。

`ChatAppearance` 挂载后先从 `useUserStore` 读取当前设置。如果用户设置尚未初始化，页面显示 `Skeleton`。初始化完成后，组件拿到 `general` 配置并渲染每个设置组。

用户修改某个控件时，例如切换 `transitionMode`：

1. `Segmented` 触发 `onChange`
2. 调用 `handleChange('transitionMode', value)`
3. `loadingStates.transitionMode` 被设为 `true`
4. 调用 `setSettings({ general: { transitionMode: value } })`
5. 保存完成后 `loadingStates.transitionMode` 被设为 `false`
6. 因为 `general.transitionMode` 变化，`ChatTransitionPreview` 的 `key` 也变化，预览组件会重新挂载
7. 新的预览按新的动画模式重新模拟流式输出

其他设置流程类似。`fontSize` 变化后传给 `ChatPreview`，`highlighterTheme` 变化后传给 `HighlighterPreview`，`mermaidTheme` 变化后传给 `MermaidPreview`。其中主题预览也使用 `key={general.highlighterTheme}` 或 `key={general.mermaidTheme}`，确保主题切换时预览组件完整刷新。

`enableAutoScrollOnStreaming` 比较特殊，它没有预览内容，`FormGroup` 的 children 是 `{null}`。这是因为自动滚动行为需要真实聊天流式输出场景才能观察，当前设置页只提供开关本身。

## 小白阅读顺序

1. 先看 `src/routes/(main)/settings/chat-appearance/index.tsx`  
   这个文件最简单，只负责说明页面标题和主体组件从哪里来。读完能知道 `ChatAppearance` 是页面核心。

2. 再看 `ChatAppearance/index.tsx`  
   重点关注三件事：如何从 `useUserStore` 读设置、如何通过 `handleChange` 写设置、每个 `FormGroup` 对应哪个 `general` 字段。

3. 接着看 `ChatPreview.tsx`  
   它是最简单的预览组件，只展示 `Markdown fontSize` 如何生效，适合理解“设置值传给预览组件”的模式。

4. 再看 `ChatTransitionPreview.tsx`  
   这是目录里逻辑最多的文件。重点理解 `useState`、`useMemo`、`useEffect` 如何模拟一段消息逐步输出，以及 `mode` 如何影响动画表现。

5. 最后看 `HighlighterPreview.tsx` 和 `MermaidPreview.tsx`  
   这两个文件结构类似，都是把主题值传给底层 `@lobehub/ui` 组件，适合理解代码高亮和 Mermaid 主题设置的下游表现。

6. 如果继续向外追，可以看 `src/store/user/slices/settings/selectors/general.ts`  
   这里能看到 `fontSize`、`highlighterTheme`、`mermaidTheme`、`transitionMode`、`enableAutoScrollOnStreaming` 这些字段在用户设置选择器层的读取方式。

## 常见误区

不要把这个目录理解成全局 `src/features` 下的业务模块。它实际位于 `src/routes/(main)/settings/chat-appearance/features`，是设置路由内部的局部组件目录。按照仓库新约定，复杂业务逻辑通常更推荐沉到 `src/features/<Domain>/`，但这里当前代码仍是路由内 feature 组织方式。

不要以为 `ChatAppearance` 自己实现了聊天渲染逻辑。它只负责设置页表单和预览；真正聊天窗口里的 Markdown 渲染、流式输出、自动滚动等行为应在聊天相关模块中消费这些设置。

不要把 `loadingStates` 当成全局保存状态。它只是当前组件内按字段维护的小型 UI 状态，用于显示某个设置项正在保存。

不要忽略 `isUserStateInit`。如果直接在设置未初始化时读取 `general.fontSize`、`general.transitionMode` 等字段，可能会出现预览和控件值不稳定的问题。这里先渲染 `Skeleton` 是为了等用户设置准备好。

不要误解 `key={general.transitionMode}`、`key={general.highlighterTheme}`、`key={general.mermaidTheme}`。这些 `key` 不是列表渲染需要，而是故意让预览组件在关键设置变化时重新挂载，从而重启动画或刷新主题效果。

不要以为 `enableAutoScrollOnStreaming ?? true` 表示设置一定已经保存为 `true`。这只是 UI 层在字段为空时采用默认开启显示；真正保存只有用户切换 `Switch` 后才会调用 `setSettings`。

不要把预览里的英文 Markdown、TypeScript 示例、Mermaid 示例当作真实业务数据。它们都是本地写死的演示内容，用来帮助用户观察视觉效果。
