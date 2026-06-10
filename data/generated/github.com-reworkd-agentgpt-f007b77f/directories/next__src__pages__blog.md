# 子系统：next/src/pages/blog

## 解决什么问题

`next/src/pages/blog` 是博客详情页子系统，负责把单篇文章映射到 `/blog/[slug]` 路由，并在构建期或请求期读取本地文章文件生成页面。它不是完整博客模块的全部入口：博客列表页位于 `next/src/pages/blog.tsx`，文章数据读取位于 `next/src/lib/posts.ts`，目标目录下的 `next/src/pages/blog/[slug].tsx` 主要承担“文章详情页”的职责。

从 Next.js Pages Router 角度看，`[slug].tsx` 是动态路由页面。它通过 `getStaticPaths()` 预先枚举文章 slug，通过 `getStaticProps()` 读取对应文章内容，再由 `BlogPost` 组件渲染页面。页面视觉上复用站点公共外壳，包括 `AppHead`、`NavBar`、`FadeIn`、`FooterLinks`，并使用 `ReactMarkdown` 将文章正文渲染为 HTML。

## 相关目录和文件

`next/src/pages/blog/[slug].tsx` 是本子系统核心文件，定义动态详情页、静态路径生成和静态属性注入。

`next/src/pages/blog.tsx` 是上游列表页。它调用同一个 `getSortedPostsData()` 获取文章元数据，展示封面、标题、日期、分类、作者信息，并通过 `router.push("/blog/${id}")` 进入详情页。

`next/src/lib/posts.ts` 是数据访问层。它使用 Node 的 `fs`、`path` 读取 `process.cwd()/posts` 下的 `.mdx` 文件，并用 `gray-matter` 解析 frontmatter。`getSortedPostsData()` 面向列表页和路径生成，`getPostData()` 面向详情页正文读取。

`next/package.json` 声明了关键依赖：`gray-matter` 用于解析文章头部元数据，`react-markdown` 用于在详情页渲染正文内容。根据当前片段推断，文章文件虽然使用 `.mdx` 扩展名，但当前详情页并没有走 MDX 编译管线，而是把正文当作普通 Markdown 交给 `ReactMarkdown`。

`next/src/components/NavBar.tsx` 提供博客入口。导航项中包含 `Blog`，指向 `/blog`，因此用户主要先进入列表页，再跳转到 `/blog/[slug]`。

## 核心对象

`BlogPost` 是详情页 React 组件，接收 `postData`，其中至少包含 `title`、`date`、`content`。当前实现实际只渲染 `date` 和 `content`，标题没有直接使用，页面头部固定显示 `Reblogd`，浏览器标题固定为 `Reworkd Blog`。

`getStaticPaths()` 是动态路由的路径发现函数。它调用 `getSortedPostsData()`，从每篇文章的文件名生成 `id`，再转成 `{ params: { slug: id } }`。返回值中 `fallback: true`，意味着没有在构建期生成的 slug 也可能在首次访问时尝试生成页面。

`getStaticProps()` 是详情页的数据注入函数。它从 `params.slug` 读取对应文章，调用 `getPostData(slug)` 得到 frontmatter 和正文内容，然后作为 `postData` 传入组件。

`getSortedPostsData()` 读取文章目录下所有 `.mdx` 文件，解析 frontmatter，将文件名去掉 `.mdx` 后作为 `id`，并按 `date` 倒序排序。它既服务 `/blog` 列表展示，也服务详情页的静态路径生成。

`getPostData()` 根据 slug 读取单个 `${slug}.mdx` 文件，返回 `slug`、frontmatter 字段和 `content`。详情页渲染正文依赖这里返回的 `content`。

## 运行流程

用户从导航栏进入 `/blog` 时，`next/src/pages/blog.tsx` 在构建期通过 `getStaticProps()` 读取文章列表。列表页渲染每篇文章的封面、日期、分类、标题和作者信息。点击某篇文章后，客户端使用 `next/router` 跳转到 `/blog/${id}`。

访问 `/blog/[slug]` 时，Next.js 会匹配到 `next/src/pages/blog/[slug].tsx`。构建阶段，`getStaticPaths()` 先扫描文章列表并生成已知 slug 的静态路径。对每个路径，`getStaticProps()` 读取对应文章内容。页面组件收到 `postData` 后，先判断 `router.isFallback`：如果当前页面处于 fallback 生成阶段，则显示 `Loading...`；数据准备好后渲染完整页面。

