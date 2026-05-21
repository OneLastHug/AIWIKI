# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/MetadataApplierTest.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package org.gotson.komga.domain.service

import org.assertj.core.api.Assertions.assertThat
import org.gotson.komga.domain.model.Author
import org.gotson.komga.domain.model.BookMetadata
import org.gotson.komga.domain.model.BookMetadataPatch
import org.gotson.komga.domain.model.SeriesMetadata
import org.gotson.komga.domain.model.SeriesMetadataPatch
import org.gotson.komga.domain.model.WebLink
import org.junit.jupiter.api.Nested
import org.junit.jupiter.api.Test
import java.net.URI
import java.time.LocalDate

class MetadataApplierTest {
  private val metadataApplier = MetadataApplier()

  @Nested
  inner class Book {
    @Test
    fun `given locked metadata when applying patch then metadata is not changed`() {
      val metadata =
        BookMetadata(
          title = "title",
          number = "1",
          numberSort = 1F,
          titleLock = true,
          summaryLock = true,
          numberLock = true,
          numberSortLock = true,
          releaseDateLock = true,
          authorsLock = true,
          tagsLock = true,
          isbnLock = true,
          linksLock = true,
        )

      val patch =
        BookMetadataPatch(
          title = "new title",
          summary = "new summary",
          number = "2",
          numberSort = 2F,
          releaseDate = LocalDate.of(2020, 12, 2),
          authors = listOf(Author("Marcel", "writer")),
          isbn = "9782811632397",
          links = listOf(WebLink("Comixology", URI("[URL已移除]"))),
          tags = setOf("tag1", "tag2"),
        )

      val patched = metadataApplier.apply(patch, metadata)

      assertThat(patched.title).isEqualTo(metadata.title)
      assertThat(patched.number).isEqualTo(metadata.number)
      assertThat(patched.numberSort).isEqualTo(metadata.numberSort)
      assertThat(patched.summary).isEqualTo("")
      assertThat(patched.authors).isEmpty()
      assertThat(patched.releaseDate).isNull()
      assertThat(patched.tags).isEmpty()
      assertThat(patched.isbn).isEqualTo("")
      assertThat(patched.links).isEmpty()
      assertThat(patched.tags).isEmpty()
    }

    @Test
    fun `given unlocked metadata when applying patch then metadata is changed`() {
      val metadata =
        BookMetadata(
          title = "title",
          number = "1",
          numberSort = 1F,
        )

      val patch =
        BookMetadataPatch(
          title = "new title",
          summary = "new summary",
          number = "2",
          numberSort = 2F,
          releaseDate = LocalDate.of(2020, 12, 2),
          authors = listOf(Author("Marcel", "writer")),
          isbn = "9782811632397",
          links = listOf(WebLink("Comixology", URI("[URL已移除]"))),
          tags = setOf("tag1", "tag2"),
        )

      val patched = metadataApplier.apply(patch, metadata)

      assertThat(patched.title).isEqualTo(patch.title)
      assertThat(patched.number).isEqualTo(patch.number)
      assertThat(patched.numberSort).isEqualTo(patch.numberSort)
      assertThat(patched.summary).isEqualTo(patch.summary)
      assertThat(patched.authors)
        .hasSize(1)
        .containsExactlyInAnyOrder(
          Author("Marcel", "writer"),
        )
      assertThat(patched.releaseDate).isEqualTo(patch.releaseDate)
      assertThat(patched.isbn).isEqualTo(patch.isbn)
      assertThat(patched.links)
        .hasSize(1)
        .containsExactlyInAnyOrder(
          WebLink("Comixology", URI("[URL已移除]")),
        )
      assertThat(patched.tags as Iterable<String>)
        .hasSize(2)
        .containsExactlyInAnyOrder("tag1", "tag2")
    }
  }

  @Nested
  inner class Series {
    @Test
    fun `given locked metadata when applying patch then metadata is not changed`() {
      val metadata =
        SeriesMetadata(
          title = "title",
          statusLock = true,
          titleLock = true,
          titleSortLock = true,
          summaryLock = true,
          readingDirectionLock = true,
          publisherLock = true,
          ageRatingLock = true,
          languageLock = true,
          genresLock = true,
          tagsLock = true,
          totalBookCountLock = true,
        )

      val patch =
        SeriesMetadataPatch(
          title = "new title",
          titleSort = "new title sort",
          status = SeriesMetadata.Status.ENDED,
          summary = "new summary",
          readingDirection = SeriesMetadata.ReadingDirection.VERTICAL,
          publisher = "new publisher",
          ageRating = 12,
          language = "en",
          genres = setOf("shonen"),
          totalBookCount = 12,
          collections = emptySet(),
        )

      val patched = metadataApplier.apply(patch, metadata)

      assertThat(patched.title).isEqualTo(metadata.title)
      assertThat(patched.titleSort).isEqualTo(metadata.titleSort)
      assertThat(patched.status).isEqualTo(metadata.status)
      assertThat(patched.summary).isEqualTo(metadata.summary)
      assertThat(patched.readingDirection).isEqualTo(metadata.readingDirection)
      assertThat(patched.publisher).isEqualTo(metadata.publisher)
      assertThat(patched.ageRating).isEqualTo(metadata.ageRating)
      assertThat(patched.language).isEqualTo(metadata.language)
      assertThat(patched.genres).isEmpty()
      assertThat(patched.totalBookCount).isNull()
      assertThat(patched.tags).isEmpty()
    }

    @Test
    fun `given unlocked metadata when applying patch then metadata is changed`() {
      val metadata =
        SeriesMetadata(
          title = "title",
        )

      val patch =
        SeriesMetadataPatch(
          title = "new title",
          titleSort = "new title sort",
          status = SeriesMetadata.Status.ENDED,
          summary = "new summary",
          readingDirection = SeriesMetadata.ReadingDirection.VERTICAL,
          publisher = "new publisher",
          ageRating = 12,
          language = "en",
          genres = setOf("shonen"),
          totalBookCount = 12,
          collections = emptySet(),
        )

      val patched = metadataApplier.apply(patch, metadata)

      assertThat(patched.title).isEqualTo(patch.title)
      assertThat(patched.titleSort).isEqualTo(patch.titleSort)
      assertThat(patched.status).isEqualTo(patch.status)
      assertThat(patched.summary).isEqualTo(patch.summary)
      assertThat(patched.readingDirection).isEqualTo(patch.readingDirection)
      assertThat(patched.publisher).isEqualTo(patch.publisher)
      assertThat(patched.ageRating).isEqualTo(patch.ageRating)
      assertThat(patched.language).isEqualTo(patch.language)
      assertThat(patched.totalBookCount).isEqualTo(patch.totalBookCount)
      assertThat(patched.genres as Iterable<String>)
        .hasSize(1)
        .containsExactlyInAnyOrder("shonen")
      assertThat(patched.tags).isEmpty()
    }
  }
}

```
