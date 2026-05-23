# 目录：src/server/services/search/impls

## 它负责什么

`src/server/services/search/impls` 是服务端搜索能力的“具体供应商实现层”。上层 `src/server/services/search/index.ts` 只面向统一接口 `SearchServiceImpl` 调用搜索，而这个目录负责把不同搜索服务商的 API、参数格式、鉴权方式、返回结构，转换成项目内部统一的 `UniformSearchResponse`。

从当前片段看，这里并不直接决定“什么时候搜索”或“搜索结果怎么被前端展示”，它只解决一件事：给定 `query` 和可选的 `SearchParams`，调用某个 provider，并返回统一格式。真正的 provider 选择、降级重试、多个 provider 串行尝试等逻辑在上层 `SearchService` 中完成。

统一契约定义在 `src/server/services/search/impls/type.ts`：

`SearchServiceImpl` 只有一个方法 `query(query: string, params?: SearchParams): Promise<UniformSearchResponse>`。

因此可以把这个目录理解为 search provider adapter 集合：每个子目录是一个 adapter，入口类通常命名为 `XxxImpl`，并实现同一个 `query` 方法。

## 直接子目录地图

当前目录下的 provider 子目录包括：

`src/server/services/search/impls/anspire`：Anspire 搜索实现，包含 `index.ts` 与 `type.ts`。

`src/server/services/search/impls/bocha`：Bocha 搜索实现，包含 provider 请求与类型定义。

`src/server/services/search/impls/brave`：Brave 搜索实现，带有 `index.test.ts`，说明该 provider 的映射或异常处理有单测覆盖。

`src/server/services/search/impls/exa`：Exa 搜索实现，也带有 `index.test.ts`。

`src/server/services/search/impls/firecrawl`：Firecrawl 搜索实现。注意它在这里作为 search provider 出现，但仓库另有 `@lobechat/web-crawler` 被 `SearchService.crawlPages` 用于抓取页面内容，两者不要混淆。

`src/server/services/search/impls/google`：Google 搜索实现，负责把 Google 侧响应映射为统一搜索结果。

`src/server/services/search/impls/jina`：Jina 搜索实现。

`src/server/services/search/impls/kagi`：Kagi 搜索实现。

`src/server/services/search/impls/search1api`：Search1API 搜索实现，带有 `index.integration.test.ts`，根据命名推断这里更偏集成测试，可能依赖真实或近真实的外部调用条件。

`src/server/services/search/impls/searxng`：SearXNG 搜索实现，是默认 provider。这个目录比其他 provider 多一个 `client.ts` 和 `fixtures` 子目录，说明它把 SearXNG HTTP 请求封装为独立 client，并为测试准备了样例数据。

`src/server/services/search/impls/tavily`：Tavily 搜索实现，带有 `index.test.ts`。从当前片段可见它通过 `POST /search` 风格请求外部服务，并将 `results` 映射成 `UniformSearchResult`。

目录根部还有两个关键文件：`src/server/services/search/impls/index.ts` 是 provider 注册与工厂入口，`src/server/services/search/impls/type.ts` 是统一接口定义。

## 关键入口

最重要的入口是 `src/server/services/search/impls/index.ts`。

这个文件做两件事：

第一，定义 `SearchImplType` 枚举，列出当前系统支持的搜索实现：`anspire`、`bocha`、`brave`、`exa`、`firecrawl`、`google`、`jina`、`kagi`、`search1api`、`searxng`、`tavily`。

第二，提供 `createSearchServiceImpl(type)` 工厂函数。上层只传入一个 `SearchImplType`，这里通过 `switch` 创建对应的实现类，比如 `new SearXNGImpl()`、`new TavilyImpl()`、`new BraveImpl()`。

默认值是 `SearchImplType.SearXNG`，也就是说在没有显式配置 provider 时，系统会创建 `SearXNGImpl`。另外，`switch` 的 `default` 分支返回 `Search1APIImpl`，这一点阅读时要留意：函数参数默认是 SearXNG，但未知枚举值落入的是 Search1API，而不是 SearXNG。

接口入口是 `src/server/services/search/impls/type.ts`。所有实现都必须实现 `SearchServiceImpl.query`，返回 `@lobechat/types` 中的 `UniformSearchResponse`。这使上层可以无视不同搜索服务商的原始返回结构。

provider 内部入口一般是各子目录的 `index.ts`。例如 `src/server/services/search/impls/searxng/index.ts` 中定义 `SearXNGImpl`，`src/server/services/search/impls/tavily/index.ts` 中定义 `TavilyImpl`。

## 主流程位置

主流程不在本目录内部，而在 `src/server/services/search/index.ts` 的 `SearchService`。

初始化流程是：`SearchService` 构造时读取 `toolsEnv.SEARCH_PROVIDERS`，通过 `parseImplEnv` 解析逗号分隔的 provider 列表，然后对每个 provider 调用 `createSearchServiceImpl`。如果环境变量没有配置任何 provider，就使用默认实现，也就是 `createSearchServiceImpl()`，最终得到默认的 `SearXNGImpl`。

