# 文件：src/gateway/methods/registry.ts

## 一句话定位

`src/gateway/methods/registry.ts` 是 Gateway RPC 方法表的构建器：把 core、plugin、aux 等来源的方法描述符统一规范化、去重、索引，并向请求分发、方法列表、权限与启动状态判断提供只读视图。

## 它暴露/定义了什么

它导出 `GatewayMethodRegistry` 类型别名，实际等同于 `GatewayMethodRegistryView`；同时转导 `createCoreGatewayMethodDescriptors`、`isCoreGatewayMethodClassified`，方便 Gateway 组装层从同一模块拿到 core 方法描述能力。

核心导出函数包括：

`createGatewayMethodRegistry`：把一组 `GatewayMethodDescriptorInput` 变成可查询的 registry。

`createGatewayMethodDescriptorsFromHandlers`：把普通 `Record<string, GatewayMethodHandler>` 转成带 owner 和 scope 的描述符列表。

`createPluginGatewayMethodDescriptor`：为单个 plugin 方法创建描述符，并应用 plugin 方法 scope 规则。

`createPluginGatewayMethodDescriptors`：从 `PluginRegistry` 中提取 plugin Gateway 方法描述符；如果旧式 registry 只有 `gatewayHandlers`，则生成默认 `operator.admin` scope 的兼容描述符。

## 谁调用它

主要调用点在 Gateway 服务装配和请求处理路径。

`src/gateway/server-methods.ts` 的 `createRequestGatewayMethodRegistry` 会在处理请求时把 `coreGatewayHandlers`、当前 active plugin registry 的方法、以及 `extraHandlers` 合并成 registry，然后 `handleGatewayRequest` 通过 `getHandler` 找处理函数，通过 `isControlPlaneWrite` 做控制面写限流。

`src/gateway/server.impl.ts` 在 WebSocket Gateway 启动/插件运行时替换时构建 `attachedGatewayMethodRegistry`，并用 `listAdvertisedMethods` 填充对外可见方法列表。

测试侧 `src/gateway/methods/registry.test.ts`、`src/gateway/method-scopes.test.ts` 验证去重、scope 规范化、plugin 方法默认 admin、保留命名空间强制 admin 等行为。

## 它调用谁

它依赖 `src/gateway/methods/descriptor.ts` 中的描述符类型、`NODE_GATEWAY_METHOD_SCOPE`、`DYNAMIC_GATEWAY_METHOD_SCOPE` 常量；依赖 `src/gateway/operator-scopes.ts` 的 `ADMIN_SCOPE` 和 `OperatorScope`；依赖 `src/shared/gateway-method-policy.ts` 的 `normalizePluginGatewayMethodScope`，用于保证 plugin 不能把保留管理命名空间降权。它还接收 `src/plugins/registry-types.ts` 的 `PluginRegistry` 形状，读取其中的 `gatewayHandlers` 和 `gatewayMethodDescriptors`。

## 核心流程

入口通常先准备多来源描述符：core 由 `createCoreGatewayMethodDescriptors` 生成，plugin 由 `createPluginGatewayMethodDescriptors` 提供，未分类的额外 handler 由 `createGatewayMethodDescriptorsFromHandlers` 包装。随后 `createGatewayMethodRegistry` 对所有描述符执行 `normalizeDescriptor`。

规范化阶段会 trim 方法名，拒绝空名称；如果 scope 是特殊的 `"node"` 或 `"dynamic"`，直接保留；如果 owner 是 plugin，则通过 `normalizePluginGatewayMethodScope` 二次校正 scope；其他 owner 的 scope 原样保留。之后 registry 用 `Map` 建立 name 到 descriptor 的索引，重复 name 会直接抛错，避免运行时分发出现来源不确定。

最终返回的是一个闭包式只读对象：按名称查 handler/scope/启动可用性/控制面写标记，或列出全部方法、可广告方法、完整 descriptors。

## 关键函数的高层作用

`createGatewayMethodRegistry` 是本文件的中心。它定义了 Gateway 方法命名唯一性、描述符规范化、对外查询接口，是请求分发和方法公告之间的共同事实来源。

`normalizeDescriptor` 是关键的策略收口点。它不是简单复制输入，而是把 plugin 方法的 scope 约束集中到 registry 构建阶段，尤其防止 `config.`、`wizard.`、`update.`、`exec.approvals.` 等保留管理命名空间被 plugin 注册成低权限方法。根据当前片段推断，这一设计是为了让权限判断、方法列表和 handler 分发共享同一个规范化结果，依据是 `server-methods.ts` 与 `method-scopes.ts` 都会读取 active plugin 描述符或 registry 元数据。

`createGatewayMethodDescriptorsFromHandlers` 是适配器，把旧式 handler map 或 aux handlers 转成标准描述符；它要求调用者提供默认 scope 或逐方法 scope，缺失就抛错。

`createPluginGatewayMethodDescriptor` 是 plugin 单方法注册的便捷入口，默认 scope 为 `ADMIN_SCOPE`，并复用保留命名空间策略。

`createPluginGatewayMethodDescriptors` 兼容两类 plugin registry：优先使用显式 `gatewayMethodDescriptors`；没有时从 `gatewayHandlers` 退化生成 admin-only 描述符。

## 修改风险

最大风险是权限边界。改动 `normalizeDescriptor`、`createPluginGatewayMethodDescriptor` 或默认 scope，可能让 plugin 方法被错误降权，影响 operator scope 授权、CLI 最小权限推导和 WebSocket 请求放行。

第二类风险是方法冲突处理。当前重复方法名直接失败，保证 core、plugin、aux handler 不会静默覆盖；如果改成后写覆盖，会改变 `server-methods.ts` 中 extraHandlers 与 pluginHandlers 的优先级语义。

第三类风险是方法可见性和启动期行为。`advertise: false`、`startup: "unavailable-until-sidecars"`、`controlPlaneWrite` 分别影响方法列表、启动期不可用响应和控制面写限流，字段规范化如果丢失会造成客户端看到错误能力或绕过限流。

第四类风险是向后兼容。`createPluginGatewayMethodDescriptors` 仍支持只有 `gatewayHandlers` 的旧式 plugin registry，并默认 admin；删除这条路径会影响未迁移插件或测试夹具。

修改时应同步检查 `src/gateway/methods/registry.test.ts`、`src/gateway/method-scopes.test.ts`、`src/gateway/server-methods.ts`、`src/gateway/server.impl.ts`，并特别验证保留命名空间、plugin 方法 scope、重复注册、方法公告和控制面写限流。
