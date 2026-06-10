# 文件：ui-tui/src/domain/providers.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
export const providerDisplayNames = (providers: readonly { name: string; slug: string }[]): string[] => {
  const counts = new Map<string, number>()

  for (const p of providers) {
    counts.set(p.name, (counts.get(p.name) ?? 0) + 1)
  }

  return providers.map(p =>
    (counts.get(p.name) ?? 0) > 1 && p.slug && p.slug !== p.name ? `${p.name} (${p.slug})` : p.name
  )
}

```
