# 文件：packages/tui/src/index.ts
## 一句话定位
这是 `@earendil-works/pi-tui` 的总出口文件，作用不是实现业务逻辑，而是把 TUI 包里分散在各个模块的能力统一整理成一个对外稳定的 API 入口，方便上层直接 `import { ... } from "@earendil-works/pi-tui"`。

## 它暴露/定义了什么
这个文件几乎全部由 `export` 组成，按领域分组暴露了整套公共接口：自动补全相关的 `AutocompleteProvider`、`CombinedAutocompleteProvider`、`SlashCommand`；组件层的 `Box`、`Editor`、`Input`、`Markdown`、`SelectList`、`SettingsList`、`Text`、`Spacer` 等；键盘与按键处理的 `Key`、`parseKey`、`matchesKey`、`KeybindingsManager`；终端能力与图片渲染的 `getCapabilities`、`renderImage`、`encodeKitty`、`detectCapabilities`；核心容器与 UI 协调对象的 `Component`、`Container`、`TUI`；以及文本宽度和包装工具 `truncateToWidth`、`visibleWidth`、`wrapTextWithAnsi`。

从文件内容看，它没有定义自己的复杂状态或算法，主要职责是做“公共 API 聚合层”。

## 谁调用它
根据当前片段推断，它主要被三类地方调用：

1. 外部消费者：仓库里大量代码都通过包名 `@earendil-works/pi-tui` 引入能力，例如 `packages/coding-agent/src/modes/interactive/*`、`packages/coding-agent/src/core/*`、测试文件和示例扩展。
2. 本仓库的开发态配置：`packages/coding-agent/vitest.config.ts` 把 `@earendil-works/pi-tui` 映射到 `packages/tui/src/index.ts`，让测试直接吃源码。
3. TypeScript/构建配置：`packages/coding-agent/tsconfig.examples.json` 也把这个包名指向该入口，说明它是示例和联调时的统一入口。

换句话说，`index.ts` 是 TUI 包的“门面”，上层代码基本都从这里拿能力，而不是直接摸内部文件。

## 它调用谁
这个文件本身不主动执行业务流程，只是把下列模块的导出重新汇总起来：`autocomplete.ts`、`components/*`、`editor-component.ts`、`fuzzy.ts`、`keybindings.ts`、`keys.ts`、`stdin-buffer.ts`、`terminal.ts`、`terminal-image.ts`、`tui.ts`、`utils.ts`。  
因此它更像“路由表”，把内部实现模块连接成一个对外稳定的包边界。

## 核心流程
核心流程很简单：

1. 上层代码通过包名导入 `@earendil-works/pi-tui`。
2. 构建期或测试期把这个包名解析到 `packages/tui/src/index.ts`。
3. 这个入口文件再把具体能力分发到各个实现模块。
4. 消费者拿到的是统一命名空间下的组件、终端能力、按键工具、文本工具和 TUI 核心对象。
5. 这样上层只依赖一个入口，就能拼装整套终端 UI，而不需要关心内部文件布局。

## 关键函数的高层作用
这里没有真正“定义”核心函数，但有几组最关键的对外能力值得按职责理解：

- `TUI`：整个终端 UI 的总协调器，负责组件树、输入分发、渲染和 overlay 管理，是上层交互流的核心。
- `Container`、`Component`：组件抽象和组合容器，支撑树形 UI 结构。
- `getKeybindings`、`setKeybindings`、`KeybindingsManager`：集中管理快捷键配置和查询。
- `parseKey`、`matchesKey`、`isKeyRelease`、`decodeKittyPrintable`：处理原始键盘输入与终端协议差异。
- `renderImage`、`getCapabilities`、`detectCapabilities`：处理终端图片协议和能力探测。
- `fuzzyMatch`、`fuzzyFilter`：给搜索、选择器、补全等交互提供模糊匹配。
- `visibleWidth`、`truncateToWidth`、`wrapTextWithAnsi`：保证终端文本排版在可见宽度内正确工作。

## 修改风险
这个文件的风险不在逻辑正确性，而在 API 边界稳定性。这里新增、删除或改名任何导出，都会直接影响 `packages/coding-agent`、示例扩展、测试和外部使用者；尤其是 `TUI`、`Component`、`Keybindings`、`terminal-image` 这类高频入口，改动会迅速扩散到大量调用点。  
另外，它还是源码联调的统一映射点，所以一旦导出列表与内部模块不同步，就可能出现“编译期能过、运行期缺导出”或声明文件不一致的问题。对这个文件的改动，通常要优先看它是否破坏公共包面，而不是只看本地能否通过编译。
