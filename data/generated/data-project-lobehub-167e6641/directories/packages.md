# `packages` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/packages`
- 它是 pnpm workspace 的共享包目录

## 它负责什么

`packages` 负责把“主工程和桌面端都会反复用到的能力”抽成内部包。

所以它不是第三方依赖缓存，也不是随手堆工具脚本的地方。

它真正解决的是：

- 类型和常量怎么共享
- 数据库和模型运行时怎么复用
- Agent / Tool 生态怎么模块化
- Electron 桥接协议怎么抽离

## 初学者应该先看哪些文件和包

推荐顺序：

1. `packages/types`
   先看共享类型，不容易迷路。
2. `packages/const`
   看全局常量和运行环境判断。
3. `packages/config`
   看默认配置怎样被聚合。
4. `packages/database`
   看数据库能力为什么独立成包。
5. `packages/model-runtime`
   看模型 Provider 运行时为什么不直接写在 `src/server`。
6. `packages/agent-runtime`
   看 Agent 执行为什么独立成可复用运行时。
7. `packages/builtin-tools`
   看内置工具如何被聚合。
8. `packages/desktop-bridge`
9. `packages/electron-client-ipc`
10. `packages/electron-server-ipc`

## 这个目录里的重要包分组

## 1. 基础共享层

这些包最适合当作“字典”和“基础规则”来看：

| 包名 | 作用 |
| --- | --- |
| `@lobechat/types` | 共享类型定义 |
| `@lobechat/utils` | 通用工具函数 |
| `@lobechat/const` | 常量、URL、运行环境标记、默认值 |
| `@lobechat/config` | 把若干默认配置装配成默认设置对象 |

一个很典型的例子是：

- `packages/config/src/index.ts` 输出 `DEFAULT_SETTINGS`
- 这个默认设置并不是凭空写死，而是组合了 `@lobechat/const` 与 `@lobechat/business-config`

## 2. 数据与持久化层

最重要的是：

- `@lobechat/database`

它独立成包后，前后端和测试可以共享：

- 数据库适配器
- schema
- repository
- 类型

这比把数据库逻辑散在 `src/server` 各处更容易维护。

## 3. 模型与 Agent 运行时层

这里是 AI 平台最重的一组共享包：

| 包名 | 大致作用 |
| --- | --- |
| `@lobechat/model-runtime` | 各模型 Provider 的统一运行时封装 |
| `@lobechat/agent-runtime` | Agent 运行时核心能力 |
| `@lobechat/agent-manager-runtime` | Agent 管理相关运行时 |
| `@lobechat/context-engine` | 工具、上下文、能力组装相关机制 |

从 `model-runtime/src/index.ts` 能直接看出，它统一导出了大量 Provider 运行时类。

这说明项目不是把 OpenAI、Anthropic、Ollama 等逻辑零散塞进业务代码，而是尽量抽到独立层。

## 4. 工具与技能生态层

这组包数量很多，但可以先按“总控包 + 细分包”理解。

### 总控包

- `@lobechat/builtin-tools`
- `@lobechat/builtin-agents`
- `@lobechat/builtin-skills`

### 细分包

- `@lobechat/builtin-tool-agent-builder`
- `@lobechat/builtin-tool-memory`
- `@lobechat/builtin-tool-web-browsing`
- `@lobechat/builtin-tool-task`
- 以及大量 `builtin-tool-*`

对初学者来说，最重要的观察不是每个工具具体干嘛，而是：

- `builtin-tools` 负责聚合
- `builtin-tool-*` 负责各自的 manifest 和实现

`packages/builtin-tools/src/index.ts` 里能直接看到：

- `defaultToolIds`
- `alwaysOnToolIds`
- `chatModeAllowedToolIds`
- `runtimeManagedToolIds`
- `builtinTools`

也就是说，它像一个“内置工具总表”。

## 5. 桌面桥接层

这些包帮助桌面端和共享前端代码说同一种语言：

| 包名 | 作用 |
| --- | --- |
| `@lobechat/desktop-bridge` | 共享桌面常量、路由变体、头信息约定 |
| `@lobechat/electron-client-ipc` | 渲染进程侧 IPC 类型和辅助工具 |
| `@lobechat/electron-server-ipc` | 主进程侧 IPC 服务与类型 |
| `@lobechat/file-loaders` | 文件解析和读取能力 |

如果你要理解桌面端，不读这组包会很难真正看懂 `apps/desktop` 和 `src/services/electron`。

## 6. `packages/business/*` 怎么理解

这里有：

- `packages/business/config`
- `packages/business/const`
- `packages/business/model-runtime`

从当前代码能直接看出：

- `business-config` 会参与默认设置装配
- `business-const` 暴露品牌、默认模型等业务常量
- `ENABLE_BUSINESS_FEATURES` 当前为 `false`

因此可以比较稳地理解为：

- 这是主工程之外的一层业务扩展能力

如果进一步把它理解成商业版扩展，需要标记为“推测”，因为当前这批文件只能证明它是扩展层，不能单独证明全部产品边界。

## 它和其他目录如何交互

最典型的交互方式是：

```text
src/*
-> import '@lobechat/...'
-> 使用共享类型 / 常量 / 运行时 / 桥接能力

apps/desktop/*
-> import '@lobechat/...'
-> 使用共享桌面桥接、IPC、文件能力
```

也就是说，`packages` 是整个仓库的“基础设施供应层”。

## 常见概念解释

### `workspace:*`

表示这个依赖来自当前 monorepo，而不是外部 npm 仓库。

### `exports`

每个包通过 `package.json` 的 `exports` 暴露公共入口。

这会强迫大家通过稳定入口使用包，而不是到处深路径 import。

### `peerDependencies`

表示这个包希望宿主项目提供某些依赖，例如 React、zod、drizzle。

### “barrel export”

很多包的 `src/index.ts` 本身不做复杂逻辑，而是统一 re-export。

这很常见，不代表文件没用；它的价值在于给全项目提供稳定 import 入口。

## 需要暂时跳过的内容

初学阶段建议先跳过：

- 每一个 `builtin-tool-*` 的具体实现
- `chat-adapter-*` 一系列平台适配包
- `eval-*` 评测细分包
- `openapi`、`observability-otel` 之类偏专项基础设施

先抓共享层分组和代表包，比逐个扫包更有效率。

## 一句话阅读建议

读 `packages` 时，不要数包名，要先按“基础层 / 数据层 / 运行时层 / 工具层 / 桌面桥接层”分组。
