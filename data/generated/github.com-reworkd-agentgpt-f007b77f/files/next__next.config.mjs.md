# 文件：next/next.config.mjs

## 一句话定位

`next/next.config.mjs` 是 `next` 子应用的 Next.js 全局配置入口，负责在应用启动、开发、构建阶段把环境变量校验、国际化路由、webpack 能力扩展和特定域名重写规则接入到 Next.js 运行链路中。

## 它暴露/定义了什么

该文件默认导出一个 `NextConfig` 对象 `config`。它定义了四类关键配置：第一，`reactStrictMode: true`，让 React 在开发环境启用更严格的副作用检查；第二，`i18n: nextI18NextConfig.i18n`，把 `next-i18next` 的语言列表与默认语言交给 Next.js 路由系统；第三，`webpack(config, options)`，在 Next.js 内部 webpack 配置基础上追加 WebAssembly、layer 和 SVG 组件化能力；第四，`rewrites()`，声明基于 host 的请求重写规则。

文件顶部还有一个重要的顶层副作用：当没有设置 `SKIP_ENV_VALIDATION` 时，动态导入 `./src/env/server.mjs`。这不是业务功能，而是构建和启动前的环境变量守门逻辑。

## 谁调用它

直接调用者是 Next.js CLI 与运行时。根据 `next/package.json`，`dev` 执行 `next dev`，`build` 执行 `next build --no-lint`，`start` 执行 `next start`，这些命令都会读取项目根下的 `next.config.mjs` 并应用其中配置。`next/jest.config.cjs` 的注释也表明测试环境会通过 Next/Jest 加载 Next 配置和 `.env` 文件。

业务代码通常不直接 import 这个文件。它更像框架层契约：开发服务器、生产构建器、生产服务进程读取它，然后把配置结果反向影响页面路由、资源编译和请求处理。

## 它调用谁

它显式依赖 `next/next-i18next.config.js`，只取其中的 `i18n` 字段交给 Next.js。该配置定义了 `defaultLocale: "en"`、多语言 `locales`、命名空间 `ns`、`localePath` 等，但在本文件里只有语言路由部分进入 Next.js 原生配置，其余部分仍由页面层和 `appWithTranslation` 等 `next-i18next` 机制使用。

它还按条件调用 `next/src/env/server.mjs`。该文件进一步调用 `./client.mjs`、`./schema.mjs` 中的 `clientEnv`、`formatErrors`、`serverSchema`、`serverEnv`，通过 schema 校验服务端环境变量，并阻止服务端变量误以 `NEXT_PUBLIC_` 暴露。

在 webpack 配置中，它调用的是 Next.js 传入的 webpack `config` 对象：修改 `experiments`、`watchOptions`，并向 `config.module.rules` 追加 `@svgr/webpack` loader。

## 核心流程

启动或构建时，Next.js 首先加载 `next.config.mjs`。文件执行到顶部条件导入：如果环境变量 `SKIP_ENV_VALIDATION` 不存在，就加载 `src/env/server.mjs`；该模块会校验环境变量，不通过则打印错误并抛出异常，从而中止构建或启动。注释说明跳过校验主要用于 Docker 构建等场景。

随后文件构造 `config`。Next.js 读取 `reactStrictMode` 与 `i18n`，将严格模式和多语言路由注册进框架层。构建资源时，Next.js 调用这里定义的 `webpack` 函数，并把内部生成的 webpack 配置传入；该函数原地修改配置后返回，使项目可以 import SVG 为 React 组件，同时启用异步 WebAssembly。处理请求路由时，Next.js 调用 `rewrites()` 获取规则：当请求 host 匹配 `reworkd.ai` 且路径为任意 `/:path*` 时，在 `beforeFiles` 阶段把请求导向 `/landing-page`。

## 关键函数的高层作用

`webpack(config, options)` 是资源编译扩展点。它保留 Next.js 生成的大部分默认配置，只做三处增强：开启 `asyncWebAssembly` 和 `layers` 实验能力；设置文件监听轮询参数，适配 Docker、远程文件系统或某些宿主机文件通知不可靠的开发环境；增加 `.svg` 规则，让从 `.js/.ts/.jsx/.tsx` 发起的 SVG import 交给 `@svgr/webpack`，因此类似 `import HomeIcon from ".../icon-home.svg"` 的代码可以把 SVG 当 React 组件使用。`options` 当前未使用，属于 Next.js webpack hook 的标准参数。

`rewrites()` 是请求改写配置函数。它返回 `beforeFiles` 规则，表示在 Next.js 检查页面文件和静态文件之前先尝试重写。当前规则把特定 host 的所有路径转到 `/landing-page`，根据当前片段推断，这是为了让主域访问统一落到营销落地页，而不影响其他 host 下的普通应用路由；依据是 `source: '/:path*'`、`has.type: 'host'` 和 `destination: '/landing-page'` 的组合。

顶层 `await import("./src/env/server.mjs")` 不是函数，但它是本文件最关键的控制点之一。它把环境变量错误提前暴露在启动/构建阶段，避免应用运行到请求期才失败。

## 修改风险

修改 `i18n` 接入会影响 Next.js 的本地化路由生成、静态页面路径和语言切换行为。尤其 `next-i18next.config.js` 同时被多个页面直接引用，如果这里只改 `next.config.mjs` 而没有同步语言资源、命名空间或页面层配置，可能出现构建通过但页面翻译缺失、路由不匹配的问题。

修改环境校验跳过逻辑风险较高。移除 `src/env/server.mjs` 的导入会降低本地和 CI 对配置错误的发现能力；滥用 `SKIP_ENV_VALIDATION` 可能让缺失的密钥、数据库地址或模型服务配置进入运行时才报错。反过来，在 Docker 构建阶段强制校验也可能因为构建时没有注入运行时环境变量而导致镜像无法构建。

修改 `webpack` 时要注意覆盖而不是合并的问题。当前代码直接赋值 `config.experiments = { asyncWebAssembly: true, layers: true }`，如果未来 Next.js 或其他插件预先写入了更多 `experiments` 字段，直接覆盖可能造成隐藏回归。`config.module.rules.push` 影响所有从 TS/JS 发起的 `.svg` import；若改动 test、issuer 或 loader，`NavBar`、`HeroCard`、`landing` 组件中的 SVG 图标可能无法作为组件渲染。

修改 `watchOptions` 主要影响开发体验。轮询间隔过低会增加 CPU 消耗，过高会导致热更新延迟；删除轮询可能让容器或挂载目录中的文件变化无法被及时检测。

修改 `rewrites()` 的风险集中在路由劫持。当前 host 规则匹配 `reworkd.ai` 的所有路径，并在 `beforeFiles` 阶段生效；如果 destination 页面不存在、host 条件写错，或把规则扩大到所有域名，可能导致应用主页面、API-like 页面或静态资源访问被意外导向 `/landing-page`。此外，因为该规则没有在源码中解释业务背景，调整前应确认部署域名策略和 `/landing-page` 页面是否仍是预期入口。
