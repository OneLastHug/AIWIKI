# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner/ListUsersRunner.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package org.gotson.komga.interfaces.apprunner

import io.github.oshai.kotlinlogging.KotlinLogging
import org.gotson.komga.domain.persistence.KomgaUserRepository
import org.springframework.boot.ApplicationArguments
import org.springframework.boot.ApplicationRunner
import org.springframework.context.annotation.Profile
import org.springframework.stereotype.Component

private val logger = KotlinLogging.logger {}

@Profile("!test")
@Component
class ListUsersRunner(
  private val userRepository: KomgaUserRepository,
) : ApplicationRunner {
  override fun run(args: ApplicationArguments) {
    if (args.getOptionValues("list-users") != null) {
      val emails = userRepository.findAll().map { it.email }
      if (emails.isNotEmpty())
        logger.info { "Here is a list of all users: $emails" }
      else
        logger.info { "No users exist yet" }
    }
  }
}

```
