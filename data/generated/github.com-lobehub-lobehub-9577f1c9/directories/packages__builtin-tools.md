# 目录：packages/builtin-tools

## 它负责什么

`packages/builtin-tools` 是 LobeHub 里“内置工具注册中心”的聚合目录。根据当前片段推断，它的核心职责不是实现具体工具逻辑，而是把分散在各个 `@lobechat/builtin-tool-*` 包里的能力，统一整理成前端和运行时都能消费的注册表。

这里主要做几件事：  
1. 汇总所有内置工具的 `manifest`、`identifier` 和能力映射。  
2. 按工具 ID 和 API 名提供统一查询入口，给 UI 渲染、工具调用展示、占位符、干预面板、流式状态等模块使用。  
3. 维护一些全局规则，比如默认工具、常驻工具、聊天模式允许的工具、运行时托管工具。  
4. 为少数特殊工具提供定制适配层，比如 `codex`、`github`、`linear`、`notebook`。

从 `package.json` 可以看出，这个包通过多个子路径导出给外部使用，属于典型的“公共索引层”。

## 直接子目录地图

这个目录的直接子目录不多，当前可见的只有四个：

- `src/codex/`：面向 Codex 工具的专用适配区，放的是 `file_change`、`todo_list` 这类专属 inspector/render 以及对应的展示控制。
- `src/github/`：GitHub 工具的专用适配区，主要围绕 `run_command` 这种命令执行类调用提供 inspector 和 render。
- `src/linear/`：Linear 工具的专用适配区，职责很薄，核心是把一组工具名统一映射到同一个 inspector。
- `src/notebook/`：Notebook 工具的专用渲染区，负责文档创建类工具的展示。

其余文件都在 `src/` 根层，属于注册表、常量、聚合入口和辅助映射，不再继续往下分层。也就是说，这个目录是“少量专用子目录 + 大量根层注册文件”的结构。

## 关键入口

最重要的入口是 `src/index.ts`。它把各类工具 manifest 聚合起来，输出几组关键常量：

- `defaultToolIds`
- `alwaysOnToolIds`
- `manualModeExcludeToolIds`
- `chatModeAllowedToolIds`
- `runtimeManagedToolIds`
- `builtinTools`

这几个数组和列表基本决定了“系统默认带哪些工具”“哪些工具用户不能关”“聊天模式下能看到哪些工具”“哪些工具由系统运行时决定”。

第二层入口是各类注册表文件：

- `src/inspectors.ts`
- `src/renders.ts`
- `src/placeholders.ts`
- `src/interventions.ts`
- `src/streamings.ts`
- `src/portals.ts`
- `src/displayControls.ts`
- `src/dynamicInterventionAudits.ts`
- `src/identifiers.ts`

其中 `inspectors`、`renders`、`placeholders`、`interventions`、`streamings` 负责把“工具 ID + API 名”映射到对应的 UI 组件；`displayControls.ts` 单独抽出，是为了避免渲染注册表引入循环依赖。

`package.json` 里的 `exports` 也很关键，它说明这个包不是只给单一入口用，而是按子路径对外暴露能力。

## 主流程位置

如果要理解这目录的主流程，建议按下面这条线看：

1. 先看 `src/index.ts`，理解工具总名单、默认集、常驻集、聊天模式白名单。  
2. 再看 `src/identifiers.ts`，理解“内置工具 ID 列表”是如何单独维护的。  
3. 然后看 `src/renders.ts`、`src/inspectors.ts`、`src/placeholders.ts`，理解同一个工具如何按 API 名挂接不同 UI。  
4. 接着看 `src/interventions.ts`、`src/streamings.ts`、`src/portals.ts`，补齐运行时展示链路。  
5. 最后看 `src/codex/`、`src/github/`、`src/linear/`、`src/notebook/` 这些特例目录，理解个别工具为什么需要单独适配。

从结构上说，这里的主流程就是“工具定义来源于各个兄弟包，`builtin-tools` 负责把它们编排成统一注册表，再由上层 UI/运行时按需查询”。

## 推荐阅读顺序

1. `packages/builtin-tools/package.json`  
2. `packages/builtin-tools/src/index.ts`  
3. `packages/builtin-tools/src/renders.ts`  
4. `packages/builtin-tools/src/inspectors.ts`  
5. `packages/builtin-tools/src/placeholders.ts`  
6. `packages/builtin-tools/src/interventions.ts`  
7. `packages/builtin-tools/src/streamings.ts`  
8. `packages/builtin-tools/src/displayControls.ts`  
9. `packages/builtin-tools/src/codex/index.ts`、`src/github/index.ts`、`src/linear/index.ts`、`src/notebook/index.ts`

这个顺序的好处是先抓住“总表”，再看“按类型分发”，最后看“个别特例”。

## 常见误区

- 容易把这里当成工具实现目录，但实际上它更像注册与编排层。真正的工具实现大多在 `@lobechat/builtin-tool-*` 的兄弟包里。
- 容易把 `builtinToolIdentifiers`、`defaultToolIds`、`builtinTools` 混为一谈。它们层级不同：一个是 ID 清单，一个是默认启用策略，一个是完整工具对象集合。
- 容易忽略 `displayControls.ts` 的存在。它不是普通 render 入口，而是为少数工具提供显示控制的轻量 fallback，目的是避开循环依赖。
- 容易把 `codex`、`github`、`linear`、`notebook` 看成普通业务子模块。实际上它们是专门处理少数工具的适配区，和主注册表是并列协作关系。
- 容易只看 `src/index.ts`，忽略 `package.json` 的 `exports`。对外暴露哪些能力，`exports` 才是准确边界。
