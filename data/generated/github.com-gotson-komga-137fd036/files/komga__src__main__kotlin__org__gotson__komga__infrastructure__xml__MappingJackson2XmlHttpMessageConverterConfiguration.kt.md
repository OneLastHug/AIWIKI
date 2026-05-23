# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/MappingJackson2XmlHttpMessageConverterConfiguration.kt

## 它负责什么

这个文件负责给 Spring MVC 注册一个自定义的 XML HTTP 消息转换器：`MappingJackson2XmlHttpMessageConverter`。

在 Komga 里，OPDS v1 接口会返回 Atom/XML 格式的数据，例如目录 feed、entry、link 等。普通的 Jackson XML 序列化可以把 Kotlin/Java 对象转成 XML，但对于 XML namespace 前缀的控制不够明确。这个配置文件的作用，就是让 Jackson 在输出 XML 时使用项目自定义的 `NamespaceXmlFactory`，从而提前注册特定 namespace 的前缀映射。

当前实际注册的前缀来自 `org.gotson.komga.interfaces.api.opds.v1.dto.prefixToNamespace`：

```kotlin
val prefixToNamespace =
  mapOf(
    "pse" to OPDS_PSE,
  )
```

也就是说，它主要保证 OPDS PSE 扩展命名空间 `[URL已移除] 在 XML 输出中使用稳定的 `pse` 前缀，而不是由底层 XML writer 自动生成不可读或不稳定的前缀。

## 关键组成

这个文件内容很短，核心是一个 Spring 配置类和一个 Bean 方法。

```kotlin
@Configuration
class MappingJackson2XmlHttpMessageConverterConfiguration {
  @Bean
  fun mappingJackson2XmlHttpMessageConverter(builder: Jackson2ObjectMapperBuilder) =
    MappingJackson2XmlHttpMessageConverter(
      builder.createXmlMapper(true).factory(NamespaceXmlFactory(prefixToNamespace = prefixToNamespace)).build(),
    )
}
```

关键点如下。

`@Configuration` 表示这是一个 Spring 配置类。应用启动时，Spring 会扫描到这个类，并处理其中的 `@Bean` 方法。

`@Bean` 方法名是 `mappingJackson2XmlHttpMessageConverter`，返回值是 `MappingJackson2XmlHttpMessageConverter`。这是 Spring MVC 用来把对象写成 XML 响应体的组件，和 JSON 场景里的 `MappingJackson2HttpMessageConverter` 类似，只是这里面向 XML。

`Jackson2ObjectMapperBuilder` 是 Spring 提供的 Jackson 构建器。这里没有直接 `XmlMapper()`，而是复用 Spring 注入的 builder，意味着它可以继承 Spring Boot / 项目里已经配置好的 Jackson 模块、日期处理、Kotlin 支持等公共设置。

`builder.createXmlMapper(true)` 表示创建 XML mapper。参数 `true` 的含义是启用 XML mapper 模式。

`.factory(NamespaceXmlFactory(prefixToNamespace = prefixToNamespace))` 是这个文件最关键的一步。它把默认 XML factory 替换成项目自定义的 `NamespaceXmlFactory`，并传入 OPDS DTO 层定义好的 namespace 前缀映射。

`.build()` 创建最终的 mapper，再交给 `MappingJackson2XmlHttpMessageConverter` 使用。

这个文件 import 的依赖也能说明它的定位：

```kotlin
import org.gotson.komga.interfaces.api.opds.v1.dto.prefixToNamespace
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder
import org.springframework.http.converter.xml.MappingJackson2XmlHttpMessageConverter
```

其中唯一的项目内 import 是 `prefixToNamespace`，说明这个基础设施配置直接服务于 OPDS v1 DTO 的 XML 命名空间输出需求。

## 上下游关系

上游主要是 OPDS v1 的 DTO 和 Controller。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/dto/XmlNamespaces.kt` 定义了 XML namespace 常量：

```kotlin
const val ATOM = "[URL已移除]"
const val OPDS_PSE = "[URL已移除]"
const val OPENSEARCH = "[URL已移除]"

val prefixToNamespace =
  mapOf(
    "pse" to OPDS_PSE,
  )
```

其中 `ATOM`、`OPDS_PSE`、`OPENSEARCH` 会被 OPDS DTO 上的 Jackson XML 注解使用。例如 `OpdsFeed` 使用 Atom namespace：

