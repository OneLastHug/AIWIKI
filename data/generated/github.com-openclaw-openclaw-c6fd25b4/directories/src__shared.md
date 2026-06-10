# 目录：src/shared

## 它负责什么

`src/shared` 是仓库里最典型的“公共基础层”目录，放的是跨模块复用的纯函数、类型和少量小型状态工具。根据当前片段推断，它不承担单一业务流程，而是给 `src/` 下的 CLI、gateway、agents、secrets、plugin-sdk 等多条主线提供通用能力。这里的代码大多很小、很纯，目标是把“字符串怎么规范化、URL 怎么脱敏、节点怎么解析、文本怎么裁剪、运行时怎么按需导入”这些横切逻辑收拢到一个地方。

从引用情况看，`src/shared` 不是封闭内核，而是被大量上层模块直接调用；同时它也会被 `src/plugin-sdk/*` 进一步重新导出，说明它既是核心内部工具层，也是外部插件能力的底座之一。

## 直接子目录地图

`src/shared` 下面只有两个直接子目录：

- `src/shared/net`：网络与 URL 相关的通用处理，重点是 IP、IPv4、userinfo、敏感 URL 脱敏、以及与网络安全相关的字符串判断。
- `src/shared/text`：面向文本处理的公共能力，重点是 markdown 清理、assistant 可见文本、代码区域识别、reasoning/tool-call 相关标记，以及文本片段拼接与过滤。

目录根部的其余文件可以按职责粗分为几组：字符串与类型规范化、配置与元数据、节点解析、运行时导入、状态/生命周期、用量与会话类型等。这里不适合逐文件背诵，更重要的是把它看成“跨域工具仓”。

## 关键入口

这个目录没有明显的单一 barrel 入口文件，消费者通常是按需直引具体模块。最常见、也最能代表目录角色的入口有几类：

- 字符串规范化入口：`src/shared/string-coerce.ts`、`src/shared/string-normalization.ts`。前者提供 `normalizeOptionalString`、`normalizeStringifiedOptionalString`、`hasNonEmptyString` 一类基础归一化，后者补充大小写、slug 之类的规范处理。
- 文本入口：`src/shared/text/strip-markdown.ts`、`src/shared/text/code-regions.ts`、`src/shared/text/join-segments.ts`。这些通常出现在 TTS、assistant 观测文本、消息格式化路径上。
- 网络安全入口：`src/shared/net/redact-sensitive-url.ts`、`src/shared/net/ip.ts`、`src/shared/net/ipv4.ts`、`src/shared/net/url-userinfo.ts`。它们服务于 gateway、secrets、配置显示和日志脱敏。
- 节点解析入口：`src/shared/node-resolve.ts`、`src/shared/node-match.ts`、`src/shared/node-list-parse.ts`。这组通常被 CLI 和节点管理逻辑调用。
- 动态导入入口：`src/shared/runtime-import.ts`，负责把运行时模块拼成安全 import specifier 并执行动态加载。
- 入口元数据入口：`src/shared/entry-metadata.ts`、`src/shared/requirements.ts`、`src/shared/entry-status.ts`，偏向“功能可用性判定”和展示状态。

另外，`src/plugin-sdk/text-runtime.ts`、`src/plugin-sdk/core.ts`、`src/plugin-sdk/gateway-runtime.ts` 等文件也会把这里的能力再向外暴露，说明它们是对外能力的真实入口之一。

## 主流程位置

严格说 `src/shared` 不是一个“流程编排目录”，但它处在几条主流程的上游：

1. 文本处理链路  
   典型路径是上层消息/assistant 输出先经过 `string-coerce`、`text/strip-markdown`、`text/code-regions`、`text/join-segments` 之类工具，再进入 TTS、展示或插件 runtime。根据当前片段推断，这条链路是 `src/shared/text` 的主要用途。

2. 网关与安全链路  
   `net/redact-sensitive-url.ts`、`net/ip.ts`、`net/ipv4.ts` 这类模块会被 gateway、secret 扫描、URL 处理和调试输出反复使用。它们的位置很靠下，但对日志安全和外部暴露面影响很大。

3. 节点与列表解析链路  
   `node-list-parse.ts`、`node-resolve.ts`、`node-match.ts` 是节点选择、查询、解析的基础件，常见于 CLI、配对、状态查询等路径。这里的逻辑往往决定“用户输入如何映射到真实节点”。

4. 配置/元数据判定链路  
   `config-eval.ts`、`entry-metadata.ts`、`requirements.ts`、`entry-status.ts` 负责把元数据、前置条件、平台约束和展示信息组合起来，通常用于“某个入口能不能跑、缺什么、怎么显示”的判断。

5. 运行时加载链路  
   `runtime-import.ts` 把“拼 specifier”和“执行 import”收在一起，避免上层到处手写动态导入拼接逻辑。

## 推荐阅读顺序

如果只是想建立地图，建议按这个顺序看：

1. `src/shared/string-coerce.ts`：先看最底层的字符串规范化习惯。
2. `src/shared/net/redact-sensitive-url.ts`：理解安全脱敏和敏感参数判断。
3. `src/shared/text/strip-markdown.ts`：看文本处理风格，再扩展到 `src/shared/text/` 其余文件。
4. `src/shared/node-resolve.ts`：了解节点查询与选择的入口形式。
5. `src/shared/runtime-import.ts`：理解运行时导入是怎么被约束的。
6. `src/shared/entry-metadata.ts` 与 `src/shared/requirements.ts`：最后看元数据与可用性判定。

如果你关心对外插件能力，再顺着 `src/plugin-sdk/text-runtime.ts`、`src/plugin-sdk/core.ts` 回看这些共享模块的导出面。

## 常见误区

- 把 `src/shared` 当成“一个单独业务模块”。它更像公共工具仓，主题分散，但都服务于上层主线。
- 只盯根目录文件，忽略 `src/shared/net` 和 `src/shared/text`。这两个子目录才是最清晰的分区。
- 以为这里有统一入口。当前片段看不出一个总 `index.ts`，多数消费是按文件直引，或者经 `src/plugin-sdk/*` 转出。
- 低估这些工具的影响面。像 `string-coerce`、`redact-sensitive-url`、`runtime-import` 这种文件虽然短，但经常处在高频路径上，改动会外溢到 CLI、gateway、plugin SDK 和消息处理链路。
- 只把它理解成“辅助代码”。实际上它承载了很多跨层契约：输入归一化、URL 安全、文本可读化、节点解析和动态加载边界，都是主流程的一部分。
