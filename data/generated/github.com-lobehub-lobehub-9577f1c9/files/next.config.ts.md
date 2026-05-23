# 文件：next.config.ts

## 一句话定位
这是仓库的 Next.js 根配置入口，负责把环境判断结果和站点级构建策略交给 `src/libs/next/config/define-config.ts`，最终生成 Next.js 读取的默认配置。

## 它暴露/定义了什么
它默认导出一个 `nextConfig`。这个对象本身不展开大量业务细节，而是先判断当前是否处于 Vercel 环境，再为 Vercel 注入一组额外的 `outputFileTracingExcludes`。这些排除项主要针对 musl 版本原生依赖，以及 SPA、桌面端、移动端构建产物和数据库迁移文件。

## 谁调用它
根据当前片段推断，调用方是 Next.js 自身的构建与运行入口，也就是 `next dev`、`next build`、`next start` 这类命令。仓库里 `package.json` 的 `dev:next`、`build:next:raw`、`start` 都会间接触发它。在 Vercel 部署时，Next.js 也会自动读取这个文件，`process.env.VERCEL_ENV` 就是这里用来识别平台的依据。

## 它调用谁
它只显式调用了 `src/libs/next/config/define-config.ts` 里的 `defineConfig`。这个包装函数才是真正的配置组装器，会继续合并 headers、redirects、logging、reactStrictMode、experimental 以及 tracing 相关配置。也就是说，`next.config.ts` 只负责给总配置器喂一个环境特定的补充参数。

## 核心流程
先判断 `process.env.VERCEL_ENV`，得到 `isVercel`。如果是 Vercel，就准备 `vercelConfig`，核心内容是 `outputFileTracingExcludes`。这组排除规则的意图很明确：让 Vercel 的 serverless 打包不要把不需要的 musl 二进制、桌面和 SPA 构建产物、迁移文件一起带上，减少函数体积。随后把这个对象传给 `defineConfig`，由后者统一拼装成最终 NextConfig。根据当前片段推断，整体设计是“根文件做平台分支，通用规则下沉到共享配置函数”。

## 关键函数的高层作用
`defineConfig` 的作用是把仓库级通用策略集中起来。它不仅设置 `output: 'standalone'`、安全响应头、缓存头、重定向和日志选项，还会根据 `DOCKER`、`NEXT_BUILD_STANDALONE`、`ENABLED_CSP` 等环境变量改变构建形态。`next.config.ts` 这层没有再做复杂计算，只是把 Vercel 特有的 tracing 排除项接进去。

## 修改风险
这类文件的改动风险很高，因为它影响整个应用的构建、部署和静态资源访问。改错 `outputFileTracingExcludes` 可能导致 Vercel 上函数体积暴涨，或者把运行时实际需要的文件排除掉，造成线上缺依赖。改动 headers、redirects 或 tracing 策略，也可能引发缓存失效、SEO 跳转异常、PWA/站点验证文件不可用等问题。另一个常见风险是只考虑本地 `next dev`，忽略了 Vercel 与 Docker 的差异，导致本地可用、线上报错。
