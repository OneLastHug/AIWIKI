# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/SearchIndexController.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package org.gotson.komga.interfaces.scheduler

import io.github.oshai.kotlinlogging.KotlinLogging
import org.gotson.komga.application.tasks.HIGHEST_PRIORITY
import org.gotson.komga.application.tasks.TaskEmitter
import org.gotson.komga.infrastructure.search.LuceneEntity
import org.gotson.komga.infrastructure.search.LuceneHelper
import org.springframework.boot.context.event.ApplicationReadyEvent
import org.springframework.context.annotation.Profile
import org.springframework.context.event.EventListener
import org.springframework.stereotype.Component

private val logger = KotlinLogging.logger {}

@Profile("!test")
@Component
class SearchIndexController(
  private val luceneHelper: LuceneHelper,
  private val taskEmitter: TaskEmitter,
) {
  @EventListener(ApplicationReadyEvent::class)
  fun createIndexIfNoneExist() {
    if (!luceneHelper.indexExists()) {
      logger.info { "Lucene index not found, trigger rebuild" }
      taskEmitter.rebuildIndex(HIGHEST_PRIORITY)
    } else {
      val indexVersion = luceneHelper.getIndexVersion()
      logger.info { "Lucene index version: $indexVersion" }
      when {
        indexVersion < 6 -> {
          taskEmitter.upgradeIndex(HIGHEST_PRIORITY) // upgrade index to Lucene 9.x
          taskEmitter.rebuildIndex(HIGHEST_PRIORITY, setOf(LuceneEntity.Series))
        }

        indexVersion < 8 -> taskEmitter.rebuildIndex(HIGHEST_PRIORITY, setOf(LuceneEntity.Series))
      }
    }
  }
}

```
