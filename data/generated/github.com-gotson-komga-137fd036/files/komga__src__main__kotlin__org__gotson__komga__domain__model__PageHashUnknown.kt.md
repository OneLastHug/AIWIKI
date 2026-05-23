# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashUnknown.kt

## 它负责什么

`PageHashUnknown` 是一个很薄的领域模型，用来表示“**尚未在已知哈希表里登记，但又被系统判定为可疑重复的页面哈希**”。

它继承自 `PageHash`，本身只额外保存一个 `matchCount`：

- `hash`：页面哈希值，来自父类 `PageHash`
- `size`：文件大小，来自父类 `PageHash`
- `matchCount`：这个未知哈希对应的匹配数量，通常可以理解为“有多少条页面记录命中了这个哈希”

从代码形态看，它不是业务处理器，也不是算法实现，只是给 DAO、服务层和 REST 层传递数据的容器。

## 关键组成

这个文件里只有一个类定义：

```kotlin
class PageHashUnknown(
  hash: String,
  size: Long? = null,
  val matchCount: Int = 0,
) : PageHash(hash, size)
```

它的关键点有三个：

1. **继承 `PageHash`**
   - `PageHash` 负责公共字段 `hash` 和 `size`
   - `PageHash` 的构造里还会把负数 `size` 规整为 `null`
   - 所以 `PageHashUnknown` 自己不重复实现这部分基础逻辑

2. **新增 `matchCount`**
   - 这是它和 `PageHashKnown` 最本质的区别
   - 代表当前哈希在“未知重复页”查询结果中的命中次数
   - 默认值是 `0`，但在正常 DAO 返回里通常会被填成真实统计值

3. **没有额外方法**
   - 它不实现 `copy`
   - 不实现业务判断
   - 不做序列化转换
   - 纯粹是结果对象

## 上下游关系

### 上游

1. **`PageHashDao.findAllUnknown`**
   - 这是直接构造 `PageHashUnknown` 的地方
   - DAO 查询会按 `FILE_HASH` 分组，排除空哈希，排除已经存在于已知哈希表中的记录，并要求重复数大于 1
   - 当前片段里可以看到映射逻辑是：
     `PageHashUnknown(it.value1(), it.value2(), it.value3())`
   - 也就是说：
     - `value1` 是 `hash`
     - `value2` 是 `size`
     - `value3` 是 `matchCount`

2. **`PageHashRepository.findAllUnknown`**
   - 仓储接口把 DAO 的结果向上暴露为分页结果
   - 上层不关心 SQL 细节，只接收 `Page<PageHashUnknown>`

### 下游

1. **`PageHashController.getUnknownPageHashes`**
   - REST 接口 `/api/v1/page-hashes/unknown`
   - 返回 `Page<PageHashUnknownDto>`
   - 控制器只是把领域对象转成 DTO

2. **`PageHashUnknownDto.toDto()`**
   - 直接读取 `hash`、`size`、`matchCount`
   - 说明这三个字段就是 API 层对外要展示的全部内容

3. **页面/前端消费**
   - 从接口语义看，前端通常会把它当成“未知重复页列表”
   - 用户可以进一步查看该哈希对应的页面缩略图，或者执行删除操作
   - 这一层不直接依赖 `PageHashUnknown` 的内部实现，只依赖它的字段

## 运行/调用流程

根据当前片段推断，完整链路大致是这样：

1. **数据库中存在页面哈希数据**
   - 页面文件被扫描或哈希计算后，相关记录进入页面哈希表

2. **DAO 查询“未知重复”**
   - `PageHashDao.findAllUnknown(pageable)` 执行查询
   - 过滤条件包括：
     - `FILE_HASH != ""`
     - 该哈希在已知哈希表中不存在
     - 分组后 `count(book_id) > 1`
   - 这一步把“未知但重复”的页面哈希筛出来

3. **DAO 映射为 `PageHashUnknown`**
   - 每个分组结果被构造成 `PageHashUnknown(hash, size, matchCount)`

4. **Repository 向上返回分页对象**
   - `PageHashRepository.findAllUnknown` 统一抽象数据访问层

5. **Controller 转 DTO 并返回 API**
   - `PageHashController.getUnknownPageHashes()` 把领域对象映射成 `PageHashUnknownDto`
   - 最终返回给调用方

6. **用户可能进一步操作这些未知哈希**
   - 查看缩略图
   - 标记为已知
   - 触发删除重复页动作
   - 这些动作主要围绕 `PageHashKnown` 和 `PageHashLifecycle` 展开，`PageHashUnknown` 本身不参与修改逻辑

## 小白阅读顺序

如果你是第一次看这块代码，建议按这个顺序读：

1. `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHash.kt`
   - 先理解父类 `PageHash` 的公共字段和 `size` 归一化逻辑

2. `komga/src/main/kotlin/org/gotson/komga/domain/model/PageHashUnknown.kt`
   - 再看这个文件，理解它只是给“未知重复页”补了一个 `matchCount`

3. `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/PageHashDao.kt`
   - 看 `findAllUnknown` 的 SQL 和映射
   - 这里决定了 `matchCount` 的来源

4. `komga/src/main/kotlin/org/gotson/komga/domain/persistence/PageHashRepository.kt`
   - 理解仓储接口如何把 DAO 结果暴露出去

5. `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/PageHashUnknownDto.kt`
   - 看领域对象如何转成 API 输出

6. `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/PageHashController.kt`
   - 看 `/api/v1/page-hashes/unknown` 是怎么对外提供的

## 常见误区

1. **把 `PageHashUnknown` 当成“计算哈希”的类**
   - 不是。它不负责计算哈希，只负责承载结果。

2. **以为 `matchCount` 是一个通用统计值**
   - 这里的 `matchCount` 来自具体 DAO 查询结果，语义是“未知重复哈希的命中数”
   - 它不是全局唯一标准字段，不能脱离查询上下文理解

3. **忽略父类 `PageHash` 的 `size` 处理**
   - `PageHash` 会把负数 `size` 转成 `null`
   - 所以 `PageHashUnknown` 继承到的 `size` 不是原样透传

4. **把“unknown”理解成“没有哈希”**
   - 不是。这里的 unknown 不是没哈希，而是“**有哈希，但还没被登记进 known 列表**”
   - DAO 里还会排除空字符串哈希，所以它关注的是有效哈希

5. **误读 `matchCount` 和 `totalSize` 的关系**
   - 当前 DAO 查询里还有 `totalSize` 计算，但 `PageHashUnknown` 并没有接收这个值
   - 说明这个文件只关心 `hash`、`size`、`matchCount`，其他统计信息没有在该模型里表达

6. **认为它和 `PageHashKnown` 只是命名不同**
   - 不是。`PageHashKnown` 还包含 `action`、`deleteCount`、审计字段等，代表可操作的已知策略记录
   - `PageHashUnknown` 更像“待人工确认的候选重复项”
