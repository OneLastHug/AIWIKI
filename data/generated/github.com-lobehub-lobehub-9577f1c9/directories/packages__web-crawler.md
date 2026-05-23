# 目录：packages/web-crawler

## 它负责什么

根据当前片段推断，`packages/web-crawler` 应该是一个计划中的 workspace package，用于承载“网页抓取 / 网页内容抽取 / 可供上层工具消费的网页读取能力”。不过，在本次可读仓库上下文中，目标目录 `packages/web-crawler` 没有实际出现，仓库根下也没有确认到 `packages`、`src`、`package.json` 等预期路径。因此，下面的说明不能视为对现有源码实现的逐项解析，只能作为基于目标路径命名和 LobeHub monorepo 常见分层方式的地图式占位文档。

如果该目录在完整仓库中存在，它大概率不直接承担 UI 展示职责，而是作为底层能力包被 `src/server`、builtin tool、agent runtime、搜索/网页读取相关服务调用。它的边界通常应包括：接收 URL 或网页抓取任务、执行请求与重定向处理、解析 HTML 或正文、整理 metadata、输出结构化内容、处理异常与超时。它不应直接耦合具体页面组件、Zustand store 或路由层。

当前证据不足以确认它是否已经发布为 `@lobechat/web-crawler`、是否包含独立构建脚本、是否面向 Node.js、Edge Runtime 或浏览器环境，也无法确认它依赖的解析库、抓取策略和测试覆盖情况。

## 直接子目录地图

当前可读上下文中没有发现 `packages/web-crawler` 目录，因此无法给出真实的直接子目录列表。

根据 LobeHub 的 package 组织习惯，如果该包存在，常见结构可能会是：

`packages/web-crawler/src`：核心源码目录，通常放置抓取器、解析器、类型定义和导出入口。

`packages/web-crawler/src/core` 或 `packages/web-crawler/src/crawler`：可能放置主抓取流程，比如请求网页、处理响应、判断内容类型、统一错误。

`packages/web-crawler/src/parser` 或 `packages/web-crawler/src/readability`：可能放置 HTML 清洗、正文抽取、标题、摘要、站点 metadata 提取等逻辑。

`packages/web-crawler/src/utils`：可能放置 URL 标准化、header 构造、超时控制、内容长度限制、MIME 判断等辅助能力。

`packages/web-crawler/src/types`：可能定义 `CrawlerOptions`、`CrawlResult`、`PageContent`、`Metadata` 等跨模块结构。

`packages/web-crawler/tests` 或 `__tests__`：如果存在，应覆盖 URL 输入、HTML 解析、异常响应、空页面、编码问题、重定向等关键路径。

以上仅为根据当前片段推断，依据是目标目录命名和 LobeHub monorepo 中 package 的常见职责拆分。

## 关键入口

当前无法确认真实入口文件。对于 LobeHub 的 workspace package，关键入口通常有三类：

第一类是包级入口：`packages/web-crawler/package.json`。它通常声明包名、构建脚本、`exports`、`main`、`module`、`types`、内部依赖和测试命令。阅读这个文件可以先判断该包是库、工具包还是运行时服务。

第二类是源码导出入口：`packages/web-crawler/src/index.ts`。它通常集中导出对外 API，例如 `crawl`、`createCrawler`、`parseWebPage` 或相关类型。对学习者来说，这个文件比直接看内部实现更适合判断“上层能调用什么”。

第三类是主实现入口：可能位于 `packages/web-crawler/src/index.ts`、`packages/web-crawler/src/crawler.ts`、`packages/web-crawler/src/core/index.ts` 或类似路径。它一般会串起请求、解析、结果封装和错误处理。

由于目标目录缺失，以上入口均未能在当前上下文中验证。若后续能访问完整源码，建议先确认 `package.json` 的 `exports` 字段，再沿着 `src/index.ts` 进入内部实现。