```kotlin
@JacksonXmlRootElement(localName = "feed", namespace = ATOM)
abstract class OpdsFeed(...)
```

`OpdsLinkPageStreaming` 使用 OPDS PSE namespace：

```kotlin
@get:JacksonXmlProperty(isAttribute = true, namespace = OPDS_PSE)
val count: Int
```

这类字段最终需要输出类似 `pse:count`、`pse:lastRead`、`pse:lastReadDate` 这样的 XML attribute。目标文件中的配置就是为了让 Jackson XML 在写这些带 namespace 的属性时，知道 `OPDS_PSE` 对应的前缀应该是 `pse`。

直接下游是 `NamespaceXmlFactory`，路径是 `komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/NamespaceXmlFactory.kt`。

它继承 `XmlFactory`，并覆盖多个创建 XML generator / writer 的方法：

```kotlin
class NamespaceXmlFactory(
  private val defaultNamespace: String? = null,
  private val prefixToNamespace: Map<String, String> = emptyMap(),
) : XmlFactory()
```

在 writer 创建完成后，它会调用：

```kotlin
private fun XMLStreamWriter.configure() =
  try {
    defaultNamespace?.let { this.setDefaultNamespace(it) }
    for ((key, value) in prefixToNamespace) {
      this.setPrefix(key, value)
    }
  } catch (e: XMLStreamException) {
    StaxUtil.throwAsGenerationException(e, null)
  }
```

这说明目标配置文件并不直接操作 XML 文本，也不直接拼接 namespace。它只是把 `prefixToNamespace` 注入到 `NamespaceXmlFactory`，真正设置前缀的是 `XMLStreamWriter.setPrefix(key, value)`。

再往外看，OPDS v1 Controller 是主要调用场景。`OpdsController` 的类级注解声明：

```kotlin
@RequestMapping(
  value = [ROUTE_BASE],
  produces = [
    MediaType.APPLICATION_ATOM_XML_VALUE,
    MediaType.APPLICATION_XML_VALUE,
    MediaType.TEXT_XML_VALUE
  ]
)
```

也就是说 `/opds/v1.2/` 下面的接口会生产 XML 响应。当这些接口返回 `OpdsFeed`、`OpenSearchDescription` 等对象时，Spring MVC 需要选择一个能写 XML 的 `HttpMessageConverter`，目标文件注册的 converter 就会参与这个过程。

根据当前片段推断，这个配置是全局 XML converter 配置，而不是只绑定到某一个 Controller 方法。依据是它通过 Spring `@Bean` 注册 `MappingJackson2XmlHttpMessageConverter`，没有在 Controller 或某个方法上手动 new，也没有看到显式调用方。

## 运行/调用流程

一次典型的 OPDS XML 响应流程可以这样理解：

1. 客户端请求 OPDS v1 接口，例如 `/opds/v1.2/catalog`，并接受 `application/atom+xml`、`application/xml` 或 `text/xml`。

2. 请求进入 `OpdsController`。这个 Controller 位于 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`，类级别声明了 XML produces。

3. Controller 方法根据数据库、领域服务、权限检查等信息构造 OPDS DTO，比如 `OpdsFeedNavigation`、`OpdsFeedAcquisition`、`OpdsLinkPageStreaming` 等。

4. Controller 返回 Kotlin 对象，而不是手写 XML 字符串。

5. Spring MVC 根据响应类型和 `produces` 选择合适的 `HttpMessageConverter`。

6. 目标文件注册的 `MappingJackson2XmlHttpMessageConverter` 使用内部的 XML mapper 来序列化对象。

7. 这个 XML mapper 使用 `NamespaceXmlFactory` 创建 `XMLStreamWriter` 或 `ToXmlGenerator`。

8. `NamespaceXmlFactory` 在 writer/generator 创建后调用 `configure()`，把 `prefixToNamespace` 中的映射注册进去。目前就是：

   ```kotlin
   "pse" -> "[URL已移除]"
   ```

9. Jackson 读取 DTO 上的 `@JacksonXmlRootElement`、`@JacksonXmlProperty`、`@JacksonXmlElementWrapper` 等注解，生成 XML 元素和属性。

10. 当遇到 `namespace = OPDS_PSE` 的属性时，底层 XML writer 已经知道这个 namespace 对应 `pse` 前缀，因此输出可以保持为稳定的 `pse:*` 形式。

这里要注意，目标文件本身不决定哪些字段属于哪个 namespace。字段属于哪个 namespace 是由 OPDS DTO 注解决定的。目标文件只负责“Jackson 写 XML 时，namespace 前缀应该怎么映射”。

## 小白阅读顺序

建议按下面顺序读，比较容易理解这个文件为什么存在。

第一步，先读目标文件 `komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/MappingJackson2XmlHttpMessageConverterConfiguration.kt`。重点看它注册了什么 Bean，以及这个 Bean 里用的 XML mapper 和 `NamespaceXmlFactory`。

第二步，读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/dto/XmlNamespaces.kt`。这个文件很短，但它解释了 `prefixToNamespace` 到底是什么。目前只有 `pse` 到 `OPDS_PSE` 的映射。

