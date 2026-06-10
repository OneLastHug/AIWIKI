# 文件：packages/coding-agent/src/core/extensions/loader.ts
## 一句话定位
这是 `coding-agent` 的扩展装载中枢，负责把磁盘上的扩展文件、目录和内联工厂函数变成可执行的 `Extension` 实例，并把它们接入共享的 `ExtensionRuntime`、`EventBus` 和 `ExtensionAPI`。

## 它暴露/定义了什么
对外主要暴露四个入口：`createExtensionRuntime`、`loadExtensionFromFactory`、`loadExtensions`、`discoverAndLoadExtensions`。另外还定义了一组内部支撑函数，比如 `createExtensionAPI`、`loadExtensionModule`、`createExtension`、`loadExtension`、`discoverExtensionsInDir` 和 `resolveExtensionEntries`。  
从结构上看，这个文件既是“加载器”，也是“适配层”：前者负责发现和读取扩展，后者负责把扩展运行所需的能力包装成统一 API。

## 谁调用它
根据当前片段推断，真实运行时上游是 `packages/coding-agent/src/core/resource-loader.ts`：它在装配资源时直接导入 `loadExtensions`、`loadExtensionFromFactory` 和 `createExtensionRuntime`，再把结果塞进 `resourceLoader.getExtensions()`。`packages/coding-agent/src/core/index.ts` 还会把这些能力继续导出，供更高层使用。  
直接调用方里，测试覆盖很重，像 `extensions-discovery.test.ts`、`extensions-runner.test.ts`、`sdk-skills.test.ts`、`utilities.ts` 都会直接拉起这里的函数来验证扩展发现、加载和运行时行为。

## 它调用谁
它依赖的外部模块很明确：`jiti/static` 负责动态加载 TypeScript/JavaScript 扩展；`node:fs`、`node:path`、`node:url` 和 `node:module` 做文件与路径解析；`resolvePath`、`getAgentDir`、`CONFIG_DIR_NAME` 来自配置与路径工具；`createEventBus`、`execCommand`、`createSyntheticSourceInfo` 则把扩展接到事件、执行命令和源信息系统上。  
它还依赖 `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai`、`@earendil-works/pi-tui`、`typebox` 等静态包名，并在 Bun 二进制模式下通过 `virtualModules` 暴露这些包。

## 核心流程
核心链路可以看成四步。第一步，`discoverAndLoadExtensions` 先合并三类来源：项目本地 `CONFIG_DIR_NAME/extensions`、全局 `agentDir/extensions`、以及显式配置的路径，并做去重。第二步，`loadExtensions` 逐个路径调用 `loadExtension`，统一收集成功的 `Extension` 和失败原因。第三步，`loadExtension` 先解析真实路径，再用 `loadExtensionModule` 载入工厂函数，随后通过 `createExtension` 建立空壳扩展对象，再用 `createExtensionAPI` 把注册接口和运行时能力注入进去，最后执行扩展工厂。第四步，`createExtensionRuntime` 提供一套带“未初始化”保护的运行时，等待更上层的 session/runner 绑定真实实现。  
目录发现规则也很清楚：先看 `package.json` 里的 `pi.extensions`，再看 `index.ts`/`index.js`，最后才扫描目录下直接的 `.ts` / `.js` 文件；`discoverExtensionsInDir` 不做多层递归，复杂包必须显式声明入口。

## 关键函数的高层作用
`createExtensionRuntime` 是安全边界，它用抛错 stub、`staleMessage` 和 `pendingProviderRegistrations` 保证扩展在错误时机调用能力会被拦住。  
`createExtensionAPI` 是扩展侧 API 的拼装器，注册类方法直接写入扩展对象，动作类方法转发到 runtime。  
`loadExtensionModule` 负责兼容 Node 开发态和 Bun 二进制态的模块解析差异。  
`loadExtension` 是单个扩展的失败隔离点。  
`discoverAndLoadExtensions` 是最上层入口，负责“发现 + 排序 + 去重 + 加载”一体化执行。

## 修改风险
这个文件的风险主要在加载链路和兼容性。第一，`alias` / `virtualModules` 的映射一旦和实际包名、打包产物不一致，Bun binary 和开发态都会出现“能编译、不能加载”的问题。第二，路径解析、符号链接去重、`package.json` manifest 规则都影响扩展的可见性，改动会直接改变用户装载结果。第三，`runtime.assertActive()` 和 `invalidate()` 这类保护逻辑很敏感，改坏后容易出现“延迟回调继续写旧 session”的隐性错误。第四，扩展加载顺序会影响命令、工具、flag 和 provider 的最终注册结果，合并策略不能随意调整。  
如果要动这里，优先检查：Bun/Node 两种模式是否都能加载、目录发现是否仍符合测试预期、以及 `resource-loader.ts` 的上游调用是否还拿得到同样结构的 `extensionsResult`。
