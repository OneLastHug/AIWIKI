# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/BCP47TagValidator.kt`

## 它负责什么
这个文件定义了一个单例对象 `BCP47TagValidator`，作用是统一处理“语言标签”相关的两件事：

1. `isValid(value: String?)`：判断一个字符串是否可作为语言标签使用。
2. `normalize(value: String?)`：把输入规范化成 ICU 认可的标准语言标签格式。

从代码看，它依赖 `com.ibm.icu.util.ULocale`，借助 ICU 的语言标签解析能力来完成校验和格式化。  
根据当前片段推断，它的职责更接近“语言代码清洗器”和“基础合法性校验器”，而不是严格意义上完整的 BCP 47 规范校验器。

## 关键组成
- `object BCP47TagValidator`  
  Kotlin 单例，整个项目直接复用，不需要实例化。

- `private val languages by lazy { ULocale.getISOLanguages().toSet() }`  
  延迟加载 ICU 已知的 ISO 语言列表，并转成 `Set`，用于快速判断某个 tag 的语言主码是否存在。

- `fun isValid(value: String?): Boolean`  
  逻辑很短：
  - `null` 直接返回 `false`
  - `ULocale.forLanguageTag(value)` 解析输入
  - 只要解析结果里的 `language` 非空，并且存在于 `languages` 集合中，就认为有效

- `fun normalize(value: String?): String`  
  逻辑是：
  - `null` 或空白串直接返回空字符串
  - 尝试 `ULocale.forLanguageTag(value).toLanguageTag()`
  - 发生异常则返回空字符串

这里有个细节很重要：`isValid` 看的是“语言主码是否被识别”，`normalize` 看的是“能否转成标准标签字符串”。两者不是同一层面的判断。

## 上下游关系
上游是各种来源的语言字段，主要来自：
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ComicInfoProvider.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/epub/EpubMetadataProvider.kt`

这两个 provider 在提取元数据时，都会先 `isValid(...)`，再 `normalize(...)`，把结果放进 `SeriesMetadataPatch`。

中游/核心消费点是：
- `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadata.kt`

`SeriesMetadata` 构造时会直接对 `language` 做 `trim()` 后调用 `BCP47TagValidator.normalize(...)`，说明领域模型内部希望语言字段始终保存为标准化后的值。

再往外一层是校验注解：
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/validation/BCP47.kt`

这里的 `@BCP47` 约束最终也是委托给 `BCP47TagValidator.isValid(...)`，所以它同时承担了“运行时规范化”和“参数校验规则”的公共基础。

## 运行/调用流程
典型流程可以按下面理解：

1. 外部数据进入系统  
   例如 ComicInfo、EPUB 元数据里带有语言字段。

2. `isValid` 先做门槛判断  
   代码会先判断输入是不是 `null`，再解析 tag，最后确认语言主码是否在 ICU 的 ISO 语言集合中。

3. `normalize` 做标准化输出  
   通过 `ULocale.forLanguageTag(value).toLanguageTag()` 得到统一格式。  
   如果输入为空或解析失败，就返回空字符串，避免把异常扩散到上层。

4. 结果进入领域对象或 patch  
   `SeriesMetadata` 和 `SeriesMetadataPatch` 会拿到已经清洗过的语言值，后续存储、展示或比较时就更一致。

## 小白阅读顺序
1. 先读 `BCP47TagValidator.kt`，看清楚 `isValid` 和 `normalize` 的差别。
2. 再读 `SeriesMetadata.kt`，理解语言字段是如何在领域模型里被强制规范化的。
3. 再看 `infrastructure/validation/BCP47.kt`，把“校验注解”与这个工具类的关系串起来。
4. 最后看 `ComicInfoProvider.kt`、`EpubMetadataProvider.kt`，理解它如何处理真实外部数据。

## 常见误区
- 误区一：它是完整的 BCP 47 校验器。  
  不是。根据当前代码，它主要验证“语言主码是否是 ICU 认识的 ISO 语言”，并没有在这里显式检查 BCP 47 的全部结构细节。

- 误区二：`isValid` 和 `normalize` 是同一个动作。  
  不是。`isValid` 负责判断可用性，`normalize` 负责格式统一。上层通常是先校验，再规范化。

- 误区三：空字符串和非法字符串的处理一样。  
  不一样。空白输入会直接返回空字符串；解析异常时也返回空字符串，但 `isValid` 对 `null` 是直接判 `false`。

- 误区四：这个工具只给一个模块用。  
  不是。它同时被领域模型、Bean Validation、以及元数据导入流程共享，属于跨层复用的基础规则。
