# 文件：packages/coding-agent/examples/extensions/dynamic-resources/index.ts
## 一句话定位
这是一个 `coding-agent` 扩展示例的入口文件，核心作用不是提供业务逻辑，而是在运行时通过 `resources_discover` 事件向框架声明一组动态可发现资源，包括 skill、prompt 模板和 theme 配置。

## 它暴露/定义了什么
它只导出一个默认函数 `default function (pi: ExtensionAPI)`。这个函数本身不返回业务对象，而是作为扩展注册器使用：框架把 `pi` 传进来后，扩展在其上监听事件。当前文件定义的唯一行为是监听 `resources_discover`，并返回三类资源路径：
`skillPaths`、`promptPaths`、`themePaths`，分别指向同目录下的 `SKILL.md`、`dynamic.md`、`dynamic.json`。

## 谁调用它
根据当前片段推断，它由 `@earendil-works/pi-coding-agent` 的扩展加载机制调用。依据是文件默认导出接收 `ExtensionAPI`，这类签名通常意味着框架会在启动或扫描扩展时执行该函数，并把事件总线式 API 注入进去。

## 它调用谁
它只调用了 `pi.on("resources_discover", ...)` 这一框架 API。除此之外，它还调用了标准库的 `fileURLToPath(import.meta.url)` 和 `dirname/join`，用于把当前模块位置转换成稳定的文件系统路径。

## 核心流程
1. 先用 `fileURLToPath(import.meta.url)` 拿到当前文件路径，再用 `dirname(...)` 计算 `baseDir`。
2. 默认导出函数被框架执行后，向 `pi` 注册 `resources_discover` 事件处理器。
3. 当框架触发资源发现阶段时，处理器返回一个资源清单对象。
4. 框架据此加载 `SKILL.md` 作为技能说明，加载 `dynamic.md` 作为提示模板，加载 `dynamic.json` 作为主题配置。

## 关键函数的高层作用
`default function (pi: ExtensionAPI)` 是入口和注册点，职责很窄，只负责把“这个扩展有哪些动态资源”告诉框架。`resources_discover` 回调是实际的资源声明器，它不解析内容，只提供路径。`baseDir` 相关逻辑则保证资源定位不依赖工作目录，避免扩展在不同启动方式下失效。

## 修改风险
这个文件的风险主要在“路径和约定”而不是算法。改动 `join(baseDir, ...)` 的结果、文件名，或事件名 `resources_discover`，都会导致框架找不到资源，扩展示例失效。另一个风险是资源文件语义不一致：`SKILL.md`、`dynamic.md`、`dynamic.json` 是三类不同消费方的输入，改内容时要同时考虑下游如何读取。因为它是示例入口，最容易出问题的是路径拼接、导出形式，或者把静态资源改成了不符合框架预期的格式。
