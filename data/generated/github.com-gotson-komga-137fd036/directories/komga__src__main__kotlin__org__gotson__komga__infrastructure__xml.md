# 目录：komga/src/main/kotlin/org/gotson/komga/infrastructure/xml

## 它负责什么

这个目录是 Komga 后端里专门处理 **XML 输出序列化基础设施** 的小目录。它不承载业务逻辑，也不直接生成 OPDS 数据，而是为 Spring MVC 的 XML 响应配置一个带命名空间前缀能力的 Jackson XML `HttpMessageConverter`。

核心目标可以概括为一句话：当控制器返回 OPDS v1.2 的 DTO 对象时，让 Jackson 在写 XML 时能正确声明和使用特定 XML namespace prefix，尤其是 `pse` 前缀。

相关业务入口在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`。这个控制器声明：

```kotlin
@RequestMapping(
  value = [ROUTE_BASE],
  produces = [
    MediaType.APPLICATION_ATOM_XML_VALUE,
    MediaType.APPLICATION_XML_VALUE,
    MediaType.TEXT_XML_VALUE,
  ],
)
```

它的接口返回 `OpdsFeed`、`OpenSearchDescription` 等 OPDS XML DTO。目录 `infrastructure/xml` 的作用就是让这些对象经由 Spring HTTP 响应写出时，XML 命名空间更符合 OPDS 客户端预期。

## 关键组成

这个目录只有两个文件：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/MappingJackson2XmlHttpMessageConverterConfiguration.kt`

这是 Spring 配置类，标注了 `@Configuration`，对外提供一个 Bean：

```kotlin
@Bean
fun mappingJackson2XmlHttpMessageConverter(builder: Jackson2ObjectMapperBuilder) =
  MappingJackson2XmlHttpMessageConverter(
    builder.createXmlMapper(true)
      .factory(NamespaceXmlFactory(prefixToNamespace = prefixToNamespace))
      .build(),
  )
```

它做了三件事：

1. 通过 Spring 注入的 `Jackson2ObjectMapperBuilder` 创建 XML mapper。
2. 把 mapper 底层 XML factory 替换成自定义的 `NamespaceXmlFactory`。
3. 用这个 mapper 构造 `MappingJackson2XmlHttpMessageConverter`，交给 Spring MVC 用于 XML HTTP 响应序列化。

这里导入的 `prefixToNamespace` 来自 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/dto/XmlNamespaces.kt`：

```kotlin
const val ATOM = "[URL已移除]"
const val OPDS_PSE = "[URL已移除]"
const val OPENSEARCH = "[URL已移除]"

val prefixToNamespace =
  mapOf(
    "pse" to OPDS_PSE,
  )
```

也就是说，这个 HTTP XML converter 当前主要预注册 `pse` 这个 XML 前缀，对应 OPDS Page Streaming Extension namespace：`[URL已移除]

`komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/NamespaceXmlFactory.kt`

这是自定义的 Jackson `XmlFactory` 子类。它接收两个参数：

```kotlin
class NamespaceXmlFactory(
  private val defaultNamespace: String? = null,
  private val prefixToNamespace: Map<String, String> = emptyMap(),
) : XmlFactory()
```

其中：

- `defaultNamespace`：可选默认 namespace。当前配置类没有传入，所以实际是 `null`。
- `prefixToNamespace`：prefix 到 namespace URI 的映射。当前传入的是 `"pse" to OPDS_PSE`。

这个类覆盖了多个 XML writer / generator 创建入口：

```kotlin
override fun _createXmlWriter(ctxt: IOContext?, w: Writer?): XMLStreamWriter
override fun createGenerator(out: OutputStream?, enc: JsonEncoding?): ToXmlGenerator
override fun createGenerator(out: OutputStream?): ToXmlGenerator
override fun createGenerator(out: Writer?): ToXmlGenerator
override fun createGenerator(f: File?, enc: JsonEncoding?): ToXmlGenerator
override fun createGenerator(sw: XMLStreamWriter?): ToXmlGenerator
```

覆盖这么多方法的原因是 Jackson 在不同输出目标下可能走不同的 generator 创建路径，例如写到 `OutputStream`、`Writer`、`File` 或已有的 `XMLStreamWriter`。每个路径都会调用同一个扩展函数：

```kotlin
private fun XMLStreamWriter.configure()
```

`configure()` 内部逻辑很简单：

