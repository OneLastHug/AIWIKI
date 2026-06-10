# 文件：ui-tui/src/domain/paths.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
export const shortCwd = (cwd: string, max = 28) => {
  const h = process.env.HOME
  const p = h && cwd.startsWith(h) ? `~${cwd.slice(h.length)}` : cwd

  return p.length <= max ? p : `…${p.slice(-(max - 1))}`
}

export const fmtCwdBranch = (cwd: string, branch: null | string, max = 40) => {
  if (!branch) {
    return shortCwd(cwd, max)
  }

  const tag = ` (${branch.length > 16 ? `…${branch.slice(-15)}` : branch})`

  return `${shortCwd(cwd, Math.max(8, max - tag.length))}${tag}`
}

```
