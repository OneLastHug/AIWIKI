# 目录：packages/desktop/src/common/chat/navigation

## 它负责什么

这个目录是聊天系统里“导航类工具拦截”的公共工具层，核心职责是识别特定的导航工具调用，并把它们转换成预览面板可以消费的 `preview_open` 消息。换句话说，它不负责真正执行页面跳转，也不负责渲染预览界面，只负责在聊天上下文里把“要打开某个 URL”这件事标准化。

从当前代码看，它主要服务于 Chrome DevTools 相关的 MCP 工具场景：识别工具名、清洗工具前缀、提取 URL，再打包成统一的响应结构。整体是一个很薄的协议适配层，位置上属于 `common/chat`，说明它面向的是跨流程复用的公共逻辑，而不是某个单独页面。

## 直接子目录地图

这个目录下没有直接子目录，只有两个入口文件：

- `NavigationInterceptor.ts`：主体实现文件，包含常量、类型定义和 `NavigationInterceptor` 类。
- `index.ts`：对外导出入口，用于把该目录作为一个小型模块来引用。

因此，这个目录本身不是一个多层模块树，而是一个单点工具目录。根据当前片段推断，它的设计目标就是“一个目录、一组导航拦截能力”，避免把相关逻辑分散到多个位置。

## 关键入口

最重要的入口是 `NavigationInterceptor.ts` 里的 `NavigationInterceptor` 类，外部通常会通过 `index.ts` 进行导入。这个类暴露了几组关键静态能力：

- `normalizeToolName()`：清洗工具名，去掉 MCP 前缀、双下划线包装、尾部说明文本。
- `isChromeDevToolsIdentifier()`：判断字符串是否包含 Chrome DevTools 标识。
- `isNavigationTool()`：判断一个字符串或对象是否代表导航工具。
- `extractUrl()`：从多种输入格式里提取 URL。
- `createPreviewMessage()`：构造 `preview_open` 消息。
- `intercept()`：总入口，串联识别、提取、封装三个步骤。

目录级出口 `index.ts` 只做再导出，不包含业务判断。它的作用是让上层代码可以直接从 `navigation` 目录拿到这套能力，而不必关心具体实现文件名。

## 主流程位置

主流程集中在 `NavigationInterceptor.intercept()`。它的执行链路非常清楚：

1. 先调用 `isNavigationTool()` 判断输入是不是目标导航工具。
2. 如果不是，直接返回 `{ intercepted: false }`。
3. 如果是，再调用 `extractUrl()` 从 `url`、`arguments`、`rawInput`、`content`、`title` 等位置找 URL。
4. 如果没拿到 URL，也返回未拦截。
5. 如果拿到 URL，就调用 `createPreviewMessage()` 生成 `preview_open` 消息。
6. 最后返回 `{ intercepted: true, url, previewMessage }`。

这条链路说明该目录的核心价值不是“识别一个工具名”本身，而是把杂乱的 agent 输出统一收敛成可下发的预览事件。`NavigationToolData`、`PreviewOpenData`、`InterceptionResult` 这些类型也都是为这个流程服务的。

## 推荐阅读顺序

1. 先看 `index.ts`，确认这个目录对外暴露了什么。
2. 再看 `NavigationInterceptor.ts` 顶部的常量和类型，理解支持哪些工具名、哪些数据格式。
3. 然后直接读 `isNavigationTool()` 和 `extractUrl()`，这两段决定“能不能识别”和“能不能取到地址”。
4. 最后看 `intercept()` 和 `createPreviewMessage()`，把完整闭环串起来。

如果要继续向上追踪，建议再看 `packages/desktop/src/common/chat` 下其他目录的公共工具，以及真正消费 `preview_open` 消息的流程位置。根据当前片段推断，那个更上层流程才是实际把预览事件交给界面或会话系统的地方。

## 常见误区

- 误以为这是导航 UI 目录。实际上这里没有页面、组件或交互控件，只有工具逻辑。
- 误以为它负责真正打开网页。它只负责拦截和封装消息，执行动作在别处。
- 误以为只支持一种输入格式。实际上它兼容字符串和对象，还尝试从 `arguments`、`rawInput`、`content`、`title` 多处抽取 URL。
- 误以为它适用于所有工具。当前实现只认 `navigate_page`、`new_page`，并且还要求带有 Chrome DevTools 相关标识。
- 误以为这里有很多子模块。就当前仓库片段看，这个目录很小，核心逻辑基本都压在一个实现文件里。
