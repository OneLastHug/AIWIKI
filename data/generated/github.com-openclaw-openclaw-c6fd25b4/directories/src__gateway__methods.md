# 子系统：src/gateway/methods

## 解决什么问题

`src/gateway/methods` 负责把 Gateway 可调用的 RPC method 从“散落在 server、plugin、channel、node sidecar 里的处理函数”整理成一个统一的可查询注册表。它不直接实现 `health`、`sessions.send`、`config.apply` 等业务逻辑，而是定义这些 method 的元数据契约：名字、权限作用域、所有者、启动期可用性、是否属于控制面写操作、是否对客户端广告等。

这个目录的核心价值是把“能不能调用某个 method”与“method 实际做什么”分离。Gateway 的 HTTP/WS 请求分发只需要问注册表：这个名字有没有 handler、需要什么 `OperatorScope`、是否在 sidecars 未就绪时不可用、是否要出现在 method 列表中。这样权限、发现、启动状态和插件扩展不会散落在每个 handler 周围。

## 相关目录和文件

`src/gateway/methods/descriptor.ts` 定义公共类型，包括 `GatewayMethodDescriptor`、`GatewayMethodScope`、`GatewayMethodOwner` 和只读视图 `GatewayMethodRegistryView`。这是这个子系统的类型边界。

`src/gateway/methods/core-descriptors.ts` 维护 core method 的分类表 `CORE_GATEWAY_METHOD_SPECS`，例如 `config.*`、`sessions.*`、`node.*`、`plugins.*`、`talk.*`、`tools.*` 等。它把 core handler 名称映射到权限 scope 和附加标记。

`src/gateway/methods/registry.ts` 负责构造注册表，提供 `createGatewayMethodRegistry`、`createCoreGatewayMethodDescriptors`、`createGatewayMethodDescriptorsFromHandlers`、`createPluginGatewayMethodDescriptor`、`createPluginGatewayMethodDescriptors` 等入口。

`src/gateway/methods/registry.test.ts` 验证注册表行为，尤其是重复 method、广告列表、plugin descriptor 生成、scope 与 owner 元数据等。

邻近调用方主要在 `src/gateway/server.impl.ts`、`src/gateway/server-methods.ts`、`src/gateway/server/ws-connection/message-handler.ts`、`src/gateway/method-scopes.ts`、`src/gateway/server-methods-list.ts`。插件侧入口与 `src/plugins/registry.ts`、`src/plugins/registry-types.ts`、`src/channels/plugins/types.plugin.ts` 有关。

## 核心对象

`GatewayMethodDescriptor` 是最重要的数据结构。它至少包含 `name`、`handler`、`scope`、`owner`。其中 `scope` 可以是 `OperatorScope`，也可以是特殊 scope：`node` 或 `dynamic`。`node` 表示 node/sidecar 内部通信面，`dynamic` 表示权限不能只靠静态表判断，典型场景是插件会话动作这类依赖运行时上下文的 method。

`GatewayMethodOwner` 用来标记 method 归属：`core`、`plugin`、`channel`、`aux`。这让 Gateway 能区分 core 内建方法、插件贡献方法、channel 贡献方法和临时/辅助 handler。根据当前片段推断，owner 的主要用途是调试、审计、列表展示和避免把 plugin-owned 行为误塞进 core 策略；依据是 root 规则强调 core 保持 plugin-agnostic，而 registry 明确把 owner 编进 descriptor。

`GatewayMethodRegistryView` 是注册表对外暴露的最小查询接口：`getHandler`、`listMethods`、`listAdvertisedMethods`、`getScope`、`isStartupUnavailable`、`isControlPlaneWrite`、`descriptors`。调用方不需要知道内部如何存储，只通过这些方法做分发、权限判断和能力展示。

`CORE_GATEWAY_METHOD_SPECS` 是 core method 的静态分类源。它不是业务 handler 表，而是“这些 core method 应该怎样被 Gateway 看待”的规范表。新增 core RPC 时，如果只加 handler 而不加这里的分类，就会导致权限、广告或启动期行为缺失。

## 运行流程

Gateway 启动或请求处理准备阶段会先收集 core handler。`src/gateway/server.impl.ts` 和 `src/gateway/server-methods.ts` 会调用 `createCoreGatewayMethodDescriptors(coreDescriptorHandlers)`，把实际 handler 与 `CORE_GATEWAY_METHOD_SPECS` 中的权限、启动标记、控制面写标记合成 descriptor。