1. 如果 `defaultNamespace` 不为空，就调用 `setDefaultNamespace()`。
2. 遍历 `prefixToNamespace`，逐个调用 `setPrefix(prefix, namespaceUri)`。
3. 如果 StAX 层抛出 `XMLStreamException`，用 `StaxUtil.throwAsGenerationException(e, null)` 转换成 Jackson 生成异常。

这说明该类关心的是 XML 写出阶段的 StAX writer 配置，而不是 DTO 字段映射本身。

## 上下游关系

上游主要有三类：

第一类是 Spring MVC / Spring Boot 的 HTTP 消息转换机制。`MappingJackson2XmlHttpMessageConverterConfiguration` 注册了一个 `MappingJackson2XmlHttpMessageConverter` Bean。根据当前片段推断，Spring MVC 在处理 `produces = application/xml`、`application/atom+xml`、`text/xml` 等响应时，会从 message converters 中选择合适的 converter，把控制器返回对象写成 XML。

第二类是 Jackson XML 基础设施。配置类使用 `Jackson2ObjectMapperBuilder` 创建 XML mapper，然后指定自定义 `NamespaceXmlFactory`。`NamespaceXmlFactory` 继承自 `com.fasterxml.jackson.dataformat.xml.XmlFactory`，最终影响的是 `ToXmlGenerator` 和底层 `XMLStreamWriter` 的行为。

第三类是 OPDS v1 DTO 的命名空间定义。`prefixToNamespace` 定义在 `interfaces/api/opds/v1/dto/XmlNamespaces.kt`，同一包下的 DTO 使用 Jackson XML 注解声明元素或属性 namespace。例如搜索结果显示：

- `OpdsFeed.kt` 使用 `@JacksonXmlRootElement(localName = "feed", namespace = ATOM)`。
- `OpdsFeed.kt`、`OpdsEntry.kt`、`OpdsAuthor.kt` 中多处使用 `@JacksonXmlProperty(namespace = ATOM)`。
- `OpdsLink.kt` 中部分属性使用 `@get:JacksonXmlProperty(isAttribute = true, namespace = OPDS_PSE)`。
- `OpenSearchDescription.kt` 使用 `@JacksonXmlRootElement(localName = "OpenSearchDescription", namespace = OPENSEARCH)`。

下游主要是 OPDS XML HTTP 响应。`OpdsController.kt` 会构造 `OpdsFeedNavigation`、`OpdsFeedAcquisition`、`OpenSearchDescription` 等 DTO 并返回给客户端。Spring MVC 在写出响应时使用 XML converter，converter 内的 mapper 使用 `NamespaceXmlFactory`，最终 StAX writer 知道 `pse` 这个 prefix 应该绑定到哪个 namespace URI。

需要注意的是，目录内这个配置注册的是 `MappingJackson2XmlHttpMessageConverter`，不是一个全局 `XmlMapper` Bean。仓库里 `infrastructure/metadata/comicrack/ComicInfoProvider.kt`、`ReadListProvider.kt` 也使用 `XmlMapper` 读取 ComicRack XML，但它们是另一个方向的 XML 处理：偏文件元数据读取，不是 HTTP OPDS 响应写出。它们和本目录没有直接调用关系。

## 运行/调用流程

典型流程如下：

1. 客户端请求 OPDS v1.2 XML 接口，例如 `/opds/v1.2/catalog`。
2. 请求进入 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`。
3. 控制器方法如 `getCatalog()` 返回 `OpdsFeed` 类型对象，实际可能是 `OpdsFeedNavigation` 等子类型。
4. Spring MVC 根据控制器 `produces`、请求 `Accept` 头和返回对象，选择 XML 类型的 `HttpMessageConverter`。
5. 本目录中的 `MappingJackson2XmlHttpMessageConverterConfiguration` 提供的 `MappingJackson2XmlHttpMessageConverter` 参与序列化。
6. converter 内部的 XML mapper 使用 `NamespaceXmlFactory` 创建 `ToXmlGenerator`。
7. `NamespaceXmlFactory` 在创建 generator / writer 后调用 `staxWriter.configure()` 或 `XMLStreamWriter.configure()`。
8. `configure()` 将 `"pse"` prefix 绑定到 `[URL已移除]
9. Jackson 根据 OPDS DTO 上的 `@JacksonXmlRootElement`、`@JacksonXmlProperty`、`@JacksonXmlElementWrapper` 等注解写出 XML。
10. 最终响应中的 OPDS XML 能包含正确的 namespace 语义，尤其是带 `OPDS_PSE` namespace 的属性可以使用预期 prefix。

