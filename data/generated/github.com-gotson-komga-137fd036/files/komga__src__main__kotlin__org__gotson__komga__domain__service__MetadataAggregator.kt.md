# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataAggregator.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package org.gotson.komga.domain.service

import org.gotson.komga.domain.model.BookMetadata
import org.gotson.komga.domain.model.BookMetadataAggregation
import org.springframework.stereotype.Service

@Service
class MetadataAggregator {
  fun aggregate(metadatas: Collection<BookMetadata>): BookMetadataAggregation {
    val authors = metadatas.flatMap { it.authors }.distinctBy { "${it.role}__${it.name}" }
    val tags = metadatas.flatMap { it.tags }.toSet()
    val (summary, summaryNumber) =
      metadatas
        .sortedBy { it.numberSort }
        .find { it.summary.isNotBlank() }
        ?.let {
          it.summary to it.number
        } ?: ("" to "")
    val releaseDate = metadatas.mapNotNull { it.releaseDate }.minOrNull()

    return BookMetadataAggregation(authors = authors, tags = tags, releaseDate = releaseDate, summary = summary, summaryNumber = summaryNumber)
  }
}

```