随后 Gateway 会从当前 active plugin registry 读取 `gatewayMethodDescriptors`，通过 `createPluginGatewayMethodDescriptors` 转换成同一套 descriptor。插件注册通常来自 `src/plugins/registry.ts`，而插件公开的 descriptor 类型又连接到 `src/channels/plugins/types.plugin.ts` 和 SDK 暴露面。

如果还有测试或嵌入式场景传入的额外 handler，会通过 `createGatewayMethodDescriptorsFromHandlers` 包装为辅助 descriptor。最后 `createGatewayMethodRegistry([...])` 把 core、plugin、aux descriptor 合并成注册表。

请求到来后，Gateway 分发层通过 method name 查 `getHandler`。权限层或连接层通过 `getScope`、`isStartupUnavailable`、`isControlPlaneWrite` 决定是否允许调用、是否需要等待 sidecars、是否属于敏感控制面写操作。客户端能力发现则使用 `listAdvertisedMethods`，这会排除 `advertise: false` 的内部或兼容 method，例如片段中可见的 `assistant.media.get`、`sessions.get`、`poll`、`connect` 等。

## 上下游依赖

上游输入包括三类：core server method handler、active plugin registry、额外注入 handler。core handler 来自 Gateway server 方法实现；plugin descriptors 来自插件加载和注册系统；extra handlers 多用于测试、嵌入或特殊运行环境。

下游消费方包括 HTTP/WS RPC 分发、WebSocket message handler、method scope 校验、method list 广告、server runtime 注入。`src/gateway/server-ws-runtime.ts` 和 `src/gateway/server/ws-connection.ts` 接受 `getMethodRegistry`，说明运行中的连接可能拿到最新注册表视图，而不是复制一份过期列表。

它还依赖 `src/gateway/operator-scopes.ts` 的权限模型。`operator.read`、`operator.write`、`operator.admin`、`operator.approvals`、`operator.pairing` 等 scope 决定调用者能力边界。对于 plugin method，依赖插件注册契约而不是 Gateway 私自加载插件内部实现，这符合 `src/gateway/AGENTS.md` 关于热路径避免物化完整 bundled plugin runtime 的约束。

## 修改时最容易踩的坑

新增 core method 时，不能只在 `src/gateway/server-methods.ts` 或某个 handler 文件里加函数，还要在 `CORE_GATEWAY_METHOD_SPECS` 中补齐 scope、`startup`、`controlPlaneWrite`、`advertise` 等分类。分类错误比编译错误更危险，因为它可能表现为权限过宽、启动期误暴露或客户端发现列表异常。

不要把插件专属策略硬编码进 core method 表。plugin-owned Gateway 行为应该通过插件 descriptor 或轻量 public artifact resolver 暴露，避免 Gateway 热路径为了静态问题加载完整插件运行时。

`advertise: false` 不等于不可调用。它只是不出现在广告列表，真实访问仍由 handler 存在性和 scope 决定。内部兼容 method、旧客户端入口、测试入口都可能选择隐藏但保留。

`startup: true` 在源码中表示转换成 `unavailable-until-sidecars` 这类启动期可用性标记时要特别小心。根据当前片段推断，`models.list`、`tools.effective`、`sessions.create` 等在 sidecars 未就绪时可能不能正常服务；依据是它们在 core spec 中带有 `startup: true`，而 descriptor 类型有 `GatewayMethodStartupAvailability`。

重复 method name 是高风险冲突。core、plugin、aux 最终进入同一个 registry，任何重复都可能覆盖或触发错误。新增 plugin method 前应先查 `CORE_GATEWAY_METHOD_SPECS` 和现有插件 descriptor，避免抢占 core 名称。

## 推荐阅读顺序

先读 `src/gateway/methods/descriptor.ts`，掌握 descriptor、scope、owner 和 registry view 的边界。

再读 `src/gateway/methods/core-descriptors.ts`，重点看 `CORE_GATEWAY_METHOD_SPECS` 如何把大量 Gateway RPC 分组到权限和启动行为上，不需要逐项背诵。

然后读 `src/gateway/methods/registry.ts`，理解 core、plugin、aux descriptor 如何归一化并合并成注册表。

接着读 `src/gateway/server-methods.ts` 和 `src/gateway/server.impl.ts`，观察注册表在请求路径和 attached Gateway server 中如何创建、刷新和传入。

最后读 `src/gateway/method-scopes.ts`、`src/gateway/server/ws-connection/message-handler.ts`、`src/gateway/server-methods-list.ts`，把权限校验、WS 调用分发和 method 广告列表串起来。测试可放在最后看 `src/gateway/methods/registry.test.ts`，用于确认你对重复、广告、plugin descriptor 和 scope 查询的理解是否正确。
