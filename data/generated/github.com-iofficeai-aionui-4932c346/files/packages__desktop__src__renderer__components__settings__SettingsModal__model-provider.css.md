# 文件：packages/desktop/src/renderer/components/settings/SettingsModal/model-provider.css

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
/* Model settings provider action buttons (+ / - / edit)
 * Normal state merges with row background, hover/focus shows a block.
 */
.model-provider-action-btn.arco-btn {
  background-color: transparent !important;
  border-color: transparent !important;
  box-shadow: none !important;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;
}

/* Light mode: hover feedback should be visible */
[data-theme='light'] .model-provider-action-btn.arco-btn:hover,
[data-theme='light'] .model-provider-action-btn.arco-btn:focus-visible,
[data-theme='light'] .model-provider-action-btn.arco-btn:active {
  background-color: var(--fill-0) !important;
  border-color: var(--color-border-2) !important;
}

/* Dark mode: keep normal merged with row; highlight only on interaction */
[data-theme='dark'] .model-provider-action-btn.arco-btn:hover,
[data-theme='dark'] .model-provider-action-btn.arco-btn:focus-visible,
[data-theme='dark'] .model-provider-action-btn.arco-btn:active {
  background-color: var(--color-bg-1) !important;
}

```