搜索流程主要有两个公开方法：

`query(query, params)`：只调用 provider 列表中的第一个实现，适合明确只要一次普通搜索的场景。

`webSearch({ query, searchCategories, searchEngines, searchTimeRange })`：这是更完整的搜索主流程。它会按 `searchImpList` 顺序逐个尝试 provider。每个 provider 先带完整限制条件搜索；如果结果为空且传入了 `searchEngines`，会去掉搜索引擎限制再试一次；如果仍然为空，会去掉所有限制再试一次。只要某个 provider 返回非空结果，就立即返回。所有 provider 都没有结果时，返回空的 `UniformSearchResponse`。

异常处理也在上层集中做了一层：`queryWithImpl` 捕获 provider 抛出的错误，打印 `[SearchService] query failed:`，并返回空结果和 `errorDetail`。因此 provider 内部可以抛 `TRPCError` 或普通错误，上层会把失败转成统一的空搜索响应，避免单个 provider 直接中断整个 `webSearch` provider 链。

以 `SearXNGImpl` 为例，它会检查 `toolsEnv.SEARXNG_URL`，未配置时抛出 `NOT_IMPLEMENTED`；配置后创建 `SearXNGClient`，调用 `client.search(query, { categories, engines, time_range })`，再把 SearXNG 的 `results` 映射到统一字段，如 `title`、`url`、`content`、`engines`、`parsedUrl`、`publishedDate`、`score`、`thumbnail`。`SearXNGClient` 还处理了一个特殊情况：当 SearXNG 返回包含 `empty results` 的错误体时，把它视为正常空结果。

以 `TavilyImpl` 为例，它从 `process.env.TAVILY_API_KEY` 读取鉴权信息，构造搜索请求体，并把 Tavily 的 `results` 映射成统一的 `UniformSearchResult`。它只支持部分分类语义，例如从 `searchCategories` 中选择 `news` 或 `general` 作为 Tavily 的 `topic`。

## 推荐阅读顺序

建议先读 `src/server/services/search/impls/type.ts`，明确所有 provider 必须遵守的最小接口。

然后读 `src/server/services/search/impls/index.ts`，了解有哪些 provider、默认 provider 是谁、工厂函数如何创建实现类。

接着读上层 `src/server/services/search/index.ts`，重点看 `constructor`、`queryWithImpl`、`query`、`webSearch`。这里能理解 provider 列表来自哪里、失败如何处理、结果为空时如何降级重试。

之后读 `src/server/services/search/impls/searxng/index.ts` 和 `src/server/services/search/impls/searxng/client.ts`。SearXNG 是默认实现，而且拆出了 client，最适合作为理解 provider adapter 写法的样板。

再选择一个外部商业 API provider 阅读，例如 `src/server/services/search/impls/tavily/index.ts`、`src/server/services/search/impls/brave/index.ts` 或 `src/server/services/search/impls/exa/index.ts`，对比不同 provider 如何处理 API key、请求参数、分类、时间范围和结果映射。

最后看测试文件，例如 `src/server/services/search/impls/searxng/index.test.ts`、`src/server/services/search/impls/brave/index.test.ts`、`src/server/services/search/impls/tavily/index.test.ts`。测试通常能补足“哪些边界情况被认为重要”的信息。

## 常见误区

不要把 `impls` 目录理解成完整搜索服务。它只是 provider 实现层；搜索 provider 的编排、顺序、重试、空结果降级都在 `src/server/services/search/index.ts` 的 `SearchService` 中。

不要以为每个 provider 都支持同样的参数。统一接口允许传入 `searchCategories`、`searchEngines`、`searchTimeRange`，但具体 provider 能否支持、如何支持，取决于各自 API。例如根据当前片段，Tavily 的分类只映射到 `news` 或 `general`，SearXNG 则把 categories、engines、time_range 传给自己的 client。

不要混淆 search 和 crawl。`SearchService` 同时有 `webSearch` 和 `crawlPages`，但 `crawlPages` 使用的是 `@lobechat/web-crawler` 的 `Crawler`，并由 `CRAWLER_IMPLS`、`CRAWL_CONCURRENCY`、`CRAWLER_RETRY` 等配置控制；这和 `src/server/services/search/impls` 下的搜索 provider 不是同一套实现。

不要假设默认 provider 与异常 fallback 是同一个。`createSearchServiceImpl()` 的默认参数是 `SearXNG`，但 `switch` 的 `default` 分支返回 `Search1APIImpl`。如果传入未知类型，根据当前代码会走 Search1API，而不是 SearXNG。

不要在新增 provider 时只写子目录实现。还需要在 `src/server/services/search/impls/index.ts` 中增加 `SearchImplType` 枚举值、导入实现类，并在 `createSearchServiceImpl` 里注册对应分支，否则上层无法通过环境变量创建它。

不要直接返回 provider 原始响应。这个目录存在的核心价值就是适配统一结构，所有实现最终都应返回 `UniformSearchResponse`，结果项应尽量映射到统一字段，如 `title`、`url`、`content`、`parsedUrl`、`engines`、`score` 等。
