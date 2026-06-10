# 目录：src/acp

## 它负责什么

`src/acp` 是 OpenClaw 里 ACP（Agent Client Protocol）适配层的核心目录，负责把 OpenClaw 的网关、会话、命令、权限与运行时能力，映射成 ACP 客户端和服务端都能理解的协议行为。根据当前片段推断，这个目录既承担“对外协议壳”的职责，也承担“内部会话编排”的职责，位置上介于网关层 `src/gateway`、自动回复/命令体系 `src/auto-reply`，以及运行时插件注册体系之间。

从文件结构看，它不是单纯的工具集合，而是一套完整的 ACP 接入面：  
- `server.ts` 提供 ACP gateway 侧服务入口。  
- `client.ts` 提供本地 ACP 客户端入口。  
- `translator.ts` 负责把 ACP 请求、通知、权限、事件和 OpenClaw 内部数据互相转换。  
- `control-plane/` 负责会话与 turn 级别的编排。  
- `runtime/` 负责 ACP runtime backend 的注册、发现和约束。  
- 其他顶层文件则提供会话存储、命令表、事件账本、权限中继、文本规范化、秘密文件读取等支撑能力。

## 直接子目录地图

`src/acp` 下只有两个直接子目录，职责边界比较清楚：

- `src/acp/control-plane/`  
  这里放的是 ACP 的控制面逻辑，重点是 session manager、turn stream、runtime options、runtime cache、身份 reconcile、spawn 流程等。根据文件名和入口结构推断，这里更接近“ACP 会话如何运行、如何分配、如何恢复”的编排层。

- `src/acp/runtime/`  
  这里放 ACP runtime 抽象和 backend 注册机制，包括 runtime 类型、错误、可用性、session 标识、session meta、registry。它更像一个“运行时后端目录”，负责把可插拔 runtime 统一成 ACP 能消费的接口。

这两个子目录之外，`src/acp` 根部的大量 `.ts` 文件都在做协议适配和会话桥接，不再继续细分子目录。

## 关键入口

这个目录最值得先看的入口有四个：

1. `src/acp/server.ts`  
   这是 ACP 服务端入口，导出 `serveAcpGateway()`。它会解析网关 bootstrap，启动 gateway client，等待 hello 就绪，再通过 `AgentSideConnection` 和 `ndJsonStream` 挂上 ACP 连接。这个文件通常是“ACP 服务如何真正跑起来”的起点。

2. `src/acp/client.ts`  
   这是 ACP 客户端入口，导出 `runAcpClientInteractive()`。它会拉起 server 进程、建立 `ClientSideConnection`、初始化协议、创建 session，然后进入交互式 prompt 循环。它适合看“本地用户如何通过 ACP 驱动服务端”。

3. `src/acp/translator.ts`  
   这是最核心的协议翻译层，导出 `AcpGatewayAgent`。虽然当前只看到文件前半部分，但从导入结构和测试文件密度看，它负责 prompt 处理、会话映射、权限中继、事件映射、stop reason、session lineage、rate limit、生命周期等关键转换。

4. `src/acp/runtime/registry.ts`  
   这是 runtime backend 注册表。它提供 `registerAcpRuntimeBackend()`、`unregisterAcpRuntimeBackend()`、`getAcpRuntimeBackend()`、`requireAcpRuntimeBackend()`，决定 ACP runtime 后端如何被发现、选中和报错。

补充入口还有 `src/acp/control-plane/manager.ts` 和 `src/acp/session.ts`：前者是单例式 session manager 门面，后者是内存 session store 的默认实现。

## 主流程位置

主流程大致可以分成三段看。

第一段是“启动与连接建立”，核心在 `src/acp/server.ts`。它先解析运行配置、启动 gateway client、等待 gateway ready，然后建立 ACP 输入输出流，最后把 `AcpGatewayAgent` 绑到 `AgentSideConnection` 上。这里是 ACP 服务端生命线，决定它是否真正对外提供协议服务。

第二段是“客户端拉起与交互”，核心在 `src/acp/client.ts`。它会决定启动哪个 server 命令、是否剥离 provider auth 环境变量、如何初始化 ACP client capabilities，再创建 session 并进入交互循环。也就是说，这里是“ACP 客户端如何把用户输入送进协议”的主入口。

第三段是“协议翻译与会话编排”，核心在 `src/acp/translator.ts`、`src/acp/control-plane/manager.core.ts`、`src/acp/session.ts`、`src/acp/event-mapper.ts`、`src/acp/permission-relay.ts`。根据当前片段推断，这条链路大致负责：  
- 把 prompt/command 转成内部 run 请求。  
- 把 gateway 事件、tool call、权限审批转回 ACP notification。  
- 通过 session store 维持 session、runId、abort controller、idle 淘汰。  
- 通过 control-plane manager 处理 turn 流、身份 reconcile、runtime cache 和 spawn。  

`src/acp/commands.ts` 则像“能力目录”，决定 ACP 对外暴露哪些命令名；`src/acp/meta.ts`、`src/acp/policy.ts`、`src/acp/approval-classifier.ts` 这些则分别负责元数据读取、策略判断和审批分类。

## 推荐阅读顺序

1. 先看 `src/acp/types.ts`，确认 ACP 侧的选项、会话类型和 `ACP_AGENT_INFO`。  
2. 再看 `src/acp/server.ts`，把“服务端如何挂起来”先串起来。  
3. 接着看 `src/acp/client.ts`，理解本地交互端如何启动 server 并建立 session。  
4. 然后读 `src/acp/translator.ts`，这是协议语义转换的中心。  
5. 再看 `src/acp/session.ts` 和 `src/acp/control-plane/manager.ts`，理解会话与 turn 的生命周期。  
6. 最后补 `src/acp/runtime/registry.ts`、`src/acp/event-mapper.ts`、`src/acp/permission-relay.ts`、`src/acp/commands.ts`，把运行时、事件、权限、命令四条支线补齐。

如果只想快速建立目录地图，优先顺序可以压缩成：`server.ts` -> `client.ts` -> `translator.ts` -> `control-plane/manager.ts` -> `runtime/registry.ts`。

## 常见误区

1. 把 `src/acp` 当成单一“客户端实现”会看漏职责。它同时包含服务端、客户端、协议翻译、会话存储和 runtime 注册，不是只有一个入口。

2. 只看 `server.ts` 或 `client.ts` 会误判主流程。真正的业务语义大头在 `translator.ts` 和 `control-plane/`，前两者只是启动壳。

3. 把 `runtime/registry.ts` 误认为普通工具文件。它实际是 backend 发现与选择的门禁，影响 ACP runtime 的可用性和默认选择。

4. 忽略 `session.ts` 的会话存储语义。这里不只是缓存对象，还负责 active run、取消、淘汰和测试清理，直接影响并发和生命周期。

5. 看到大量 `*.test.ts` 就以为目录是测试驱动的杂乱集合。实际上测试密度高，说明这里的协议边界和生命周期复杂，许多行为是通过专门测试锁定的。

6. 如果只依据文件名下结论，容易过度细化某些职责。比如 `meta.ts`、`policy.ts`、`approval-classifier.ts` 各自边界需要结合调用链理解，当前只适合做地图式概览，不能把每个叶子都解释成独立子系统。
