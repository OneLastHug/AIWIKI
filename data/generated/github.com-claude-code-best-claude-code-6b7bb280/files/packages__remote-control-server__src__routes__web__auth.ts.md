# 文件：packages/remote-control-server/src/routes/web/auth.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { Hono } from 'hono'
import { storeBindSession } from '../../store'
import {
  resolveExistingWebSessionId,
  toWebSessionId,
} from '../../services/session'

const app = new Hono()

/** POST /web/bind — Bind a session to a UUID (no-login auth) */
app.post('/bind', async c => {
  const body = await c.req.json()
  const sessionId = body.sessionId
  // UUID can come from query param (api.js sends it in URL) or body
  const uuid = c.req.query('uuid') || body.uuid

  if (!sessionId || !uuid) {
    return c.json({ error: 'sessionId and uuid are required' }, 400)
  }

  const resolvedSessionId = resolveExistingWebSessionId(sessionId)
  if (!resolvedSessionId) {
    return c.json({ error: 'Session not found' }, 404)
  }

  storeBindSession(resolvedSessionId, uuid)
  return c.json({ ok: true, sessionId: toWebSessionId(resolvedSessionId) })
})

export default app

```
