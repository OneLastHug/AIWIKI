# 文件：komga-webui/fork-ts-checker.config.js

## 它负责什么

这个文件是 `fork-ts-checker-webpack-plugin` 的配置入口，核心作用只有一件事：把 TypeScript 校验进程的内存上限提高到 `4096` MB，也就是 4 GB。

从当前仓库片段看，`komga-webui` 使用的是 Vue CLI 构建链，`package.json` 里的 `serve`、`build`、`lint` 都走 `vue-cli-service`。同时依赖里有 `@vue/cli-plugin-typescript` 和 `fork-ts-checker-webpack-plugin`。因此可以合理推断，这个文件是给构建期的独立类型检查 worker 用的，不是给应用运行时用的。

## 关键组成

这个文件内容非常短，只有一层导出：

```js
module.exports = {
  typescript: {
    memoryLimit: 4096,
  },
}
```

其中最关键的是：

- `module.exports`：CommonJS 导出，供构建工具直接读取
- `typescript.memoryLimit`：控制 TypeScript checker 进程的堆内存上限
- `4096`：单位是 MB，表示 4 GB

它没有任何业务逻辑，也没有别的参数，说明它是一个纯构建配置文件。

## 上下游关系

上游是构建入口和 Vue CLI 配置：

- `komga-webui/package.json` 中的 `serve`、`build`、`lint`
- `komga-webui/vue.config.js`，这里定义了 `publicPath`、`devServer`、`configureWebpack`
- `komga-webui/package-lock.json` 中存在 `fork-ts-checker-webpack-plugin`

下游是构建时的类型检查过程：

- webpack 在编译时启动 TypeScript 检查 worker
- worker 读取这个配置文件
- worker 按 `memoryLimit: 4096` 运行，减少大项目里类型检查因内存不足而失败的概率

根据当前片段推断，这个文件不是手动 import 到源码里的，而是被 Vue CLI / 插件按约定自动读取。证据是文件名非常贴近插件名，而且仓库没有显式的业务代码引用它。

## 运行/调用流程

1. 你执行 `npm run serve`、`npm run build` 或 `npm run lint`。
2. `vue-cli-service` 启动 Vue CLI 的构建链。
3. Vue CLI 在 webpack 流程里接入 TypeScript 检查插件。
4. 插件查找 `fork-ts-checker.config.js` 作为配置来源。
5. `typescript.memoryLimit` 生效，TypeScript 校验 worker 获得更大的堆内存。
6. 构建期间的类型检查更不容易因为大型项目、很多 `.ts/.vue` 文件而爆掉。

## 小白阅读顺序

1. 先看 `komga-webui/fork-ts-checker.config.js`，确认它只是在调内存。
2. 再看 `komga-webui/package.json`，理解哪些命令会触发它。
3. 接着看 `komga-webui/vue.config.js`，把它放进整个 Vue CLI 构建上下文里。
4. 最后再去看 `package-lock.json` 里 `fork-ts-checker-webpack-plugin` 的版本，确认依赖确实存在。

## 常见误区

- 这不是 TypeScript 的全局编译配置文件，不会改变语言语义，也不会影响运行时代码。
- 这不是 webpack 业务配置，只是给类型检查插件单独用的参数文件。
- `memoryLimit` 调大不是越大越好，它只是在项目规模变大时，避免 checker 进程内存不足。
- 这个文件通常不会被业务代码直接 import，所以改它不会在源码里立刻看到调用点变化。
- 看到 `4096` 不要误以为是固定性能优化，它只是给检查进程留出更大的内存空间。
