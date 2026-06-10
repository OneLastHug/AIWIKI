# 文件：docs/docs.json

## 一句话定位

`docs/docs.json` 是 `docs` 目录下的 Mintlify 文档站点总配置文件，负责定义 Reworkd 文档站的品牌外观、导航结构、API Reference 入口、全局链接、Logo、导航栏按钮和页脚社交信息；它不参与 AgentGPT/Next/FastAPI 的运行时业务逻辑，而是面向文档构建与托管流程。

## 它暴露/定义了什么

该文件以 JSON 形式暴露 Mintlify 可识别的站点配置。顶层 `$schema` 指向 Mintlify 的 `docs.json` schema，用于编辑器校验和平台解析；`theme` 指定使用 `mint` 主题；`name` 设置站点名称为 `Reworkd`；`background`、`colors`、`favicon`、`logo` 控制视觉风格和静态资源。

最核心的是 `navigation`。其中 `tabs` 定义两个一级页签：`Documentation` 和 `API Reference`。`Documentation` 下按 `Get Started`、`Features`、`Developers` 分组组织本地 `.mdx` 页面；`API Reference` 通过 `openapi` 字段接入远程 OpenAPI 描述，实际地址在本文中记为 `[URL已移除]`。`navigation.global.anchors`、`navbar.primary`、`footer.socials` 定义外部跳转入口，目标地址同样统一记为 `[URL已移除]`。

## 谁调用它

根据当前片段推断，直接调用者不是仓库内业务代码，而是 Mintlify 文档平台或 Mintlify CLI。依据是：仓库中只有 `docs/docs.json` 使用 Mintlify schema，`docs` 目录下存在 `introduction.mdx`、`features/exports/overview.mdx` 等 Mintlify 风格页面，并使用 `<Frame>`、`<CardGroup>`、`<Card>`、`<Info>` 等文档组件。仓库内没有发现其他源码显式 import 或读取 `docs/docs.json`。

README 中的 Docs 入口指向线上文档站，但那是用户访问入口，不是代码级调用。真正的消费链路通常是：文档托管服务或本地 Mintlify 预览工具读取 `docs/docs.json`，再根据其中的 `navigation` 找到对应 `.mdx` 页面并生成站点导航。

## 它调用谁

`docs/docs.json` 本身不是程序，没有函数调用。它通过配置“引用”三类对象。

第一类是本地文档页面，例如 `introduction`、`key-concepts`、`schemas`、`features/deduplication`、`features/exports/overview`、`developers/sdk` 等。这些值会被 Mintlify 解析为 `docs` 目录下对应的 `.mdx` 文件路径。

第二类是本地静态资源，例如 `/favicon.png`、`/images/logo.png`、`/images/logo-light.png`，对应 `docs/favicon.png`、`docs/images/logo.png`、`docs/images/logo-light.png`。

第三类是外部资源，包括 OpenAPI 描述、官网、GitHub、社交媒体等，原始地址均为真实网址，本文按要求写作 `[URL已移除]`。

## 核心流程

文档站构建或预览时，Mintlify 首先读取 `docs/docs.json`，根据 `$schema` 和自身规则校验配置结构。随后加载主题、颜色、背景、favicon、logo 等全局展示配置，确定站点的基础视觉外观。

接着 Mintlify 解析 `navigation.tabs`。当用户进入 `Documentation` 页签时，左侧导航会按 `groups` 展示 `Get Started`、`Features`、`Developers`。普通字符串页面会映射到同名 `.mdx`，例如 `introduction` 映射 `docs/introduction.mdx`；嵌套对象则生成二级分组，例如 `Features` 里的 `Exports` 分组继续包含 `features/exports/overview`、`features/exports/api-exports`、`features/exports/bulk-exports`。

当用户进入 `API Reference` 页签时，Mintlify 不再读取本地 `.mdx` 页面列表，而是通过 `openapi` 配置拉取远程 OpenAPI JSON，生成接口参考页。最后，`navigation.global`、`navbar`、`footer` 被用于渲染站点顶部或底部的全局跳转入口。

## 关键函数的高层作用

该文件没有函数、类或可执行逻辑，因此不存在传统意义上的“关键函数”。如果把关键配置块视作功能单元，`navigation.tabs` 是最重要的“入口编排单元”，决定用户能看到哪些文档、文档如何分组、API Reference 是否出现；`navigation.global`、`navbar.primary`、`footer.socials` 是“外链入口单元”，决定站点外围跳转；`logo`、`colors`、`background`、`favicon` 是“品牌呈现单元”，控制文档站的识别度和主题一致性。

辅助配置如 `theme`、`name` 相对简单，只提供站点级元信息；样板字段 `$schema` 主要服务于工具校验，不影响业务语义。

## 修改风险

最大风险是导航页面路径与实际 `.mdx` 文件不一致。比如删除或重命名 `docs/features/exports/api-exports.mdx` 后，没有同步修改 `features/exports/api-exports`，文档站可能出现构建失败、导航死链或页面不可访问。

第二类风险是嵌套导航结构写错。`tabs`、`groups`、`pages` 的层级需要符合 Mintlify schema；如果把页面字符串、分组对象、`openapi` 字段放错层级，可能导致整个导航渲染异常。

第三类风险是外部链接和 OpenAPI 地址稳定性。`API Reference` 依赖远程 OpenAPI JSON，如果该地址不可用、返回格式变化或权限策略变化，接口文档会失效。全局 anchors、navbar、footer 中的外链也会影响用户从文档跳转到产品、仓库或社交渠道的路径。

第四类风险是品牌资源路径。`/images/logo.png`、`/images/logo-light.png`、`/favicon.png` 必须能在 Mintlify 静态资源规则下被解析；移动图片或调整路径时要同步更新配置。

总体上，修改该文件不太会破坏应用运行时，但会直接影响公开文档站的信息架构、入口可见性、API 文档生成和品牌展示。对于新增文档页面，推荐先新增对应 `.mdx`，再把相对路径加入 `navigation.tabs`；对于删除页面，则必须先检查 `docs/docs.json` 中是否仍有引用。
