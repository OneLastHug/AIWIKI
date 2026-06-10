# 文件：ui-tui/src/domain/roles.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { Theme } from '../theme.js'
import type { Role } from '../types.js'

export const ROLE: Record<Role, (t: Theme) => { body: string; glyph: string; prefix: string }> = {
  assistant: t => ({ body: t.color.text, glyph: t.brand.tool, prefix: t.color.border }),
  system: t => ({ body: '', glyph: '·', prefix: t.color.muted }),
  tool: t => ({ body: t.color.muted, glyph: '⚡', prefix: t.color.muted }),
  user: t => ({ body: t.color.label, glyph: t.brand.prompt, prefix: t.color.label })
}

```
