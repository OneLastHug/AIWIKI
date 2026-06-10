# 目录：packages/desktop/src/common/chat/approval

## 它负责什么

根据当前片段推断，`packages/desktop/src/common/chat/approval` 在本次可读工作树中并不存在，因此无法从实际源码确认它的职责、导出对象、类型定义或调用链。判断依据是：对目标相对路径与映射后的仓库路径进行目录检查时，目标目录没有命中；随后在 `packages/desktop/src` 范围内检索 `approval`、`Approval`、`approve`、`permission` 等相关关键词，也没有发现可用引用结果。

如果这个目录在预期分支中存在，从路径命名看，它很可能属于 `common/chat` 下的共享聊天审批模型层：也就是不直接处理 UI 渲染，也不直接执行主进程副作用，而是放置聊天审批相关的通用类型、状态枚举、数据结构、请求/响应协议或跨进程共享常量。这里的“审批”可能对应 AI 会话中的人工确认、敏感操作确认、工具调用授权、权限请求或用户决策结果。但这只是根据路径语义推断，不是当前源码证据。

因此，阅读这个目标时应先把它当作“缺失目录”处理：不要假设已有实现，也不要把审批能力误认为已经接入聊天主流程。若后续在其他分支、生成产物或未挂载源码中能看到该目录，再根据真实文件重新建立目录地图。

## 直接子目录地图

当前可读片段中，`packages/desktop/src/common/chat/approval` 没有实际目录，也没有直接子目录可列出。

按目标路径的层级关系，理论上的邻近区域应是：

- `packages/desktop/src/common`：跨进程或跨模块共享代码所在层，通常不应依赖 DOM、Electron 主进程专用能力或 renderer 组件。
- `packages/desktop/src/common/chat`：聊天领域的共享模型层或协议层，根据路径推断可能承载 chat message、session、agent/tool 调用等通用定义。
- `packages/desktop/src/common/chat/approval`：预期的审批子域，但当前片段未发现。

由于目标目录缺失，无法确认它下面是否采用 `types.ts`、`constants.ts`、`schema.ts`、`index.ts` 这样的扁平结构，也无法确认是否继续拆分为 `model`、`service`、`adapter`、`validator` 等子目录。

## 关键入口

当前没有可确认的关键入口文件。通常一个这类目录若存在，优先检查以下入口形态：

- `packages/desktop/src/common/chat/approval/index.ts`：最可能的聚合导出入口，用来暴露 approval 相关类型、枚举、辅助函数。
- `packages/desktop/src/common/chat/approval/types.ts`：最可能保存审批请求、审批结果、审批状态、审批来源等结构定义。
- `packages/desktop/src/common/chat/approval/constants.ts`：可能保存审批状态常量、默认超时、事件名或 IPC channel 名称。
- `packages/desktop/src/common/chat/approval/*.schema.ts` 或 `*.validator.ts`：如果项目使用结构化校验，这里可能定义审批 payload 的运行时校验规则。

但这些路径都属于阅读建议，不是当前工作树中已验证存在的文件。当前可以确认的是：没有发现可作为入口的 `index.ts` 或同级源文件，也没有发现从 renderer、process、preload 到该目录的导入引用。

## 主流程位置

当前片段无法定位真实主流程。根据路径语义，若该目录存在，它通常不会是完整业务流程的执行中心，而更可能处在主流程的“协议与状态定义”位置。

一个可能的审批主流程会是：聊天运行过程中产生需要用户确认的动作，例如工具调用、文件操作、命令执行或敏感能力访问；chat 领域代码构造 approval request；renderer 收到请求后展示确认 UI；用户选择 approve 或 deny；结果被写回会话执行链；执行层根据结果继续、跳过或中止后续步骤。若涉及 Electron 多进程，renderer 与 process 之间应通过 `packages/desktop/src/preload` 暴露的 IPC bridge 通信，而不是让 common 层直接调用 Node.js、DOM 或 Electron API。

在这个假设流程里，`packages/desktop/src/common/chat/approval` 的合理位置是定义双方都能理解的数据契约，例如 `ApprovalRequest`、`ApprovalResponse`、`ApprovalStatus`、`ApprovalAction`。真正的 UI 主流程应在 `packages/desktop/src/renderer`，真正的执行或持久化逻辑应在 `packages/desktop/src/process`，跨进程入口应在 `packages/desktop/src/preload`。不过当前检索未发现对应引用，所以只能标记为“根据当前片段推断”。

## 推荐阅读顺序

建议先确认目录是否应当存在。当前目标目录缺失时，不要从调用方倒推过多设计结论，优先检查分支、生成步骤、子模块或仓库同步状态是否正确。

如果后续拿到包含该目录的源码，推荐按以下顺序阅读：

1. 先看 `packages/desktop/src/common/chat/approval/index.ts`，确认它对外暴露的 API 边界。
2. 再看 `types.ts` 或相近类型文件，弄清楚审批对象的核心字段：请求 id、来源、动作类型、展示文案、风险等级、状态、结果、时间戳等。
3. 接着看 `constants.ts`、`schema.ts`、`validator.ts`，确认哪些状态和 payload 是稳定协议，哪些只是内部辅助。
4. 然后用 `rg` 查调用方，重点看 `packages/desktop/src/renderer` 中谁展示审批 UI，`packages/desktop/src/process` 中谁等待或消费审批结果，`packages/desktop/src/preload` 中是否有桥接通道。
5. 最后再看测试，确认 approve、deny、timeout、重复响应、会话取消等边界行为。

这个顺序能先建立共享契约，再进入执行链，避免一开始陷入 UI 或 IPC 细节。

## 常见误区

第一个误区是把 `common` 下的目录当成业务执行层。按照项目结构约束，`common` 更适合放共享类型、常量和纯函数；它不应该直接访问 DOM，也不应该直接调用 Node.js 或 Electron 主进程能力。审批如果涉及真实授权或副作用执行，通常应由 renderer、preload、process 分层协作完成。

第二个误区是看到 `approval` 就默认已有完整审批闭环。当前片段中目标目录不存在，也没有检索到相关引用，因此不能断言项目已经实现了聊天审批能力。最多只能说这个路径表达了一个可能的设计意图。

第三个误区是把用户确认 UI、权限策略、工具执行结果混在一个模块里。审批目录如果存在，最好只承载 chat approval 的领域契约；UI 文案应走 i18n，渲染组件应留在 renderer，真正执行动作的权限校验应留在 process 或专门服务中。

第四个误区是忽略跨进程边界。聊天审批往往横跨 renderer 和 process，但二者不能互相直接依赖内部 API；共享的数据结构可以放在 `common`，通信必须经过 preload 暴露的桥接层。

第五个误区是基于路径名补写不存在的架构事实。当前文档中凡是涉及职责和流程的部分，都应理解为“根据当前片段推断”；真正的结论需要等目标目录在源码中出现后，再以实际文件、导出和调用关系为准。
