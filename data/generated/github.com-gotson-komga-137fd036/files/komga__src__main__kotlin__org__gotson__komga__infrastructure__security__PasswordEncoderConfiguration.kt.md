# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/security/PasswordEncoderConfiguration.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package org.gotson.komga.infrastructure.security

import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.security.core.token.Sha512DigestUtils
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder
import org.springframework.security.crypto.password.PasswordEncoder

@Configuration
class PasswordEncoderConfiguration {
  @Bean
  fun getPasswordEncoder(): PasswordEncoder = BCryptPasswordEncoder()

  @Bean
  fun getTokenEncoder(): TokenEncoder = TokenEncoder { rawPassword -> Sha512DigestUtils.shaHex(rawPassword) }
}

```
