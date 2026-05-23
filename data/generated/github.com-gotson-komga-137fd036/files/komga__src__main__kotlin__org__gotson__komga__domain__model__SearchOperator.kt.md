# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/SearchOperator.kt

## 它负责什么

这个文件定义了 Komga 搜索系统里的“操作符集合”。它本身不是业务对象，而是一个类型命名空间：把“等于、包含、大于、小于、时间范围、布尔判断、空值判断”等搜索动作，统一封装成可序列化、可在编译期受限使用的一组类型。

它的核心价值有两个：

1. 约束 `SearchCondition` 里每个字段能接受什么样的操作符，避免把字符串操作符误用到数值字段，或者把日期操作符误用到布尔字段。
2. 作为 API / JSON 与后端查询层之间的中间表示，方便控制器先把请求参数转成搜索条件，再由后端查询实现转换成 SQL 或其他查询逻辑。

## 关键组成

- `SearchOperator`：外层类，只承担命名空间作用，真正的内容都在内部类型里。
- 一组 `sealed interface`：
  - `Equality<T>`
  - `EqualityNullable<T>`
  - `StringOp`
  - `Numeric<T>`
  - `NumericNullable<T>`
  - `Date`
  - `Boolean`

  这些接口用来按字段类型划分“允许的操作符种类”。

- 一组具体操作符类：
  - `Is<T>`、`IsNot<T>`：通用等值/非等值操作，覆盖字符串、枚举、数值等多种字段。
  - `Contains`、`DoesNotContain`、`BeginsWith`、`DoesNotBeginWith`、`EndsWith`、`DoesNotEndWith`：字符串匹配。
  - `GreaterThan<T>`、`LessThan<T>`：数值比较。
  - `Before`、`After`、`IsInTheLast`、`IsNotInTheLast`：日期时间相关比较。
  - `IsTrue`、`IsFalse`：布尔判断。
  - `IsNull`、`IsNotNull`：日期字段的空值判断。
  - `IsNullT<T>`、`IsNotNullT<T>`：可空泛型字段的空值判断。

- Jackson 标注：
  - `@JsonTypeInfo(... property = "operator")`：序列化时用 `operator` 字段区分具体子类型。
  - `@JsonTypeName("is")` 之类：指定每个具体操作符在 JSON 里的名字。

这里有一个设计细节很重要：`IsNull` / `IsNotNull` 和 `IsNullT` / `IsNotNullT` 共享同样的 JSON 名称，但分别服务于不同字段类别。根据当前片段推断，这是为了同时满足“同名语义”与“Kotlin 泛型类型约束”。

## 上下游关系

上游主要是 `SearchCondition`。在 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt` 里，很多条件字段都直接声明成 `SearchOperator.*` 的某个子类型，例如：

- `Title` 用 `SearchOperator.StringOp`
- `ReleaseDate` 用 `SearchOperator.Date`
- `NumberSort` 用 `SearchOperator.Numeric<Float>`
- `Deleted` 用 `SearchOperator.Boolean`
- `Tag` 用 `SearchOperator.EqualityNullable<String>`

这说明 `SearchOperator` 是 `SearchCondition` 的类型基础。

再往上，是 REST 控制器和领域服务。`BookController`、`SeriesController`、`ReadListController`、`LibraryController`、`TaskEmitter`、`SyncPointLifecycle`、`BookLifecycle`、`TransientBookLifecycle`、`LibraryContentLifecycle` 等地方都会创建 `SearchCondition`，并用这里定义的操作符拼装过滤条件。

下游是查询实现层。根据当前片段推断，像 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt` 这样的代码会读取具体操作符类型，然后把它们翻译成 JOOQ 条件，最终落到数据库查询。

另外，`SeriesSearch.kt` 里保留了 `regexSearch` 的兼容字段，并明确注释“use SearchOperator.BeginsWith instead”；`SearchField.kt` 也已经标记弃用。说明这个文件也是旧搜索模型向新模型迁移的核心承接点。

## 运行/调用流程

1. API 层接收搜索参数。
2. 控制器把参数组装成 `SearchCondition.Book` 或 `SearchCondition.Series`。
3. 每个条件字段带着一个 `SearchOperator` 子类，例如：
   - `SearchOperator.Is(it)`
   - `SearchOperator.Contains(text)`
   - `SearchOperator.After(dateTime)`
4. 查询服务读取这些条件。
5. JOOQ 或其他查询适配器根据具体 operator 类型分支处理：
   - `Is`、`IsNot` 转成等值/非等值或子查询匹配
   - `Contains`、`BeginsWith` 转成字符串匹配
   - `GreaterThan`、`LessThan` 转成范围比较
   - `IsNullT`、`IsNotNullT` 转成空值相关判断
6. 返回查询结果给上层调用者。

这条链路里，`SearchOperator` 不直接执行查询，它只负责把“搜索语义”表达清楚，真正的执行在下游适配层完成。

## 小白阅读顺序

1. 先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt`，理解哪些业务字段会用到这些操作符。
2. 再回到 `SearchOperator.kt`，把每一类 operator 和字段类型对应起来。
3. 看一个控制器，比如 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt` 或 `SeriesController.kt`，观察请求参数如何组装成 `SearchCondition`。
4. 再看查询层，比如 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt`，理解 operator 如何被翻译成 SQL。
5. 最后补看 `SeriesSearch.kt` 和 `SearchField.kt`，理解旧接口兼容和弃用迁移。

## 常见误区

- 误以为 `SearchOperator` 是可直接实例化的业务对象。实际上它更像一个“类型容器”。
- 误以为所有字段都能用同一组操作符。这里用不同的 sealed interface 明确做了类型约束。
- 误以为 `IsNull`、`IsNotNull`、`IsNullT`、`IsNotNullT` 是重复代码。它们分别照顾了不同字段类别和泛型可空场景。
- 误以为 JSON 里的 `operator` 只是普通字段。实际上它是 Jackson 多态反序列化的关键标识。
- 误以为这个文件会直接参与数据库查询。它不负责执行，只负责表达搜索语义，真正落库是在下游查询适配器里完成的。
- 误把 `SearchField` 或 `regexSearch` 当成主路径。当前代码里它们已经是兼容入口，主线已经转向 `SearchOperator.BeginsWith` 等新结构。