详情页布局先放置公共头部和导航，再进入带星空背景动画的内容区域。正文区域展示文章日期，并把 `postData.content` 传给 `ReactMarkdown`。页面底部复用 `FooterLinks` 和版权文本。整体样式主要依赖 Tailwind CSS class，例如 `prose`、`text-white`、`bg-stars`、`animate-stars` 等。

## 上下游依赖

上游依赖首先是本地文章目录。`next/src/lib/posts.ts` 使用 `path.join(process.cwd(), "posts")` 定位文章，因此运行 Next.js 的当前工作目录必须与 `posts` 目录位置匹配。根据当前片段推断，在常见 monorepo 运行方式下，应用可能从 `next` 目录启动，此时文章目录应是 `next/posts`；如果从仓库根目录直接启动而根目录没有 `posts`，读取会失败。

第二个上游是文章 frontmatter 结构。列表页期待字段包括 `title`、`date`、`imageUrl`、`category`、`author`；详情页最低依赖 `date` 和 `content`，但类型标注中也出现 `title`。如果文章元数据缺失，列表页比详情页更容易直接报错，尤其是 `category.title`、`author.imageUrl`、`author.name`、`author.role` 这类嵌套字段。

下游主要是 Next.js 静态生成系统和客户端路由系统。`getStaticPaths()`、`getStaticProps()` 决定页面能否被构建；`router.isFallback` 决定 fallback 页面状态；`ReactMarkdown` 决定正文最终可渲染的 Markdown 能力边界。

公共 UI 依赖包括 `AppHead`、`NavBar`、`FadeIn`、`FooterLinks`。这些组件决定页面头信息、导航入口、动效和页脚，与博客数据本身解耦，但会影响页面结构、滚动行为和视觉一致性。

## 修改时最容易踩的坑

第一，`.mdx` 文件并不等于当前页面支持完整 MDX。详情页使用的是 `ReactMarkdown`，不会执行 MDX 中的 JSX 组件或 import 语句。如果新增文章写了 MDX 组件语法，可能无法按预期渲染，甚至显示异常。

第二，`fallback: true` 但 `getStaticProps()` 没有处理不存在的 slug。访问不存在的文章时，`getPostData()` 会直接读取文件，文件缺失会触发异常。更稳妥的做法通常是捕获缺失文件并返回 `notFound: true`，否则线上可能出现 500。

第三，`postsDirectory` 依赖 `process.cwd()`。这对本地开发、构建脚本、部署平台都敏感。修改启动目录、移动 `posts` 目录、或者从仓库根目录运行 Next.js，都可能导致文章读取路径变化。

第四，类型定义偏弱。`SlugData` 使用 `[key: string]: string`，但列表页实际使用的 `category`、`author` 是对象结构；`BlogPage` 的 props 也没有明确类型。修改 frontmatter 时，TypeScript 不一定能提前暴露结构错误，运行时才会发现。

第五，列表页和详情页展示字段不一致。列表页展示标题、封面、分类、作者，详情页只展示日期和正文，`postData.title` 没有进入正文标题区域。如果希望详情页显示文章标题，需要同步调整 `BlogPost` 的渲染和可能的 SEO 标题。

第六，图片使用普通 `<img>`，不是 `next/image`。如果调整为远程图片或 Next 图片优化，需要同时检查 `next.config.mjs` 的图片域名配置，否则构建或运行时可能失败。

## 推荐阅读顺序

1. 先读 `next/src/pages/blog.tsx`，理解博客列表页如何拿到文章元数据，以及用户如何从列表跳转到详情页。
2. 再读 `next/src/pages/blog/[slug].tsx`，重点看 `BlogPost`、`getStaticPaths()`、`getStaticProps()` 三部分，掌握动态路由和静态生成关系。
3. 接着读 `next/src/lib/posts.ts`，确认文章目录位置、slug 生成规则、frontmatter 解析方式和排序逻辑。
4. 然后查看实际 `posts` 目录下的 `.mdx` 文章样例，重点关注 frontmatter 字段，而不是正文内容。
5. 最后读 `next/src/components/NavBar.tsx`、`AppHead`、`FooterLinks`、`FadeIn` 等公共组件，理解博客页面如何接入全站导航、头信息、动效和页脚。
