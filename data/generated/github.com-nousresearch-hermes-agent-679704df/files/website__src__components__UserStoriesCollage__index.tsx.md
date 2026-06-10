# 文件：website/src/components/UserStoriesCollage/index.tsx

## 一句话定位

`website/src/components/UserStoriesCollage/index.tsx` 是 Docusaurus 文档站里的“用户故事/用例墙”组件：它把 `website/src/data/userStories.json` 中的故事数据渲染成可按分类和来源筛选的瀑布流卡片页，用于展示社区真实使用 Hermes Agent 的案例。

## 它暴露/定义了什么

该文件默认导出一个 React 函数组件 `UserStoriesCollage()`。组件内部还定义了几个局部结构和配置：

- `Story` interface：描述单条故事数据的字段，包括 `id`、`source`、`author`、`url`、`date`、`category`、`headline`、`quote`、`size`。
- `allStories`：把导入的 JSON 数据断言为 `Story[]`，作为页面唯一数据源。
- `CATEGORIES`：分类元数据表，把 `category` key 映射为展示标签、主色、浅色背景和顶部渐变条。
- `SOURCE_LABELS`：来源元数据表，把 `source` key 映射为更友好的平台名称。
- `sourceColor(source)`：根据来源返回对应徽标颜色。

这个文件没有暴露额外命名导出，也没有对外提供数据处理 API；它的主要边界就是一个可嵌入 MDX 页面的展示组件。

## 谁调用它

当前检索到的直接调用方是 `website/docs/user-stories.mdx`。该 MDX 文件通过：

`import UserStoriesCollage from '@site/src/components/UserStoriesCollage';`

引入组件，并直接渲染 `<UserStoriesCollage />`。根据当前片段推断，这个 MDX 文件由 Docusaurus docs 系统生成对应的用户故事页面；依据是文件位于 `website/docs` 下，带有 frontmatter，并设置了 `hide_title`、`hide_table_of_contents`，说明页面主体完全交给该组件渲染。

## 它调用谁

组件主要依赖三类对象：

- React：使用 `useState` 管理当前选中的分类和来源，使用 `useMemo` 缓存计数和筛选结果。
- 数据文件：从 `@site/src/data/userStories.json` 读取故事列表。新增、删除、调整故事内容时，通常应改这个 JSON，而不是改组件逻辑。
- CSS Module：从 `./styles.module.css` 导入 `styles`，负责页面布局、筛选按钮、瀑布流列布局、卡片尺寸、hover 效果、暗色主题适配等视觉细节。

它还生成普通 `<a>` 外链卡片和页脚外链。文档中不展开真实地址，可理解为卡片链接到每条故事的来源，页脚引导用户编辑 `userStories.json` 或到社区提交故事。

## 核心流程

组件初始化时默认 `activeCategory = 'all'`、`activeSource = 'all'`，即展示全部故事。

第一步，基于 `allStories` 计算两个计数字典：`categoryCounts` 统计每个分类下有多少故事，`sourceCounts` 统计每个来源下有多少故事。这两个结果用于顶部摘要数字，也用于决定哪些筛选按钮应该出现。

第二步，基于当前筛选状态计算 `visible`。如果分类不是 `all`，只保留同分类故事；如果来源不是 `all`，只保留同来源故事。两个条件是交集关系，因此用户可以同时按分类和来源过滤。

第三步，渲染页面头部。头部展示标题、说明文案，以及故事总数、分类数、来源数。这里的数据都来自 JSON 的实际内容，因此添加故事后统计会自动变化。

第四步，渲染两行筛选按钮。第一行是分类筛选，先显示 `All`，再显示 `CATEGORIES` 中存在且当前数据里有计数的分类，并按故事数量从高到低排序。第二行是来源筛选，先显示 `All sources`，再显示 `SOURCE_LABELS` 中存在且当前数据里有计数的来源。点击按钮只是更新本地 state，不会改 URL，也不会触发后端请求。

第五步，渲染卡片网格。如果 `visible` 为空，显示空状态文案；否则遍历 `visible` 生成一组 `<a>` 卡片。每张卡片会根据分类拿到颜色变量，根据 `size` 选择 `tileSm`、`tileMd` 或 `tileLg` 样式，根据 `source` 显示来源徽标颜色。卡片内容包括来源、分类、标题、引用、作者、日期和外链箭头。

最后，渲染页脚，引导用户补充自己的故事。页脚仍然是静态文案加外链，不参与筛选流程。

## 关键函数的高层作用

`UserStoriesCollage()` 是唯一核心函数。它承担数据聚合、筛选状态管理和完整 UI 渲染三件事：从 JSON 得到原始故事，派生计数和可见列表，再把这些派生结果映射为筛选按钮与瀑布流卡片。

`sourceColor(source)` 是辅助函数，用固定映射给不同来源分配颜色。它不影响数据筛选，只影响来源徽标和激活来源按钮的视觉呈现。

`categoryCounts`、`sourceCounts`、`visible` 虽然不是独立函数，但属于组件的核心派生数据。它们通过 `useMemo` 表达“由故事数据和筛选状态计算得到”的关系，避免每次渲染时把这些逻辑散落到 JSX 中。

`CATEGORIES` 和 `SOURCE_LABELS` 是配置表。它们决定哪些分类/来源有漂亮标签和颜色；数据中出现未登记的分类时，卡片会回退到 `general` 分类，但分类筛选按钮不会自动显示该未知分类，因为按钮来自 `CATEGORIES` 的 entries。数据中出现未登记的来源时，卡片会显示原始 `source` 值，但来源筛选按钮也不会自动显示，因为按钮来自 `SOURCE_LABELS`。

## 修改风险

主要风险在数据 key 与配置表不一致。`userStories.json` 的 `category` 如果没有加入 `CATEGORIES`，卡片可显示但会用 `general` 样式，并且用户无法通过分类按钮筛到它；`source` 如果没有加入 `SOURCE_LABELS`，卡片可显示原始来源名，但不会出现在来源筛选行中。新增分类或来源时应同时更新 JSON 和对应元数据表。

第二个风险是类型只在组件里用 `as Story[]` 断言，运行时没有校验。JSON 中如果缺少 `id`、`url`、`headline`、`quote` 等字段，构建可能不一定立刻失败，但页面会出现空文本、错误链接或 React key 问题。`size` 不是 `sm`、`md`、`lg` 时会落到 `tileMd`，这属于隐式容错。

第三个风险是视觉布局高度依赖 `styles.module.css`。网格使用 CSS columns 和 `break-inside: avoid` 做瀑布流，而不是 JS masonry；改卡片 padding、min-height、quote clamp 或 column-count 可能改变页面密度和响应式表现。长标题、长作者名、长引用尤其容易影响移动端观感。

第四个风险是筛选状态不进入 URL。当前交互简单、无分享筛选结果的需求；如果未来要支持可复制筛选链接，需要引入路由 query 或 hash，同步 state 时要避免 Docusaurus 静态渲染与浏览器环境差异。

第五个风险是外链安全和内容可信度。卡片和页脚外链使用 `target="_blank"` 与 `rel="noopener noreferrer"`，这是必要的；新增外链渲染时应保持这一模式。由于页面展示真实社区来源，修改文案或数据采集方式时还要注意不要把来源、作者、日期和引用关系搞混。
