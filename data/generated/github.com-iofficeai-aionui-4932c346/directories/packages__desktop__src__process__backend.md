# 目录：packages/desktop/src/process/backend

## 它负责什么

这个目录的职责很集中：为桌面端后端进程提供 `aioncore` 可执行文件的定位能力。当前片段里，核心能力只有一个，就是 `resolveBinaryPath()`，它会先尝试在应用打包后的资源目录里找随包分发的二进制，再退回到系统 `PATH`。如果两条路都失败，就抛出带诊断信息的自定义错误，方便排查为什么找不到二进制。

从结构上看，这里不是“业务后端”目录，而是“后端进程里的基础设施层”。它更像一个启动依赖解析器，给后续真正调用 `aioncore` 的流程提供路径。

## 直接子目录地图

根据当前片段推断，这个目录下没有子目录，只有三个文件：

- `index.ts`：对外出口，重新导出 `resolveBinaryPath`
- `binaryResolver.ts`：主实现，负责查找和诊断
- `binaryResolver.test.ts`：单测，验证失败场景下的诊断内容

也就是说，这里是一个很扁平的小目录，适合把“一个能力 + 一组测试”放在一起，避免职责扩散。

## 关键入口

真正的入口在 `binaryResolver.ts` 里的 `resolveBinaryPath()`，而 `index.ts` 只是把它向外导出。对上层模块来说，通常只需要从这个目录的 `index.ts` 引入即可，不必关心内部实现细节。

`resolveBinaryPath()` 的关键配套对象是 `BackendBinaryResolveError` 和 `BackendBinaryResolveDiagnostics`。前者是失败时抛出的错误类型，后者是错误里附带的诊断数据结构。这个设计说明作者希望“找不到二进制”时不是简单报错，而是把运行时环境、路径尝试结果、PATH 查询命令等信息一并留下。

## 主流程位置

主流程主要集中在 `binaryResolver.ts`：

1. `resolveBinaryPath()` 先根据运行环境生成 `runtimeKey`，格式是 `platform-arch`
2. 再根据平台决定二进制名，Windows 下是 `aioncore.exe`，其他平台是 `aioncore`
3. 然后先走 `bundledPath()`，即检查应用资源目录下的 `bundled-aioncore/{platform-arch}/` 结构
4. 如果打包内路径不存在，再走 `resolveFromSystemPATH()`，通过 `which aioncore` 或 `where aioncore` 查系统路径
5. 两条路都失败时，抛出 `BackendBinaryResolveError`，并把 diagnostics 带上

这里还有两个细节值得注意：

- `bundledPath()` 会读取 `process.resourcesPath`，所以它明显是面向打包后的运行态，不是纯开发态逻辑
- `resolveFromSystemPATH()` 不只是拿命令输出，还会再次用 `existsSync()` 校验首个匹配路径是否真的存在，避免“命令输出了路径但文件不可用”的假阳性

## 推荐阅读顺序

如果你是第一次看这个目录，建议按下面顺序读：

1. `index.ts`：先确认对外暴露了什么
2. `binaryResolver.ts` 顶部常量和类型：先理解 `BINARY_NAME`、`MAX_DIR_ENTRIES`、`BackendBinaryResolveDiagnostics`
3. `resolveBinaryPath()`：看主流程怎么串起来
4. `bundledPath()`：理解打包资源目录约定
5. `resolveFromSystemPATH()`：理解系统回退路径
6. `binaryResolver.test.ts`：最后看测试如何验证失败时的诊断字段

这个顺序能帮助你先建立调用视角，再补实现细节，不容易一开始就被局部工具函数带偏。

## 常见误区

第一，这里不是“后端功能集合目录”。它只做一件事：解析 `aioncore` 的路径。不要把它和真正的业务服务、数据处理或 IPC 逻辑混在一起。

第二，容易忽略 `process.resourcesPath`。这个目录默认面向桌面应用打包后的运行环境，`bundled-aioncore/{platform-arch}/` 是它的关键约定。只看 `PATH` 会漏掉最重要的生产路径。

第三，不要以为 `which` 或 `where` 的输出就足够可靠。实现里还做了 `existsSync()` 二次确认，所以调试时要同时关注“命令输出”和“文件是否真存在”。

第四，失败时别只盯着异常消息。这里的价值在 `diagnostics`，它记录了 runtimeKey、候选路径、目录枚举结果和 PATH 查询错误文本。排障时应优先看这些字段，而不是只看顶层报错字符串。
