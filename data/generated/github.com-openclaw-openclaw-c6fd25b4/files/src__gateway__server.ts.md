# 文件：src/gateway/server.ts

## 一句话定位

`src/gateway/server.ts` 是 Gateway Server 的轻量入口门面：它对外暴露启动服务器和测试缓存重置能力，但把真正的服务器实现延迟到 `src/gateway/server.impl.ts` 动态加载，以降低 Gateway 启动路径和测试路径的初始负担。

## 它暴露/定义了什么

这个文件暴露四类表面：

- `truncateCloseReason`：从 `src/gateway/server/close-reason.js` 重新导出，用于 WebSocket 或连接关闭原因的裁剪逻辑。
- `GatewayServer`、`GatewayServerOptions`：从 `src/gateway/server.impl.js` 重新导出的类型，保持调用方可以只依赖 `server.ts` 这个入口。
- `startGatewayServer(...)`：对外的主启动函数，参数和返回值直接绑定到 `server.impl.js` 中同名函数的类型。
- `resetModelCatalogCacheForTest()`：测试辅助入口，用于重置模型目录缓存。

文件内部还定义了两个辅助函数：`emitStartupTrace` 负责在环境变量开启时输出启动耗时；`loadServerImpl` 负责动态加载真正实现并记录导入耗时。

## 谁调用它

根据当前片段可见，直接调用者主要是需要启动 Gateway 的测试和脚本，例如 `scripts/tool-search-gateway-e2e.ts` 会导入 `startGatewayServer` 启动端到端测试用 Gateway；`src/gateway/server.shared-auth-rotation.test.ts` 也直接导入 `startGatewayServer` 验证共享认证轮换行为。

搜索结果还显示大量 Gateway 测试、CI 分片脚本和测试规划脚本把 `src/gateway/server.ts` 视为关键测试目标或特殊处理对象，例如 `test/vitest/vitest.shared.config.ts`、`test/vitest/vitest.gateway-server.config.ts`、`scripts/lib/ci-node-test-plan.mjs`。这些不一定都运行时调用它，但说明它是 Gateway server 测试矩阵中的中心入口。

根据当前片段推断，生产启动路径也很可能通过编译后的 `src/gateway/server.js` 间接进入，但本次读取到的直接证据主要来自脚本和测试导入。

## 它调用谁

运行时最重要的调用对象是 `src/gateway/server.impl.ts` 对应的 `./server.impl.js`。`startGatewayServer` 和 `resetModelCatalogCacheForTest` 都先调用 `loadServerImpl()`，再把实际工作委托给 `server.impl.js` 中的实现。

除此之外，它依赖：

- `src/gateway/server/close-reason.ts` 对应的 `./server/close-reason.js`，仅做 re-export。
- Node/运行时全局能力：`process.env.OPENCLAW_GATEWAY_STARTUP_TRACE` 控制是否打印 trace，`process.stderr.write` 输出 trace，`performance.now()` 计算耗时。

它没有直接创建 HTTP server、WebSocket server、插件运行时或模型目录；这些都被推迟到 `server.impl.ts`。

## 核心流程

第一步，模块被 import 时只建立轻量门面。除 `truncateCloseReason` 的静态 re-export 和类型导出外，它不会立刻加载完整 Gateway 实现。

第二步，调用方执行 `startGatewayServer(...)`。该函数先调用 `loadServerImpl()`，记录开始时间，再执行动态导入 `import("./server.impl.js")`。

第三步，不论动态导入成功还是失败，`finally` 都会计算导入耗时。如果设置了 `OPENCLAW_GATEWAY_STARTUP_TRACE`，`emitStartupTrace` 会向 stderr 输出类似 Gateway server implementation import 的耗时信息；未设置时完全静默。

第四步，动态导入成功后，`startGatewayServer` 把原始参数原样传给 `mod.startGatewayServer(...args)`，返回真正服务器启动函数的结果。

第五步，测试需要清理模型目录缓存时调用 `resetModelCatalogCacheForTest()`，它复用同一个动态加载路径，再调用 `mod.resetModelCatalogCacheForTest()`。

## 关键函数的高层作用

`startGatewayServer` 是公开主入口。它的价值不在于实现服务器逻辑，而在于维持稳定 API，同时把重依赖加载延迟到真正启动 Gateway 时。它的参数和返回值通过 `Parameters<typeof import(...).startGatewayServer>`、`ReturnType<typeof import(...).startGatewayServer>` 与实现文件绑定，减少门面和实现签名漂移。

`loadServerImpl` 是懒加载边界。它把 `server.impl.js` 从入口文件中拆出去，符合 `src/gateway/AGENTS.md` 对 Gateway hot path 的要求：Gateway server 测试和启动路径不应为了轻量场景过早物化完整插件运行时或宽泛注册表。

`emitStartupTrace` 是诊断辅助。它只在 `OPENCLAW_GATEWAY_STARTUP_TRACE` 存在时输出耗时，避免默认污染 stderr。它记录单段耗时和累计耗时，当前只用于 `gateway.server-impl-import`。

`resetModelCatalogCacheForTest` 是测试专用桥接函数。它保持测试仍可从轻量入口触达实现层的缓存重置逻辑，但生产路径不应依赖它表达业务行为。

## 修改风险

最大风险是破坏懒加载边界。若在 `src/gateway/server.ts` 新增静态导入 `server.impl.ts`、插件注册表、channel runtime 或模型目录实现，就会让所有导入 `server.ts` 的调用方提前加载完整 Gateway 依赖，违背 `src/gateway/AGENTS.md` 中的 hot path 约束，并可能拖慢 Gateway 测试分片。

第二类风险是 API 表面漂移。`startGatewayServer` 的签名当前直接从 `server.impl.js` 推导；如果改成手写类型，容易和真实实现不一致，影响脚本、测试和生产启动方。`GatewayServer`、`GatewayServerOptions` 的 re-export 也承担兼容入口作用，随意移动或删除会造成外部 import 断裂。

第三类风险是 trace 行为变化。`emitStartupTrace` 输出到 stderr，虽然受环境变量保护，但格式变化可能影响依赖启动诊断日志的工具；默认开启 trace 或输出更多内容也可能污染测试输出。

第四类风险是测试辅助泄漏。`resetModelCatalogCacheForTest` 应保持测试语义，如果把它扩展为生产清理逻辑，可能绕开 `server.impl.ts` 中更完整的生命周期管理。根据当前片段推断，模型目录缓存的真正所有权在实现层或其依赖模块中，门面层只应做委托。