第三步，读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/NamespaceXmlFactory.kt`。重点看 `configure()` 方法，以及它如何调用 `setPrefix`。这一步能明白目标文件传进去的 map 最终在哪里生效。

第四步，读 OPDS DTO，例如 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/dto/OpdsLink.kt`。这里可以看到 `OpdsLinkPageStreaming` 的 `count`、`lastRead`、`lastReadDate` 使用了 `namespace = OPDS_PSE`，这就是 `pse` 前缀最直接的业务需求来源。

第五步，读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/dto/OpdsFeed.kt`。这里可以看到 OPDS feed 的 XML 根元素、子元素、列表展开规则等。

第六步，最后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`。先看类上的 `@RequestMapping(... produces = [...])`，再看它如何返回 OPDS DTO。这个文件比较大，不需要一开始就完整读完，只要先确认它是 XML 输出入口即可。

## 常见误区

误区一：以为这个配置只影响 OPDS v1 Controller 的某一个接口。

实际上它通过 Spring `@Bean` 注册的是一个 `MappingJackson2XmlHttpMessageConverter`，属于 Spring MVC 的消息转换器层面。根据当前片段推断，它会参与整个应用的 XML 响应序列化选择，而不是某个 Controller 方法里的局部工具函数。

误区二：以为 `prefixToNamespace` 定义了所有 XML namespace。

不是。`XmlNamespaces.kt` 里确实定义了 `ATOM`、`OPDS_PSE`、`OPENSEARCH` 三个 namespace 常量，但 `prefixToNamespace` 当前只映射了：

```kotlin
"pse" to OPDS_PSE
```

也就是说，这个配置当前主要解决 OPDS PSE 扩展 namespace 的前缀稳定性问题。Atom 和 OpenSearch 的 namespace 使用由 DTO 注解决定，但没有在这个 map 里指定固定前缀。

误区三：以为这个文件负责生成 OPDS XML 的结构。

不是。XML 结构由 DTO 类上的 Jackson XML 注解决定，例如 `@JacksonXmlRootElement`、`@JacksonXmlProperty`、`@JacksonXmlElementWrapper`。目标文件只负责注册 converter 和定制底层 XML factory。

误区四：以为可以直接删掉 `NamespaceXmlFactory`，Jackson 仍然会输出完全一样的 XML。

不一定。Jackson/StAX 在没有显式前缀映射时，仍可能输出合法 XML，但 namespace 前缀可能变成自动生成的形式。对于 OPDS 客户端兼容性、可读性或测试稳定性来说，固定输出 `pse` 前缀更可靠。

误区五：以为 `Jackson2ObjectMapperBuilder` 可有可无，直接 new 一个 mapper 也一样。

直接 new 可能绕过 Spring 已配置的 Jackson 行为，例如 Kotlin 模块、时间类型序列化设置、全局 Jackson 定制等。这里使用注入的 `Jackson2ObjectMapperBuilder`，说明作者希望 XML mapper 仍然继承应用级 Jackson 配置，只是在 XML factory 上加一层 namespace 定制。

误区六：以为 `MappingJackson2XmlHttpMessageConverterConfiguration` 是业务层代码。

它位于 `org.gotson.komga.infrastructure.xml`，属于基础设施层。它不理解 library、book、series、readlist 等业务概念，只提供“对象如何被写成 XML HTTP 响应”的技术能力。业务对象到 OPDS DTO 的组装发生在 `interfaces.api.opds.v1` 一侧。
