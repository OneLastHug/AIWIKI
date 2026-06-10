# 文件：docs/developers/api-keys.mdx

## 一句话定位

`docs/developers/api-keys.mdx` 是 Reworkd 文档站里面向开发者的 API key 获取与鉴权说明页，用来告诉组织用户如何创建 Reworkd 平台 API key，并在调用 Reworkd API 时通过 `Authorization: Bearer <YOUR-API-KEY>` 请求头完成认证。

## 它暴露/定义了什么

这个文件定义的是一个 Mintlify/MDX 文档页面，而不是运行时代码模块。它通过 frontmatter 暴露页面标题：

```mdx
---
title: API Keys
---
```

正文定义了三类用户可见内容：第一，说明使用 Reworkd API 前需要先为组织创建 API key；第二，描述创建 API key 的入口与步骤，包括进入组织 API key 页面、确认页面标题、点击 `New API key` 并设置合理过期时间；第三，给出 API 请求认证头格式。

它还嵌入了一个 `<Frame>` 组件，内部展示 `/images/organization-menu.png`，用于帮助用户从组织菜单进入设置页。这里的 `<Frame>` 不是本文件定义的组件，而是文档平台提供的 MDX 组件能力，当前文件只是在页面中引用它。

## 谁调用它

直接调用关系来自文档系统，而不是业务代码。

`docs/docs.json` 在 `navigation.tabs[].groups[]` 的 `Developers` 分组中注册了 `developers/api-keys`，因此文档站构建或运行时会把 `docs/developers/api-keys.mdx` 作为开发者导航下的页面加载出来。这个文件也被 `docs/features/exports/api-exports.mdx` 通过内部链接 `/developers/api-keys` 引用：API Exports 页面在介绍通过 API 导出数据前，会引导用户先阅读 API key 文档。

根据当前片段推断，另一个“调用者”是 Mintlify 文档渲染器。依据是 `docs/docs.json` 使用 Mintlify schema，且 `.mdx` 文件中出现了 `<Frame>`、`<CardGroup>`、`<Card>` 这类 Mintlify 风格组件。仓库里没有看到本文件被应用端代码 import，因此它更像静态文档内容，由文档站工具链按路径约定和导航配置解析。

## 它调用谁

这个页面主要依赖三类外部对象。

第一是 Mintlify/MDX 渲染环境。frontmatter、Markdown 列表、代码块、`<Frame>` JSX 标签都需要 MDX 渲染器处理。

第二是静态图片资源 `/images/organization-menu.png`。页面通过 `<img src="/images/organization-menu.png" />` 引用这张图，用于说明组织菜单位置。如果图片缺失或路径改变，页面文字仍可读，但视觉引导会失效。

第三是 Reworkd 认证与组织管理页面。原文中给了一个真实认证页面链接；在本文档中按要求不展开真实网址。该页面承担实际创建组织级 API key 的功能，`api-keys.mdx` 只负责说明入口和使用方式。

## 核心流程

从用户视角看，这个页面描述的是“创建凭证，再用凭证调用 API”的最短路径。

用户先进入组织 API key 管理页，可以直接访问指定入口，也可以从组织菜单下拉项里的设置按钮进入。页面要求用户确认自己处在 `Organization API Keys` 页面，避免进入个人设置、OpenAI key 设置或其他无关 API 配置。随后用户点击 `New API key` 创建新 key，并选择合理的过期时间。创建完成后，用户在调用 Reworkd API 时，把 key 放到 HTTP 请求头：

```http
Authorization: Bearer <YOUR-API-KEY>
```

从文档信息架构看，它的流程位置在 `Developers` 分组下，属于所有 API 调用前置知识；`API Exports` 页面依赖它补足鉴权前提，之后才继续讲 Outputs API 与 `created_after` 增量拉取参数。因此它不是某个具体 API 的参考页，而是跨 API 的认证准备页。

## 关键函数的高层作用

本文件没有 JavaScript/TypeScript 函数、类或导出的业务 API，因此不存在传统意义上的“关键函数”。

可以把其中几个 MDX 结构理解为页面级“关键构件”：frontmatter 的 `title: API Keys` 决定文档站页面标题与导航展示；`<Frame>` 负责把组织菜单截图包在文档平台的图片框样式中；`img` 标签加载具体截图；最后的 fenced code block 固定展示 HTTP 认证头格式，是用户真正复制到 API 客户端或脚本里的核心内容。

辅助内容包括三步有序列表和说明文字，它们只是承接用户操作流程，不包含条件分支、状态管理或数据处理逻辑。

## 修改风险

最大风险是混淆“Reworkd API key”和“OpenAI API key”。仓库里 `next/src/pages/settings.tsx`、`next/src/env/schema.mjs`、多语言 `settings.json` 和 `errors.json` 中大量出现 OpenAI API key，这些是 AgentGPT 应用调用 OpenAI 或用户自带 OpenAI key 的配置；而 `docs/developers/api-keys.mdx` 讲的是 Reworkd 组织级 API key，用于调用 Reworkd API。修改时如果把两者合并说明，会误导开发者把 OpenAI key 放进 Reworkd API 的 `Authorization` 头，或者反过来。

第二个风险是认证格式。`Authorization: Bearer <YOUR-API-KEY>` 是下游 API 文档和客户端示例的共同前提，不能随意改成 query 参数、普通 `api_key` header 或 Basic Auth，除非后端和 OpenAPI 参考同步变更。

第三个风险是导航与链接一致性。`docs/docs.json` 注册的是 `developers/api-keys`，`docs/features/exports/api-exports.mdx` 链接的是 `/developers/api-keys`。如果重命名文件、迁移目录或改 slug，需要同步更新导航和内部链接，否则 API Exports 的前置引导会断裂。

第四个风险是截图与 UI 文案过期。页面依赖 `organization-menu.png` 和 `Organization API Keys`、`New API key` 这些界面文字。如果认证后台 UI 改版，文档仍然能构建，但用户会找不到入口。修改这类说明时应同时检查截图、按钮名称、页面标题和实际后台流程。

第五个风险是外部入口稳定性。原文包含认证页面直达链接；如果认证域名、组织路径或 API key 管理入口变化，这个页面会成为所有 API 使用者的失败起点。由于该文件被 API Exports 页面引用，影响面不仅限于开发者章节，还会影响数据导出用户的首次接入体验。