这里要区分两层职责：

- DTO 注解决定“哪个元素或属性属于哪个 namespace URI”。
- `NamespaceXmlFactory` 决定“写 XML 时某些 namespace URI 可以绑定到哪个 prefix”。

例如 `OpdsLink.kt` 中某些属性声明了 `namespace = OPDS_PSE`，而 `XmlNamespaces.kt` 又声明 `"pse" to OPDS_PSE`。两者配合后，Jackson 写出 XML 时才有机会生成符合客户端预期的 `pse:*` 属性或对应 namespace 声明。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/dto/XmlNamespaces.kt`。  
   这个文件最短，先搞清楚项目里有哪些 XML namespace 常量：`ATOM`、`OPDS_PSE`、`OPENSEARCH`，以及当前显式配置的 prefix 只有 `pse`。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/MappingJackson2XmlHttpMessageConverterConfiguration.kt`。  
   重点看它如何把 `prefixToNamespace` 传给 `NamespaceXmlFactory`，以及它注册的是 `MappingJackson2XmlHttpMessageConverter` Bean。

3. 然后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/xml/NamespaceXmlFactory.kt`。  
   重点看覆盖的 `createGenerator()` 方法和 `configure()`。不需要一开始就深究 Jackson 全部内部机制，只要理解“每次创建 XML writer/generator 后，都设置 namespace prefix”。

4. 接着看 OPDS DTO，例如 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/dto/OpdsFeed.kt`、`OpdsEntry.kt`、`OpdsLink.kt`、`OpenSearchDescription.kt`。  
   重点找 `@JacksonXmlRootElement`、`@JacksonXmlProperty`、`@JacksonXmlElementWrapper`，理解对象字段如何映射成 XML 元素和属性。

5. 最后看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`。  
   重点看 `@RequestMapping(... produces = [...])` 和返回类型，例如 `getCatalog(): OpdsFeed`。这能帮助你把“控制器返回对象”与“XML converter 写响应”连起来。

如果只是理解本目录，不需要先读数据库、领域服务或书籍检索逻辑。那些属于 OPDS 数据来源，不属于 XML 序列化基础设施。

## 常见误区

第一个误区：以为 `NamespaceXmlFactory` 负责生成 OPDS 内容。  
它不生成 feed、entry、link，也不查询数据库。OPDS 内容由 `OpdsController.kt` 和 DTO 构造逻辑决定；本目录只影响 XML 写出时的 namespace prefix 配置。

第二个误区：以为 `prefixToNamespace` 会自动让所有 XML 元素都带 `pse` 前缀。  
不会。`prefixToNamespace` 只是告诉 XML writer：`pse` 对应哪个 namespace URI。某个元素或属性是否属于 `OPDS_PSE`，仍然要看 DTO 上的 Jackson XML 注解，例如 `@JacksonXmlProperty(namespace = OPDS_PSE)`。

第三个误区：以为 `ATOM` 默认 namespace 已在这里设置。  
当前配置调用的是 `NamespaceXmlFactory(prefixToNamespace = prefixToNamespace)`，没有传 `defaultNamespace`，所以 `defaultNamespace` 是 `null`。虽然 `NamespaceXmlFactory` 支持设置默认 namespace，但当前 Bean 配置没有启用这个能力。Atom namespace 主要通过 DTO 注解里的 `namespace = ATOM` 表达。

第四个误区：以为这个目录影响所有 XML 读写。  
根据当前片段推断，它主要影响 Spring MVC HTTP 响应中的 XML message converter。仓库中 ComicRack 元数据读取使用 `XmlMapper` 的代码，例如 `ComicInfoProvider.kt`、`ReadListProvider.kt`，并不是通过这个 `MappingJackson2XmlHttpMessageConverter` 来完成的。

第五个误区：忽略覆盖多个 `createGenerator()` 的意义。  
Jackson 可能根据输出目标走不同重载。如果只覆盖其中一个，某些输出路径可能不会执行 namespace 配置。这里覆盖 `OutputStream`、`Writer`、`File`、`XMLStreamWriter` 等入口，是为了让配置在不同 XML 写出路径下都尽量生效。

第六个误区：把 `StaxUtil.throwAsGenerationException(e, null)` 当成业务异常处理。  
这不是业务错误处理，而是把底层 StAX 的 `XMLStreamException` 转换为 Jackson 的生成异常，让调用链按 Jackson 序列化失败的方式处理。它说明这里处于 XML 生成基础设施层，而不是应用业务层。