## 主流程位置

当前无法指出真实函数或类名。根据目录命名推断，主流程应该围绕“输入 URL，输出可消费网页内容”展开，可能包含以下阶段：

接收输入：上层服务传入 URL、语言、抓取选项、超时时间、最大内容长度、是否提取正文等参数。

请求网页：抓取层处理 HTTP 请求、重定向、headers、状态码、内容类型、超时与网络错误。这里通常是整个包最容易出现边界问题的位置，因为网页来源不可控。

解析响应：如果响应是 HTML，则进入 HTML 解析与正文提取；如果是纯文本、PDF 或其他类型，则可能直接拒绝、降级处理或交给其他包。

内容清洗：移除脚本、样式、导航、广告、空白噪音，提取标题、正文、描述、站点信息、图标或 Open Graph metadata。

结果封装：将原始网页信息转换为结构化对象，供 agent、工具调用、搜索增强、知识库导入或消息引用使用。

错误归一：把网络错误、非 2xx 状态、解析失败、内容过长、robots 或权限限制等情况转换为统一错误类型，避免调用方直接依赖底层库异常。

如果该包被 LobeHub 的 agent 工具链使用，主流程调用点可能在 `packages/builtin-tool-*`、`packages/builtin-tools`、`packages/agent-runtime` 或 `src/server/services` 附近。但当前片段没有足够证据确认具体调用路径。

## 推荐阅读顺序

1. 先读 `packages/web-crawler/package.json`，确认包名、构建方式、导出入口和依赖。特别关注是否依赖 `fetch`、HTML parser、readability、Playwright、JSDOM 或自研工具。

2. 再读 `packages/web-crawler/src/index.ts`，只看对外导出的函数和类型。学习目标是建立“这个包对外承诺什么”，不要一开始陷入解析细节。

3. 接着进入主抓取实现文件，寻找最外层的 `crawl`、`crawler`、`createCrawler` 或类似入口。重点看输入参数如何被转成请求、请求结果如何进入解析器。

4. 然后阅读 parser 相关目录，理解 HTML 到正文结构的转换。这里适合关注数据形状、失败兜底和内容裁剪策略，而不是逐行研究每个选择器。

5. 最后看测试文件。测试通常能说明作者最在意的边界：重定向、乱码、空页面、非 HTML、超时、异常状态码、metadata 缺失等。

如果目录较大，建议不要按文件名逐个打开，而是围绕“入口、主流程、类型、测试”四条线阅读。

## 常见误区

第一个误区是把 `packages/web-crawler` 当成前端页面功能目录。按路径和命名，它更像底层 package，应该服务于上层工具、服务或 agent 流程，而不是直接渲染 UI。

第二个误区是只看 HTML 解析逻辑，不看请求边界。网页抓取的稳定性往往不在“能不能解析一个正常页面”，而在超时、重定向、状态码、内容类型、编码和异常归一。

第三个误区是把抓取结果等同于原始 HTML。对 LobeHub 这类 AI Agent Workspace 来说，上层通常需要的是干净、结构化、可投喂模型或工具链的内容，而不是完整网页源码。

第四个误区是忽略运行环境。抓取能力如果运行在 Node.js、Edge Runtime、Electron 或浏览器中，可用 API、网络权限、依赖体积和安全边界都不同。没有确认 `package.json` 与调用方之前，不应假设它能在所有环境运行。

第五个误区是过早推断真实 API 名称。当前可读上下文没有确认到目录存在，因此本文中出现的 `crawl`、`createCrawler`、`CrawlResult` 等名称只是合理示例，不代表现有源码事实。

第六个误区是把目录缺失当作功能不存在的绝对结论。更稳妥的说法是：在当前可读片段中，目标路径未出现；如果完整仓库或生成后的 workspace 中另有该目录，需要以实际 `packages/web-crawler/package.json` 和 `src/index.ts` 为准重新校准。
