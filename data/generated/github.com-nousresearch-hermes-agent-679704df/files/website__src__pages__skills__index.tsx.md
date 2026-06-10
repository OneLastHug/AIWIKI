# 文件：website/src/pages/skills/index.tsx

## 一句话定位

`website/src/pages/skills/index.tsx` 是网站里的 Skills Hub 页面入口：它把预构建出的技能目录 JSON 渲染成可搜索、可筛选、可展开查看详情的 Docusaurus 页面。

## 它暴露/定义了什么

这个文件默认导出 `SkillsDashboard` React 组件，Docusaurus 会把它作为 `/skills` 页面使用。文件内还定义了页面专用的数据结构和 UI 单元：`Skill`、`IndexMeta`、`SkillCard`、`StatCard`，以及 `CATEGORY_ICONS`、`SOURCE_CONFIG`、`SOURCE_ORDER` 等展示配置。它不是通用组件库，职责集中在一个页面内：加载技能索引、维护筛选状态、计算可见列表、渲染搜索框、来源筛选、分类侧栏、卡片网格和加载更多按钮。

## 谁调用它

直接调用者是 Docusaurus 的 pages 约定：`website/src/pages/skills/index.tsx` 会被路由系统自动注册为 `/skills`。导航入口来自 `website/docusaurus.config.ts` 的 navbar 项 `{ to: '/skills', label: 'Skills' }`。构建前的数据准备由 `website/scripts/prebuild.mjs` 和 `website/scripts/extract-skills.py` 完成，但它们不调用 React 组件，只生成组件运行时要 fetch 的静态 JSON。

## 它调用谁

运行时主要调用 React Hooks：`useState` 管理搜索、筛选、展开项、分页和侧栏状态；`useEffect` 负责加载 JSON、搜索防抖和键盘快捷键；`useMemo` 缓存来源列表、分类统计和过滤结果；`useCallback` 固定事件处理器。页面外部依赖包括 `@theme/Layout` 提供 Docusaurus 页面框架，`./styles.module.css` 提供样式，浏览器 `fetch` 拉取 `/docs/api/skills.json` 与 `/docs/api/skills-meta.json`。技能详情文档链接按 `/docs/user-guide/skills/${skill.docsPath}` 拼出。

## 核心流程

页面挂载后，`SkillsDashboard` 的第一个 `useEffect` 并行 fetch `skills.json` 和 `skills-meta.json`。`skills.json` 必须返回数组，否则降级为空数组；`skills-meta.json` 失败时被忽略并使用空对象。加载成功后，组件会给每条 `Skill` 补一个 `_search` 字段，这是由 `buildSearchHaystack` 预先拼好的小写搜索文本，避免每次输入都重新拼接大量字段。

用户输入搜索词时，原始 `search` 立即更新，但真正参与过滤的是 150ms 后同步的 `debouncedSearch`。随后 `filtered` 根据来源、分类和 `_search.includes(q)` 得到结果。结果不会一次性全量渲染，而是先显示 `PAGE_SIZE = 60` 条，通过 “Show more” 增加 `visibleCount`。当搜索、来源或分类变化时，组件重置分页数量并收起已展开卡片。

页面结构上，顶部 hero 展示总量、刷新时间和统计卡；控制条提供搜索框和来源 pill；主体左侧是分类侧栏，右侧是 `SkillCard` 网格。点击卡片会展开详情，点击分类或标签会分别改变分类筛选或搜索词。

## 关键函数的高层作用

`SkillsDashboard` 是核心页面控制器，集中负责数据加载、状态管理、派生数据计算和页面布局。它的关键风险也最大，因为筛选性能、URL 路径、空状态、移动端侧栏都在这里耦合。

`SkillCard` 负责单个技能的展示和展开态详情。收起态显示名称、描述、来源、分类和平台；展开态显示 overview、环境变量、命令、标签、作者、版本、许可证、安装命令和文档链接。它通过 `stopPropagation()` 区分“点击卡片展开”和“点击内部按钮筛选/跳转”。

`buildSearchHaystack` 是性能优化点，把名称、描述、overview、分类标签、作者、tags 预处理为 `_search`。注释说明这是为大规模技能目录设计的，避免 50k+ 技能时每次按键都做 join 和 lower-case。

`formatRelativeTime` 把元数据里的 ISO 时间转成 “minutes/hours/days/months ago”，用于展示目录刷新时间；如果时间缺失或非法则返回 `null`。

`highlightMatch` 只高亮文本中的第一个匹配片段，用于卡片标题和描述。`StatCard` 是纯展示组件，用于 hero 区统计数字。

## 修改风险

最大风险是静态资源路径。文件硬编码 `SKILLS_URL = "/docs/api/skills.json"` 和 `META_URL = "/docs/api/skills-meta.json"`，这依赖 `website/docusaurus.config.ts` 中 `baseUrl: '/docs/'` 以及 `website/static/api/` 的发布规则。如果站点 baseUrl 改动，页面会直接加载失败。

第二个风险是数据契约。`SOURCE_CONFIG` 需要和 `website/scripts/extract-skills.py` 中的来源标签保持同步；新增来源如果只改提取脚本、不改这里，仍能显示，但会落到 optional 的默认样式，来源排序也不会出现在预期位置。`Skill` 字段也依赖提取脚本输出，尤其是 `docsPath`、`installCmd`、`categoryLabel`、`source`。

第三个风险是性能。这个页面面向大目录，已有防抖、预计算 `_search`、分页渲染等优化。把过滤逻辑改回每次 render 动态拼接字符串，或一次性渲染全部结果，都会让移动端和大数据集体验明显变差。

第四个风险是交互传播。`SkillCard` 整张卡片可点击展开，内部分类按钮、标签按钮、文档链接都依赖 `e.stopPropagation()`。新增内部交互时如果漏掉这一点，用户点击按钮可能同时触发展开/收起。

第五个风险是国际化和路径。页面文案基本写死为英文，并且文档链接固定拼到 `/docs/user-guide/skills/`。如果要适配 Docusaurus 多语言路由或改变技能文档目录，需要同时检查路由、生成脚本和卡片链接逻辑。
