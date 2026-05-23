# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/ScanResult.kt

## 它负责什么

`ScanResult` 是一个很轻量的扫描结果数据容器，专门用来承接文件系统扫描之后的输出。

它本身不做扫描、不做过滤、不做合并，只负责把扫描后的两类核心结果打包起来：

- `series: Map<Series, List<Book>>`：每个 `Series` 对应一组 `Book`
- `sidecars: List<Sidecar>`：扫描到的附属文件，例如封面、元数据之类的 sidecar 资源

从职责上看，它属于 `org.gotson.komga.domain.model` 里的纯数据模型，典型作用是把“扫描阶段”的结果传递给后续业务流程。

## 关键组成

这个文件只有一个 `data class`：

- `ScanResult`
  - `series: Map<Series, List<Book>>`
    - key 是 `Series`
    - value 是该系列下扫描到的 `Book` 列表
  - `sidecars: List<Sidecar>`
    - 扫描过程中收集到的 sidecar 文件集合

几个值得注意的点：

- 它是 `data class`，所以自动拥有 `equals`、`hashCode`、`toString`、`copy`
- 它没有任何方法，说明这里不承载业务规则
- 这个文件没有显式 `import`，因为它和 `Series`、`Book`、`Sidecar` 都在同一个包 `org.gotson.komga.domain.model` 下

## 上下游关系

上游非常明确：`komga/src/main/kotlin/org/gotson/komga/domain/service/FileSystemScanner.kt`。

根据当前片段，`FileSystemScanner.scanRootFolder(...)` 会：

1. 遍历根目录
2. 识别系列目录、书籍文件、sidecar 文件
3. 用临时 map/list 聚合扫描结果
4. 最后返回 `ScanResult(scannedSeries, scannedSidecars)`

也就是说，`ScanResult` 是 `FileSystemScanner` 的最终产物，是扫描服务向外暴露的结果对象。

下游从当前片段只能确认一部分：

- `scanRootFolder` 的调用方会拿到 `ScanResult`
- 这些调用方通常会继续做库更新、元数据同步、索引刷新之类的事情

但具体是哪一个 service/controller 在消费它，当前片段没有展开，所以这里要写成“根据当前片段推断”。

## 运行/调用流程

可以把它理解成一个很短的链路：

1. `FileSystemScanner.scanRootFolder(...)` 开始扫描目录
2. 扫描过程中分别收集：
   - `Series` 和对应的 `Book` 列表
   - `Sidecar` 文件列表
3. 扫描结束后，调用 `ScanResult(scannedSeries, scannedSidecars)`
4. 返回这个对象给更上层的业务逻辑

在这个流程里，`ScanResult` 不负责“怎么扫”，只负责“扫完之后把结果装起来”。

## 小白阅读顺序

如果你第一次看这段代码，建议按这个顺序读：

1. 先看 `ScanResult.kt` 本身，确认它只是一个结果容器
2. 再看 `Series.kt`，理解 `Map<Series, List<Book>>` 里的 key 是什么
3. 再看 `Sidecar.kt`，理解 sidecar 代表什么
4. 然后看 `FileSystemScanner.kt` 里 `scanRootFolder(...)` 的结尾，确认这个结果是怎么组装出来的
5. 最后再回到更上层的调用方，弄清楚扫描结果会被拿去做什么

## 常见误区

- 把 `ScanResult` 当成扫描逻辑本身。它不是，真正的逻辑在 `FileSystemScanner`。
- 以为 `series` 只是“系列列表”。其实它是 `Map<Series, List<Book>>`，强调的是“系列和书籍的归属关系”。
- 以为 `sidecars` 只和某一本书绑定。实际上这里保存的是扫描到的 sidecar 总集合，后续再由扫描逻辑区分它属于 series 还是 book。
- 忽略 `data class` 的语义。这个类是为传递和比较结果而设计的，不是为继承或复杂行为设计的。
- 只看这个文件会觉得“没有内容”。实际上它的价值在于作为 `FileSystemScanner` 的输出契约，连接了扫描阶段和后续业务阶段。
