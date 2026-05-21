# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerConfiguration.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package org.gotson.komga.infrastructure.web

import io.github.oshai.kotlinlogging.KotlinLogging
import org.gotson.komga.infrastructure.configuration.KomgaSettingsProvider
import org.springframework.boot.web.server.WebServerFactoryCustomizer
import org.springframework.boot.web.servlet.server.ConfigurableServletWebServerFactory
import org.springframework.stereotype.Component

private val logger = KotlinLogging.logger {}

@Component
class WebServerConfiguration(
  private val settingsProvider: KomgaSettingsProvider,
) : WebServerFactoryCustomizer<ConfigurableServletWebServerFactory> {
  override fun customize(factory: ConfigurableServletWebServerFactory) {
    settingsProvider.serverPort?.let {
      if (it > 1)
        factory.setPort(it)
      else
        logger.warn { "Ignoring invalid server port: $it" }
    }
    settingsProvider.serverContextPath?.let {
      if (it.startsWith("/") && !it.endsWith("/"))
        factory.setContextPath(it)
      else
        logger.warn { "Ignoring invalid server context path: $it" }
    }
  }
}

```
