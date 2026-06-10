# 文件：ui-tui/src/domain/viewport.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { Msg } from '../types.js'

import { userDisplay } from './messages.js'

const upperBound = (offsets: ArrayLike<number>, target: number) => {
  let lo = 0
  let hi = offsets.length

  while (lo < hi) {
    const mid = (lo + hi) >> 1

    offsets[mid]! <= target ? (lo = mid + 1) : (hi = mid)
  }

  return lo
}

export const stickyPromptFromViewport = (
  messages: readonly Msg[],
  offsets: ArrayLike<number>,
  top: number,
  bottom: number,
  sticky: boolean
) => {
  if (sticky || !messages.length) {
    return ''
  }

  const first = Math.max(0, upperBound(offsets, top) - 1)
  const last = Math.max(first, upperBound(offsets, bottom) - 1)
  const visibleStart = Math.min(messages.length, first)
  const visibleEnd = Math.min(messages.length - 1, last)

  for (let i = visibleStart; i <= visibleEnd; i++) {
    if (messages[i]?.role === 'user') {
      return ''
    }
  }

  for (let i = Math.min(messages.length - 1, visibleStart - 1); i >= 0; i--) {
    if (messages[i]?.role !== 'user') {
      continue
    }

    return (offsets[i + 1] ?? (offsets[i] ?? 0) + 1) <= top
      ? userDisplay(messages[i]!.text.trim()).replace(/\s+/g, ' ').trim()
      : ''
  }

  return ''
}

```
