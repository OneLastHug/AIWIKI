# 文件：`komga/src/test/kotlin/org/gotson/komga/domain/service/MetadataApplierTest.kt`

## 它负责什么

这个文件是 `MetadataApplier` 的单元测试，核心职责是验证“补丁式元数据合并”在两类对象上的行为是否正确：

- `BookMetadata` + `BookMetadataPatch`
- `SeriesMetadata` + `SeriesMetadataPatch`

它重点检查两件事：

1. 只要某个字段被锁定，对应 patch 即使有值也不能覆盖原值。
2. 字段未锁定时，patch 应该完整覆盖原值。

所以，这个测试文件本质上是在给 `MetadataApplier` 的合并规则做行为锁定，确保书籍和系列元数据在导入、刷新时不会因为锁字段而被误改。

## 关键组成

- `package org.gotson.komga.domain.service`：说明它测试的是 service 层逻辑。
- `private val metadataApplier = MetadataApplier()`：这里没有启动 Spring 容器，直接 new 出实现类，说明测试偏纯单元测试。
- `@Nested inner class Book`：专门覆盖书籍元数据合并。
- `@Nested inner class Series`：专门覆盖系列元数据合并。
- 两组测试模式完全对称：
  - locked metadata
  - unlocked metadata

从 import 看，这个测试依赖了几类东西：

- `assertThat`：断言结果。
- `BookMetadata`、`SeriesMetadata`：被合并的目标对象。
- `BookMetadataPatch`、`SeriesMetadataPatch`：输入补丁对象。
- `Author`、`WebLink`、`URI`、`LocalDate`：用于构造更完整的 patch 数据。
- `Nested`、`Test`：JUnit 5 结构化测试。

这个文件本身不导出业务逻辑，它只是验证生产代码的行为。

## 上下游关系

上游是 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`。  
这个生产类是 `@Service`，提供两个重载的 `apply(...)` 方法，分别处理 book 和 series 的 patch 合并。

`MetadataApplier` 的下游，主要是两个生命周期服务：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesMetadataLifecycle.kt`

这两个类在刷新元数据时会注入 `MetadataApplier`，先从 provider 拿到 patch，再调用 `apply(...)` 合并到当前持久化元数据中，最后再写回仓库。

再往下是模型层：

- `BookMetadata`、`SeriesMetadata`：带锁标记的目标对象，内部提供 `copy(...)`。
- `BookMetadataPatch`、`SeriesMetadataPatch`：字段大多是可空的 patch 容器。
- `MetadataApplier` 只是“合并器”，不负责抓取数据、不负责持久化、不负责事件发布。

根据当前片段推断，这个测试直接保护的是“导入器刷新元数据时的最终写回结果”，因为生命周期服务正是 `MetadataApplier` 的实际调用者。

## 运行/调用流程

这份测试的执行方式很直接：

1. JUnit 运行 `MetadataApplierTest`。
2. 进入 `Book` 或 `Series` 的嵌套测试类。
3. 构造一份带锁或不带锁的原始 metadata。
4. 构造一份字段齐全的 patch。
5. 调用 `metadataApplier.apply(patch, metadata)`。
6. 逐字段断言结果。

核心规则来自生产代码里的一个私有函数 `getIfNotLocked(...)`：

- patch 值不为 `null` 且字段未锁定 -> 使用 patch
- 其他情况 -> 保留原值

所以：

- 在 locked 场景里，标题、简介、编号、作者、标签等字段都应该保留原值。
- 在 unlocked 场景里，patch 的值应该全部生效。
- 集合字段如 `authors`、`links`、`tags`、`genres` 是整批替换，不是增量合并。
- `BookMetadata` 和 `SeriesMetadata` 自身会做一些规范化处理，比如 `trim()`、`lowerNotBlank()`，但这个测试主要关心的是“锁”是否生效。

## 小白阅读顺序

1. 先读这个测试文件，先看它断言了哪些字段。
2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`，把 `getIfNotLocked(...)` 的规则对上测试。
3. 接着看 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt` 和 `SeriesMetadata.kt`，理解 `copy(...)` 和锁字段的含义。
4. 再看 `BookMetadataPatch.kt`、`SeriesMetadataPatch.kt`，确认 patch 为什么很多字段是可空。
5. 最后回到 `BookMetadataLifecycle.kt`、`SeriesMetadataLifecycle.kt`，把它放回真实业务流程里：先拿 provider 补丁，再合并，再持久化。

## 常见误区

- 把这个文件当成业务实现。它其实只是测试，不是逻辑入口。
- 以为 `apply(...)` 会做“智能合并”。实际上它只是按锁位判断“用 patch 还是保留原值”。
- 以为集合字段会做增量更新。这里不是，`authors`、`links`、`tags`、`genres` 都是整体替换。
- 以为 patch 中的 `null` 和“空集合”效果一样。两者不同：`null` 表示不更新，空集合在未锁定时会把目标字段替换为空。
- 只看测试不看模型类。`BookMetadata`、`SeriesMetadata` 的 `copy(...)` 和字段归一化逻辑，会影响最终结果。
- 忽略生命周期服务。真正的线上调用不是直接调用 `MetadataApplier`，而是经过 `BookMetadataLifecycle`、`SeriesMetadataLifecycle` 的刷新流程。
