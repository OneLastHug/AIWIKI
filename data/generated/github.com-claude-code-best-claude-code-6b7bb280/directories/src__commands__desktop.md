# 目录：src/commands/desktop

## 它负责什么
`src/commands/desktop` 负责把当前 Claude Code 会话迁移到 Claude Desktop。它不是一个复杂的命令集合，而是一条很短的“手动交接”链路：先检查桌面端是否已安装、版本是否足够，再把当前会话写入持久化状态，最后通过深链接把会话打开到 Desktop 里。

根据当前片段推断，这个目录的职责非常集中，属于“命令定义 + 交互 UI + 系统跳转”三段式封装。它本身不保存业务状态，真正的会话数据仍由上层的 session/bootstrap 体系提供。

## 直接子目录地图
这个目录下没有子目录，只有两个直接文件：

- `src/commands/desktop/index.ts`：命令注册与平台可用性控制
- `src/commands/desktop/desktop.tsx`：命令执行入口，渲染实际交互组件

再往下的关键依赖不在本目录里，而是在其他模块中：

- `src/components/DesktopHandoff.tsx`：真正的交互流程
- `src/utils/desktopDeepLink.ts`：安装检测、版本检测、深链接打开
- `src/commands.ts`：把 `desktop` 挂进全局命令表

## 关键入口
这个目录的对外入口是 `src/commands/desktop/index.ts` 导出的默认对象。它定义了：

- `name: 'desktop'`
- `aliases: ['app']`
- `description: 'Continue the current session in Claude Desktop'`
- `type: 'local-jsx'`
- `load: () => import('./desktop.js')`

也就是说，`desktop` 是一个延迟加载的本地 JSX 命令，不会在启动时就把 UI 全部拉起。

对应的执行入口是 `src/commands/desktop/desktop.tsx` 中的 `call()`，它几乎不做逻辑，只是返回：

```tsx
<DesktopHandoff onDone={onDone} />
```

真正的命令行为都下沉到了 `DesktopHandoff` 组件。

## 主流程位置
主流程可以按这条线理解：

1. `src/commands.ts` 注册 `desktop`
2. 用户触发 `desktop` 或别名 `app`
3. `src/commands/desktop/desktop.tsx` 加载 `DesktopHandoff`
4. `src/components/DesktopHandoff.tsx` 执行交接流程
5. `src/utils/desktopDeepLink.ts` 负责安装探测、版本检查和深链接打开
6. 成功后调用 `gracefulShutdown(0, 'other')` 退出 CLI

`DesktopHandoff` 的状态机比较清楚：`checking`、`prompt-download`、`flushing`、`opening`、`success`、`error`。如果没装或版本过旧，会提示下载；如果环境满足条件，就先 `flushSessionStorage()`，再用 `openCurrentSessionInDesktop()` 打开 deep link。

## 推荐阅读顺序
1. `src/commands/desktop/index.ts`：先看命令是怎么注册和隐藏的
2. `src/commands/desktop/desktop.tsx`：确认命令执行时只做了最薄的一层转发
3. `src/components/DesktopHandoff.tsx`：理解完整交接状态机
4. `src/utils/desktopDeepLink.ts`：看平台检测、版本门槛和 URL 打开方式
5. `src/commands.ts`：确认它在全局命令表中的挂载位置

## 常见误区
- 以为这是一个“桌面端主程序”目录。实际上它只是 CLI 里的一个迁移命令入口，真正的 Desktop 应用不在这里。
- 以为 `desktop.tsx` 里有主逻辑。实际上它只是薄包装，核心逻辑在 `DesktopHandoff` 和 `desktopDeepLink`。
- 以为它在所有平台都可用。根据当前片段推断，`index.ts` 只允许 `darwin` 和 `win32 x64`，并且会在其他平台隐藏。
- 以为“安装检测”和“打开深链接”是同一件事。其实前者是 `getDesktopInstallStatus()`，后者是 `openCurrentSessionInDesktop()`，两步分离，失败原因也不同。
- 以为命令失败就直接报错退出。实际上它会先给用户下载提示，允许手动选择是否继续，并保留系统级提示文案。
