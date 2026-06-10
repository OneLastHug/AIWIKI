# 目录：packages/desktop/src/process/services/i18n

## 它负责什么

这个目录是主进程的 i18n 服务入口，职责很集中：在 Electron 主进程里初始化 `i18next`，按用户保存的语言加载资源包，并在运行时切换语言。根据当前片段推断，它更像“主进程语言状态中心”，而不是单纯的翻译工具，因为它还负责把本地存储中的语言设置接进来，并把语言切换同步给主进程里依赖 `i18n.t()` 的各个模块。

这里还有一个重要特征：它不是去磁盘动态读 JSON，而是直接静态导入 `@renderer/services/i18n/locales/*/index`。注释已经说明，这样 Vite 打包后主进程产物里就能直接带上翻译资源，开发态和生产态都能工作。

## 直接子目录地图

当前这个目录下没有子目录，只有一个入口文件 `index.ts`。  
也就是说，`packages/desktop/src/process/services/i18n` 现在是一个“单文件服务目录”，所有主流程都收敛在这一层，不再向下拆分。

从内容上看，它内部又可以分成三块逻辑：

1. 语言资源表 `localeData`
2. 初始化与等待就绪的 `i18nReady`
3. 语言切换 API：`setInitialLanguage()`、`changeLanguage()`

## 关键入口

`index.ts` 是唯一入口，也是对外 API 的出口。它做了几件关键事：

- `import i18n from 'i18next'`：拿到 i18next 实例
- `import { ProcessConfig } from '@process/utils/initStorage'`：从主进程配置里读取已保存语言
- `import { DEFAULT_LANGUAGE, normalizeLanguageCode, mergeWithFallback, ensureAndSwitch } from '@/common/config/i18n'`：复用公共 i18n 工具
- 静态导入各语言资源：`en-US`、`zh-CN`、`ja-JP`、`zh-TW`、`ko-KR`、`tr-TR`、`ru-RU`
- 导出 `i18nReady`、`setInitialLanguage()`、`changeLanguage()`、`normalizeLanguageCode`
- 默认导出 `i18n`

这里最值得注意的是 `i18nReady`。它不是一个普通函数，而是一个立即执行的异步初始化承诺：先 `i18n.init()`，再读取 `ProcessConfig.get('language')`，如果有值就调用 `ensureAndSwitch()`。这意味着其他模块如果要安全使用主进程翻译，必须等它完成。

## 主流程位置

主流程的入口在 `packages/desktop/src/process/index.ts`，这里有一行直接导入 `./services/i18n`，注释写得很明确：初始化主进程 i18n。

结合几个调用点，可以把运行链路看成下面这样：

1. 主进程启动时，`process/index.ts` 先加载 `services/i18n/index.ts`
2. `index.ts` 里先用默认语言初始化 `i18next`
3. 再从 `ProcessConfig` 读取用户语言
4. 通过 `ensureAndSwitch()`：
   - 规范化语言码
   - 必要时按语言加载资源包
   - 调用 `i18n.changeLanguage()`
5. 运行时语言变更来自 `packages/desktop/src/process/bridge/systemSettingsBridge.ts`
   - 先广播 `languageChanged`
   - 再异步调用 `changeLanguage(language)`
6. 其他主进程模块直接消费 `i18n.t()`，例如 `pet/petManager.ts`、`pet/petConfirmManager.ts`、`utils/tray.ts`
7. `packages/desktop/src/process/bridge/updateBridge.ts` 里还做了懒加载，避免在模块加载阶段就把 `initStorage` 链路拉进来

如果只看“主流程位置”，最核心的是 `process/index.ts`、`services/i18n/index.ts`、`bridge/systemSettingsBridge.ts` 这三处。

## 推荐阅读顺序

1. `packages/desktop/src/common/config/i18n.ts`  
   先看公共工具，理解 `normalizeLanguageCode()`、`mergeWithFallback()`、`ensureAndSwitch()` 的契约。

2. `packages/desktop/src/process/services/i18n/index.ts`  
   再看这个目录本体，理解主进程如何初始化、合并资源、暴露切换 API。

3. `packages/desktop/src/process/index.ts`  
   看服务何时被挂到主进程启动链上。

4. `packages/desktop/src/process/bridge/systemSettingsBridge.ts`  
   看语言切换是怎样从 IPC 触发并同步到主进程的。

5. `packages/desktop/src/process/utils/tray.ts`、`packages/desktop/src/process/pet/petManager.ts`  
   看主进程翻译的实际消费面。

## 常见误区

1. 误以为这里可以动态按文件系统加载语言包。  
   实际上这里必须用静态 import。注释已经说明，主进程是被 Vite 打包的，生产环境下不应依赖磁盘上的原始 JSON 文件。

2. 误以为 `changeLanguage()` 可以随时直接调用。  
   不行，应该先等 `i18nReady`。这个目录里已经把“初始化完成后再切换”的顺序封装好了。

3. 误以为它只服务 renderer。  
   这里是主进程服务，`tray`、`pet`、`update` 这些主进程模块都在用它。

4. 误以为新增语言只要补 locale 文件。  
   还需要在 `localeData` 里加静态导入，并确保 `@/common/config/i18n.ts` 里的支持语言集合和归一化逻辑能覆盖到它。根据当前片段推断，这一步缺一会导致主进程无法正确切换或回退。

5. 误以为 fallback 只是 `i18n` 自己处理。  
   这里还显式做了 `mergeWithFallback()`，目的是把缺失键补到默认语言上，避免局部翻译缺项直接暴露为空。
