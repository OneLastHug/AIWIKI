# 文件：src/replLauncher.tsx

## 一句话定位
`src/replLauncher.tsx` 是 REPL 交互界面的统一启动壳，负责把应用外层容器、错误边界和 `REPL` 屏幕按固定顺序装配起来，再交给渲染器执行。它本身不承载业务逻辑，更像是“进入主交互态”的门口。

## 它暴露/定义了什么
这个文件几乎只定义了一个公开函数：`launchRepl(root, appProps, replProps, renderAndRun)`。其中 `AppWrapperProps` 是它内部的启动参数形状，包含 `getFpsMetrics`、可选 `stats` 和 `initialState`。从类型上看，它把启动时需要的全局状态和界面参数分成两层：一层给外壳 `App`，一层给真正的 `REPL` 屏幕。

## 谁调用它
根据当前片段推断，主要调用者是 `src/main.tsx`。我在该文件里看到了多处 `await launchRepl(...)`，说明它不是单次入口，而是被多个启动分支复用：包括恢复会话、不同命令路径进入交互模式、以及其他需要打开主 REPL 的场景。也就是说，`main.tsx` 负责决定“何时进 REPL”，`launchRepl` 负责决定“怎么进”。

## 它调用谁
它先动态导入 `./components/App.js`、`./components/SentryErrorBoundary.js` 和 `./screens/REPL.js`，再把三者组合成一个 React 树交给 `renderAndRun`。真正执行渲染的是外部传入的 `renderAndRun(root, element)`，因此这个文件并不直接掌控底层渲染循环，而是把渲染责任委托给上层运行器。

## 核心流程
核心流程很短，但边界清晰。第一步，接收 `root`、`appProps`、`replProps` 和 `renderAndRun`。第二步，按需动态加载 `App`、`SentryErrorBoundary`、`REPL`，把这些重模块延后到真正需要时再引入。第三步，用 `SentryErrorBoundary` 包住整个根节点，用 `App` 作为通用应用容器，再把 `REPL` 作为主屏幕放进去。第四步，把这个完整元素交给 `renderAndRun` 执行。这个顺序很重要：错误边界在最外层，`App` 提供全局状态和上下文，`REPL` 才是用户直接交互的界面。

## 关键函数的高层作用
`launchRepl` 的作用不是“渲染一个组件”这么简单，而是把启动阶段的组装规则集中到一个地方。它把启动时常见的三件事统一起来：全局应用壳、错误隔离、REPL 入口。`AppWrapperProps` 体现的是外层运行环境的依赖注入，`replProps` 体现的是会话级状态输入，`renderAndRun` 则是把 UI 交给具体运行框架。这个设计的好处是 `main.tsx` 的各个分支不需要重复拼装同样的 JSX 树。

## 修改风险
这里的风险主要是启动链路破坏，而不是单个界面样式问题。第一，`appProps` 或 `replProps` 的字段一旦和 `App`、`REPL` 的真实签名不同步，会在多个启动分支同时出错。第二，动态导入路径如果改错，会直接导致 REPL 无法启动。第三，错误边界包裹顺序不能随意变动，否则启动期异常可能泄漏到更外层。第四，这个文件被 `src/main.tsx` 多处复用，任何改动都会放大到所有进入交互态的路径上，所以它属于“改动面小，但影响面大”的文件。
