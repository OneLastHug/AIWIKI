# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/web/BracketParamsRequestWrapper.kt

## 它负责什么

`BracketParamsRequestWrapper.kt` 定义了一个 Servlet 请求包装器 `BracketParamsRequestWrapper`，它的职责是把两种常见的查询参数写法统一成同一种语义：

- 普通写法：`param=a`
- 带数组后缀写法：`param[]=a`

经过这个 wrapper 后，应用后续读取请求参数时，可以把 `param` 和 `param[]` 当成同一个参数名来处理。例如：

- 请求里只有 `param[]=a`，后续用 `getParameter("param")` 也能读到 `"a"`。
- 请求里同时有 `param=a&param[]=b`，后续会把两边的值合并。
- 参数名枚举和参数 map 中，`param[]` 会归一化成 `param`。

它解决的是 Web API 层的兼容性问题：有些前端或客户端库在序列化数组查询参数时会使用 `[]` 后缀，例如 `tag[]=a&tag[]=b`；而 Spring Controller 里通常声明的是 `@RequestParam(name = "tag") tags: List<String>?`。这个 wrapper 让后端不必同时声明 `tag` 和 `tag[]` 两套参数名。

这个文件本身不注册过滤器，也不决定作用范围。它只提供包装后的 `HttpServletRequest` 行为。真正把它接入请求链的是同目录下的 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/BracketParamsFilterConfiguration.kt`。

## 关键组成

### `BracketParamsRequestWrapper`

核心类：

```kotlin
class BracketParamsRequestWrapper(
  request: HttpServletRequest,
) : HttpServletRequestWrapper(request)
```

它继承自 Jakarta Servlet 的 `HttpServletRequestWrapper`。这类 wrapper 的典型用途是：保留原始 request 的大部分行为，只覆盖少数需要改变的方法。

这里覆盖了四个和请求参数读取直接相关的方法：

- `getParameter(name: String): String?`
- `getParameterValues(name: String): Array<String>?`
- `getParameterNames(): Enumeration<String>`
- `getParameterMap(): MutableMap<String, Array<String>>`

这四个方法正好覆盖了 Servlet / Spring 常用的参数读取入口。Spring MVC 解析 `@RequestParam` 时通常会依赖这些参数访问能力，因此 wrapper 可以影响 Controller 参数绑定。

### import 的含义

文件 import 很少：

```kotlin
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletRequestWrapper
import org.gotson.komga.language.toEnumeration
import java.util.Enumeration
```

它们分别对应：

- `HttpServletRequest`：原始 HTTP 请求对象类型。
- `HttpServletRequestWrapper`：Servlet 标准 wrapper 基类。
- `toEnumeration`：Komga 自己在 `komga/src/main/kotlin/org/gotson/komga/language/LanguageUtils.kt` 中定义的扩展函数，用来把 `List<T>` 转成 Java 风格的 `Enumeration<T>`。
- `Enumeration`：Servlet API 的参数名枚举返回类型。

这里没有 Spring import，说明这个类本身是低层 Servlet 适配逻辑，不直接依赖 Spring MVC 注解或 Controller。

### `getParameter`

代码逻辑：

```kotlin
override fun getParameter(name: String): String? {
  val nameWithoutSuffix = name.removeSuffix("[]")
  val values = listOfNotNull(super.getParameter(nameWithoutSuffix), super.getParameter("$nameWithoutSuffix[]"))
  return if (values.isEmpty())
    null
  else
    values.joinToString(",")
}
```

它做了三步：

1. 先把调用方传进来的参数名去掉末尾的 `[]`。
   - `param` 变成 `param`
   - `param[]` 也变成 `param`

2. 分别从原始 request 里读取：
   - `param`
   - `param[]`

3. 如果两边都没有值，返回 `null`；如果有值，把它们用逗号拼成一个字符串。

例如：

- 原始请求：`?param=a`
  - `getParameter("param")` 返回 `"a"`
  - `getParameter("param[]")` 也返回 `"a"`

- 原始请求：`?param[]=b`
  - `getParameter("param")` 返回 `"b"`
  - `getParameter("param[]")` 也返回 `"b"`

- 原始请求：`?param=a&param[]=b`
  - `getParameter("param")` 返回 `"a,b"`
  - `getParameter("param[]")` 返回 `"a,b"`

这里的逗号拼接很关键。Servlet 的 `getParameter` 本来就只能返回一个字符串；当同一个归一化参数名下有多个来源时，它选择用 `","` 合并。Spring 对集合参数有时也支持逗号分隔字符串的转换，因此这对 `List` / `Set` 参数绑定是有帮助的。

### `getParameterValues`

代码逻辑：

```kotlin
override fun getParameterValues(name: String): Array<String>? {
  val nameWithoutSuffix = name.removeSuffix("[]")
  val regular = super.getParameterValues(nameWithoutSuffix)
  val suffix = super.getParameterValues("$nameWithoutSuffix[]")
  val values = listOfNotNull(regular, suffix)
  return if (values.isEmpty())
    null
  else
    values.reduce { acc, strings -> acc + strings }
}
```

这个方法返回数组，语义比 `getParameter` 更适合多值参数。

它同样把参数名归一化，然后读取：

- 无后缀参数值数组：`param`
- 有后缀参数值数组：`param[]`

最后把两个数组拼接起来。

例如：

- 原始请求：`?tag=a&tag=b`
  - `getParameterValues("tag")` 返回 `["a", "b"]`

- 原始请求：`?tag[]=a&tag[]=b`
  - `getParameterValues("tag")` 返回 `["a", "b"]`

- 原始请求：`?tag=a&tag[]=b`
  - `getParameterValues("tag")` 返回 `["a", "b"]`

测试文件 `komga/src/test/kotlin/org/gotson/komga/infrastructure/web/BracketParamsRequestWrapperTest.kt` 覆盖了这些情况，并且验证了 `getParameterValues("param")` 和 `getParameterValues("param[]")` 的结果相同。

### `getParameterNames`

代码逻辑：

```kotlin
override fun getParameterNames(): Enumeration<String> =
  super
    .getParameterNames()
    .toList()
    .map { it.removeSuffix("[]") }
    .distinct()
    .toEnumeration()
