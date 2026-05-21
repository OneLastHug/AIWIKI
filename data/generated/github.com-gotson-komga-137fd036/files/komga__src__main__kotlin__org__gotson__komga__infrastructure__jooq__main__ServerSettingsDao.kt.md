# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ServerSettingsDao.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package org.gotson.komga.infrastructure.jooq.main

import org.gotson.komga.infrastructure.jooq.SplitDslDaoBase
import org.gotson.komga.jooq.main.Tables
import org.jooq.DSLContext
import org.springframework.beans.factory.annotation.Qualifier
import org.springframework.stereotype.Component

@Component
class ServerSettingsDao(
  dslRW: DSLContext,
  @Qualifier("dslContextRO") dslRO: DSLContext,
) : SplitDslDaoBase(dslRW, dslRO) {
  private val s = Tables.SERVER_SETTINGS

  fun <T> getSettingByKey(
    key: String,
    clazz: Class<T>,
  ): T? =
    dslRO
      .select(s.VALUE)
      .from(s)
      .where(s.KEY.eq(key))
      .fetchOneInto(clazz)

  fun saveSetting(
    key: String,
    value: String,
  ) {
    dslRW
      .insertInto(s)
      .values(key, value)
      .onDuplicateKeyUpdate()
      .set(s.VALUE, value)
      .execute()
  }

  fun saveSetting(
    key: String,
    value: Boolean,
  ) {
    saveSetting(key, value.toString())
  }

  fun saveSetting(
    key: String,
    value: Int,
  ) {
    saveSetting(key, value.toString())
  }

  fun deleteSetting(key: String) {
    dslRW.deleteFrom(s).where(s.KEY.eq(key)).execute()
  }

  fun deleteAll() {
    dslRW.deleteFrom(s).execute()
  }
}

```
