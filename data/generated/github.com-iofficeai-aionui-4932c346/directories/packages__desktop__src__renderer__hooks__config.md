# 子系统：packages/desktop/src/renderer/hooks/config

## 解决什么问题
这个目录目前只有一个通用 Hook：`useConfig.ts`。它的职责不是做业务配置页，而是给 renderer 层提供一个“按 key 读取、订阅、写回配置”的统一入口。  
根据当前片段推断，它解决的是配置状态在 React 组件里的同步问题：组件不需要自己去订阅事件、读缓存、再手动刷新，只要传入配置 key，就能拿到当前值和一个写回函数。

## 相关目录和文件
核心实现只有 `packages/desktop/src/renderer/hooks/config/useConfig.ts`。  
它直接依赖 `packages/desktop/src/common/config/configService.ts` 和 `packages/desktop/src/common/config/configKeys.ts`。前者负责缓存、订阅和持久化，后者定义了所有合法配置 key 及其类型映射。  
在上层，`packages/desktop/src/renderer/main.tsx` 会在应用初始化阶段先准备 configService；在业务侧，像 `packages/desktop/src/renderer/hooks/system/useAutoPreviewOfficeFilesEnabled.ts` 这样的 hook 会直接复用 `useConfig('system.autoPreviewOfficeFiles')` 这一模式。

## 核心对象
`useConfig<K extends ConfigKey>(key)` 是这里唯一的公开能力。它返回一个二元组：`[value, setValue]`。  
`value` 的类型由 `ConfigKeyMap[K]` 自动推导，`setValue` 是异步写回函数。  
底层真正干活的是 `configService`：它维护内存 cache、订阅者集合，并把变更同步到后端接口 `/api/settings/client`。`ConfigKey` 和 `ConfigKeyMap` 则把字符串型 key 和具体值类型绑定起来，避免 renderer 侧到处散落 `any` 或手写断言。

## 运行流程
1. 组件调用 `useConfig(key)`。  
2. Hook 内部用 `useSyncExternalStore` 订阅 `configService.subscribe(key, ...)`。  
3. 读取快照时调用 `configService.get(key)`，直接从内存 cache 取当前值。  
4. 当 `setValue(newValue)` 被调用时，实际执行的是 `configService.set(key, newValue)`。  
5. `configService.set` 会先更新 cache，再通知同 key 的订阅者，最后通过 `PUT /api/settings/client` 持久化到后端。  
6. 其他使用同一 key 的组件会因为订阅通知而重新渲染，保持页面一致。

## 上下游依赖
上游依赖主要是 React 的 `useSyncExternalStore` 和项目内部的 `configService`。  
下游消费方是所有需要读写配置的 renderer 组件和 hook，例如系统设置、工具设置、主题、窗口状态、语音输入、模型相关设置等。  
从 `configService.ts` 可以看出，它还兼容 WebUI browser mode 和桌面模式：会根据运行环境拼出不同的 base URL，这说明这个目录虽然在 renderer 下，但配置来源并不局限于本地 React 状态，而是跨进程/跨部署形态共享的一套配置通道。

## 修改时最容易踩的坑
最常见的问题是绕开 `ConfigKeyMap` 新增字符串 key，导致类型推导失效，后续调用方拿不到正确的值类型。  
第二个坑是误以为 `useConfig` 自己负责初始化；实际上它只读现成 cache，初始化时序仍由 `configService.initialize()` 决定。  
第三个坑是改了某个配置的存储结构，却没有同步更新 `configKeys.ts`、后端 `/api/settings/client` 的数据格式，以及相关消费 hook，最后会出现“能写不能读”或“读到旧结构”的问题。  
如果新增的是会影响首屏或全局行为的配置，还要注意它是否需要在 `main.tsx` 的初始化阶段就可用。

## 推荐阅读顺序
1. `packages/desktop/src/renderer/hooks/config/useConfig.ts`  
2. `packages/desktop/src/common/config/configKeys.ts`  
3. `packages/desktop/src/common/config/configService.ts`  
4. `packages/desktop/src/renderer/main.tsx`  
5. `packages/desktop/src/renderer/hooks/system/useAutoPreviewOfficeFilesEnabled.ts`