```

它用于返回所有参数名。这里的处理方式是：

1. 读取原始 request 的参数名。
2. 转成 Kotlin `List`。
3. 每个参数名都移除末尾 `[]`。
4. 去重。
5. 再转回 Servlet 需要的 `Enumeration<String>`。

例如原始 request 参数名是：

```text
param
param[]
page
```

包装后枚举出来的是：

```text
param
page
```

这一步非常重要。否则下游框架在枚举参数名时仍会看到 `param[]`，可能导致参数绑定、日志、调试或通用处理逻辑出现两套名字。

`toEnumeration()` 来自 `LanguageUtils.kt`，它内部用一个简单计数器实现 `Enumeration<T>`：

```kotlin
fun <T> List<T>.toEnumeration(): Enumeration<T>
```

所以这个文件没有引入额外库来做列表到枚举的转换。

### `getParameterMap`

代码逻辑：

```kotlin
override fun getParameterMap(): MutableMap<String, Array<String>> =
  super
    .getParameterMap()
    .asSequence()
    .groupBy({ it.key.removeSuffix("[]") }, { it.value })
    .mapValues { it.value.reduce { acc, strings -> acc + strings } }
    .toMutableMap()
```

它用于返回完整参数 map。原始类型是：

```kotlin
Map<String, Array<String>>
```

这个方法会把 key 归一化，并合并相同归一化 key 下的所有数组。

例如原始 map 是：

```text
param   -> ["a"]
param[] -> ["b", "c"]
```

包装后变成：

```text
param -> ["a", "b", "c"]
```

这里用到的关键 API 是：

- `asSequence()`：以序列方式处理 map entry。
- `groupBy({ key }, { value })`：按去掉 `[]` 后的参数名分组，同时保留每个 entry 的数组值。
- `reduce { acc, strings -> acc + strings }`：把同一组下的多个数组拼接起来。
- `toMutableMap()`：返回可变 map，符合方法签名的 `MutableMap<String, Array<String>>`。

## 上下游关系

### 上游：Filter 配置负责包装请求

直接创建 `BracketParamsRequestWrapper` 的地方是：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/web/BracketParamsFilterConfiguration.kt`

其中注册了一个 Spring Boot Servlet Filter：

```kotlin
@Configuration
class BracketParamsFilterConfiguration {
  @Bean
  fun bracketParamsFilter(): FilterRegistrationBean<BracketParamsFilter> =
    FilterRegistrationBean(BracketParamsFilter())
      .also {
        it.addUrlPatterns(
          "/api/*",
        )
        it.setName("queryParamsFilter")
      }
}
```

