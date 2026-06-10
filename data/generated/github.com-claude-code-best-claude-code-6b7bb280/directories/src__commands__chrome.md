# 目录：src/commands/chrome

## 它负责什么

`src/commands/chrome` 是 Claude Code 里“Claude in Chrome”这条本地命令的入口目录，负责提供一个交互式设置面板，用来管理 Chrome 扩展相关能力、默认启用状态、权限跳转和重连流程。根据当前片段推断，这里不是浏览器控制逻辑本身，而是“配置与引导入口”，真正的浏览器集成能力分散在 `src/utils/claudeInChrome/` 一带。

从目录职责上看，它做三件事：第一，向命令系统注册 `chrome` 子命令；第二，渲染一个终端内的设置对话框；第三，把用户操作转成打开扩展页、权限页、重连页或切换全局配置的动作。

## 直接子目录地图

这个目录下当前没有直接子目录。  
从文件层面看，只有两个入口文件：

- `src/commands/chrome/index.ts`
- `src/commands/chrome/chrome.tsx`

因此这里更像一个“小型命令模块”，而不是一个多层级功能目录。和它配合的关键逻辑在目录外部，比如 `src/utils/claudeInChrome/common.ts`、`src/utils/claudeInChrome/setup.ts`、`src/utils/config.ts`、`src/utils/browser.ts`。

## 关键入口

- `src/commands/chrome/index.ts`  
  这是命令注册点。它导出 `chrome` 命令对象，描述为 `Claude in Chrome (Beta) settings`，并通过 `load: () => import('./chrome.js')` 懒加载真正的 UI 组件。这里还通过 `getIsNonInteractiveSession()` 控制命令是否可用，说明它只适合交互式会话。

- `src/commands/chrome/chrome.tsx`  
  这是实际页面和交互逻辑的核心。它导入 `Dialog`、`Select`、`useAppState`，以及 Chrome 相关工具函数，负责拼出设置面板并处理用户动作。

## 主流程位置

主流程基本都在 `src/commands/chrome/chrome.tsx`：

1. `call()` 先读取当前状态  
   它会调用 `isChromeExtensionInstalled()`、`getGlobalConfig()`、`isClaudeAISubscriber()`、`env.isWslEnvironment()`，把运行环境、订阅资格和扩展安装状态准备好。

2. `ClaudeInChromeMenu()` 负责渲染与交互  
   这里根据 `mcp.clients` 判断 `claude-in-chrome` MCP 是否已连接，再决定显示 `Enabled`、`Disabled`、`Installed`、`Not detected` 等状态。

3. 用户动作被映射成固定行为  
   - `install-extension`：打开扩展安装页
   - `reconnect`：重新检测扩展并打开重连页
   - `manage-permissions`：打开权限管理页
   - `toggle-default`：写入 `claudeInChromeDefaultEnabled`

4. 运行环境分支  
   如果是 `WSL`，直接提示不支持；如果不是 `ant` 用户且不是 `claude.ai` 订阅者，也会阻止继续使用。  
   打开链接时会区分 `openBrowser()` 和 `openInChrome()`，说明这里兼顾了 homespace 场景和普通桌面场景。

5. 与全局状态联动  
   `useAppState(s => s.mcp.clients)` 让这个设置页能直接感知当前 MCP 连接状态，所以它不是静态帮助页，而是和会话状态实时联动的设置界面。

## 推荐阅读顺序

1. 先看 `src/commands/chrome/index.ts`，确认这个命令如何被注册和懒加载。  
2. 再看 `src/commands/chrome/chrome.tsx`，抓住 UI、状态判断和动作分发。  
3. 然后回头看 `src/utils/claudeInChrome/common.ts`，理解 `CLAUDE_IN_CHROME_MCP_SERVER_NAME`、`openInChrome()` 这类公共能力。  
4. 最后看 `src/utils/claudeInChrome/setup.ts`，补全扩展检测、自动启用和环境判断的细节。

## 常见误区

- 它不是 Chrome 插件本体。这个目录只管命令入口和设置界面，插件安装、连接和环境适配在别处。
- 它也不是主 CLI 启动流程。真正的命令分发发生在 `src/main.tsx` 和 `src/entrypoints/cli.tsx`，这里是其中一个子命令模块。
- `install-extension`、`reconnect`、`manage-permissions` 这些选项看起来像纯 UI，其实都带有外部跳转和状态刷新。
- `toggle-default` 不是临时开关，而是写入全局配置 `claudeInChromeDefaultEnabled`，会影响后续启动行为。
- 这里的状态显示依赖 `mcp.clients`，所以“已连接/未连接”判断来自当前会话，而不是只看扩展是否安装。

根据当前片段推断，这个目录的定位很清楚：它是 Claude in Chrome 功能的“本地配置面板”，负责把用户从命令入口带到可操作的浏览器集成状态。
