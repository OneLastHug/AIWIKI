# 文件：packages/coding-agent/src/core/export-html/index.ts
## 一句话定位
这是 coding-agent 的“会话导出为 HTML”核心模块，负责把 `SessionManager` 里的对话、工具调用、主题色和模板资源拼成一个可离线打开的 HTML 文件。根据当前片段推断，它同时服务两条入口：TUI 的 `/export` 能力和 CLI 的 `--export` 路径。

## 它暴露/定义了什么
对外主要暴露两个异步函数：`exportSessionToHtml(sm, state, options?)` 和 `exportFromFile(inputPath, options?)`。前者面向运行中的会话，能拿到 `AgentState`，所以可以把系统提示词、工具定义、当前主题和自定义工具渲染一起写进导出内容；后者面向单独的 `.jsonl` 会话文件，属于更轻量的离线导出。  
此外，这个文件还定义了 `ToolHtmlRenderer`、`ExportOptions`、内部 `SessionData` 和若干模板渲染辅助函数，构成完整的导出流水线。

## 谁调用它
能直接确认的调用方是 `packages/coding-agent/src/main.ts`：CLI 解析到 `parsed.export` 时，会调用 `exportFromFile(parsed.export, outputPath)`。  
从函数注释看，`exportSessionToHtml` 还会被 TUI 的 `/export` 命令使用；这部分在当前片段里没有展开到具体调用点，但注释已经明确它是交互模式的导出入口。

## 它调用谁
它依赖 `SessionManager` 读取会话头、消息、叶子节点和会话文件路径；依赖 `getExportTemplateDir()` 找到模板目录；依赖 `getResolvedThemeColors()` 和 `getThemeExportColors()` 获取主题变量；依赖 `normalizePath()`、`resolvePath()` 处理路径；依赖 `existsSync/readFileSync/writeFileSync` 读写文件；还会使用 `basename()`、`join()` 拼接模板文件名。  
如果提供了 `toolRenderer`，它还会回调 `ToolHtmlRenderer.renderCall()` 和 `renderResult()`，把非模板内置工具提前转成 HTML。

## 核心流程
导出流程可以概括成五步。第一步，规范化参数：把字符串形式的 `options` 转成 `ExportOptions`。第二步，校验输入来源：`exportSessionToHtml` 要求会话必须有落盘文件，`exportFromFile` 则先检查输入文件存在。第三步，组装 `SessionData`，把 header、entries、leafId、systemPrompt、tools 和可选的 `renderedTools` 放进去。第四步，调用 `generateHtml()`：读取 `template.html`、`template.css`、`template.js` 以及 `marked.min.js`、`highlight.min.js`，把主题变量和会话数据注入模板，输出完整 HTML。第五步，确定输出路径并写盘，最后返回实际生成的文件名。  
其中 `preRenderCustomTools()` 是一个关键分支，它只处理模板不内置支持的工具，避免导出页面里出现“原始 TUI 片段”和“预渲染 HTML”混杂的问题。

## 关键函数的高层作用
`parseColor()`、`getLuminance()`、`adjustBrightness()`、`deriveExportColors()` 负责把主题色转换成适合导出页面的背景色系，保证 HTML 主题不会和原始 TUI 脱节。  
`generateThemeVars()` 把主题色整理成 CSS 自定义变量，并补齐导出页专用的 `--exportPageBg`、`--exportCardBg`、`--exportInfoBg`。  
`generateHtml()` 是真正的拼装中心，负责把模板、CSS、JS、会话 JSON 一次性塞进最终页面。  
`preRenderCustomTools()` 则是工具渲染适配层，把自定义工具的 call/result 提前渲染好，交给模板直接显示。

## 修改风险
这个文件的修改风险主要集中在三类。第一类是模板耦合风险：`template.html/css/js` 的占位符一旦变动，导出页会直接失效。第二类是数据结构风险：`SessionData`、工具结果格式或 `AgentState` 结构变化，会让导出内容缺字段或渲染异常。第三类是视觉和兼容性风险：主题色推导、HTML 注入和自定义工具渲染都比较敏感，改错后常见问题不是编译失败，而是导出的页面打不开、样式错位，或者工具内容显示不完整。