这个配置说明：

- wrapper 只作用在 `/api/*` URL pattern 上。
- 它是通过 Servlet Filter 链接入的，不是 Controller 内部手动调用。
- Filter 名字叫 `"queryParamsFilter"`。

内部 filter 的逻辑很直接：

```kotlin
chain?.doFilter(BracketParamsRequestWrapper(request as HttpServletRequest), response)
```

也就是说，请求进入 `/api/*` 后，Filter 会把原始 `ServletRequest` 强转为 `HttpServletRequest`，再包一层 `BracketParamsRequestWrapper`，然后交给后续 filter / Spring MVC / Controller。

### 下游：Controller 的 `@RequestParam`

仓库里有大量 API Controller 使用 `@RequestParam` 接收查询参数，尤其是集合参数。例如根据当前片段可以看到：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`
  - `@RequestParam(name = "library_id", required = false) libraryIds: List<String>?`
  - `@RequestParam(name = "media_status", required = false) mediaStatus: List<Media.Status>?`
  - `@RequestParam(name = "tag", required = false) tags: List<String>?`

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
  - `@RequestParam(name = "library_id", required = false) libraryIds: List<String>?`
  - `@RequestParam(name = "collection_id", required = false) collectionIds: List<String>?`
  - `@RequestParam(name = "publisher", required = false) publishers: List<String>?`

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
  - `@RequestParam(name = "library_id", required = false) libraryIds: List<String>?`
  - `@RequestParam(name = "read_status", required = false) readStatus: List<ReadStatus>?`
  - `@RequestParam(name = "tag", required = false) tags: List<String>?`

这些 Controller 通常声明的是不带 `[]` 的参数名，例如 `tag`、`library_id`、`read_status`。如果客户端传的是 `tag[]=foo`，没有 wrapper 时，Spring 可能找不到名为 `tag` 的参数；有了 wrapper 后，`tag[]` 会被归一化成 `tag`。

因此这个文件的下游不是某一个具体函数，而是整个 `/api/*` 下依赖 request parameter 绑定的 Spring MVC 处理链。

### 测试：行为边界由单元测试固定

测试文件是：

`komga/src/test/kotlin/org/gotson/komga/infrastructure/web/BracketParamsRequestWrapperTest.kt`

测试按四组组织：

- `ParameterNames`
- `ParameterValue`
- `ParameterValues`
- `ParameterMap`

它验证的核心行为包括：

- 只有 `param` 时，读取 `param` 和 `param[]` 等价。
- 只有 `param[]` 时，读取 `param` 和 `param[]` 等价。
- 同时存在 `param` 和 `param[]` 时，值会合并。
- 空参数时返回空枚举、空 map 或 `null`。
- 参数名对外只暴露去掉 `[]` 后的形式。

这些测试基本就是理解本文件行为的最好规格说明。

## 运行/调用流程

一次典型请求的流程可以这样理解：

1. 客户端请求 API，例如：

   ```text
   GET /api/v1/books?tag[]=manga&tag[]=favorite&library_id=abc
   ```

2. 请求路径匹配 `/api/*`，进入 `BracketParamsFilterConfiguration` 注册的 Filter。

3. Filter 创建 wrapper：

   ```kotlin
   BracketParamsRequestWrapper(request as HttpServletRequest)
   ```

4. Filter 把包装后的 request 继续传入 filter chain：

   ```kotlin
   chain?.doFilter(wrappedRequest, response)
   ```

5. 后续 Spring MVC 解析 Controller 参数。

6. 当 Spring 需要读取 `@RequestParam(name = "tag") tags: List<String>?` 时，它会从 request 参数里查找 `tag`。

7. wrapper 的 `getParameterValues("tag")` 会同时读取原始请求中的：
   - `tag`
   - `tag[]`

8. 原始请求虽然只有 `tag[]`，但 wrapper 返回合并后的值数组：

   ```text
   ["manga", "favorite"]
   ```

9. Spring 把这些字符串转换并绑定到 Controller 方法参数。

如果客户端传的是：

```text
/api/v1/books?tag=manga&tag[]=favorite
```

那么 wrapper 会把两种来源合并，使下游看到同一个 `tag` 参数拥有两个值。

## 小白阅读顺序

1. 先看 `BracketParamsFilterConfiguration.kt`

   先理解这个 wrapper 是在哪里被接入请求链的。重点看两个地方：

   - `it.addUrlPatterns("/api/*")`
   - `chain?.doFilter(BracketParamsRequestWrapper(...), response)`

   这样可以先建立整体印象：它是一个只作用于 API 请求的 Servlet Filter 包装器。

2. 再看 `BracketParamsRequestWrapper.kt` 的类声明

   重点理解：

   ```kotlin
   : HttpServletRequestWrapper(request)
   ```

   这说明它不是重新实现一个 request，而是在原始 request 外面包一层，只改参数读取行为。

3. 然后按方法阅读

   推荐顺序：

   - `getParameterNames()`
   - `getParameterValues()`
   - `getParameter()`
   - `getParameterMap()`

   先看参数名如何归一化，再看多值如何合并，最后看单值和 map 的特殊处理。

4. 接着看测试文件

   `BracketParamsRequestWrapperTest.kt` 比源码更直观。它用 `MockHttpServletRequest` 构造了几类输入：

   - 只有 `param`
   - 只有 `param[]`
   - 两者同时存在
   - 没有参数

   对照测试可以快速确认每个 override 方法的预期结果。

5. 最后看 Controller 中的集合参数

   可以搜索 `@RequestParam`，重点关注 `List<String>`、`Set<String>`、枚举列表这些参数。它们就是这个 wrapper 最可能影响的地方。

## 常见误区

1. 误以为它只处理数组参数

   类名里有 `BracketParams`，容易让人以为它只处理数组。但实际上它处理的是“参数名是否带 `[]` 后缀”的兼容问题。它不会解析 JSON 数组，也不会理解复杂嵌套结构。

   它支持的是这种形式：

   ```text
   tag[]=a&tag[]=b
   ```

   不是这种形式：

   ```text
   tag[0]=a&tag[1]=b
   ```

2. 误以为它只影响 `getParameterValues`

   它覆盖了四个方法，所以影响范围包括：

   - 单值读取
   - 多值读取
   - 参数名枚举
   - 参数 map

   下游无论通过哪种常见 Servlet 参数 API 读取，都能看到归一化后的结果。

3. 误以为 `getParameter("param")` 只返回第一个值

   原始 Servlet API 通常对同名多值参数的 `getParameter` 返回第一个值。但这个 wrapper 在 `param` 和 `param[]` 两种来源同时存在时，会用逗号合并：

   ```text
   param=a&param[]=b -> "a,b"
   ```

   这是一种为了兼容 Spring 参数转换的设计选择。阅读时不要把它和原生 `HttpServletRequest` 的行为完全等同。

4. 误以为它会修改原始 request

   它没有修改原始请求对象，也没有重写 query string。它只是覆盖读取参数的方法。原始 request 仍然存在，wrapper 通过 `super.getParameter...` 去读取原始数据。

5. 误以为它作用于所有 URL

   根据 `BracketParamsFilterConfiguration.kt`，它只注册到：

   ```text
   /api/*
   ```

   因此非 `/api/*` 请求不会经过这个 wrapper。根据当前片段推断，这个设计是为了只影响 REST/API 参数绑定，避免对静态资源、页面、其他协议入口产生额外行为。

6. 误以为 `removeSuffix("[]")` 会删除任意位置的中括号

   Kotlin 的 `removeSuffix("[]")` 只会移除末尾的 `[]`。例如：

   - `tag[]` 变成 `tag`
   - `tag` 保持 `tag`
   - `filter[tag]` 不会变成 `filtertag`
   - `tag[][]` 只会变成 `tag[]`

   所以它处理的是简单、末尾式的数组参数后缀。

7. 误以为合并顺序一定等于客户端传参顺序

   `getParameterValues` 和 `getParameterMap` 的合并逻辑是把 `param` 和 `param[]` 两组数组拼接。对于同一组数组内部，顺序来自底层 request；对于两组之间，源码中 `getParameterValues` 是先取无后缀 `param`，再取有后缀 `param[]`。测试里使用的是 `containsExactlyInAnyOrder`，说明测试不强调最终顺序。阅读业务逻辑时不要依赖跨来源合并后的顺序。

8. 误以为它能解决所有客户端序列化差异

   它只兼容 `name` 与 `name[]`。其他格式，例如：

   ```text
   tag=a,b
   tag[0]=a
   filters[tag]=a
   ```

   是否能被正确处理，取决于 Spring MVC 默认转换器、Controller 参数类型或其他代码，不是这个 wrapper 单独负责的范围。
