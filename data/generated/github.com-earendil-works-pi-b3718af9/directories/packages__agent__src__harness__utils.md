# 子系统：packages/agent/src/harness/utils

## 解决什么问题
这个目录提供的是 harness 层的“输出整理与执行结果采集”基础能力。它不直接负责模型推理、会话树管理或工具调度，而是把底层 `ExecutionEnv` 产生的命令输出，整理成适合 agent 侧消费的形态：一方面统一截断规则，避免超长输出把上下文撑爆；另一方面把 shell 执行的 stdout / stderr 合并、清洗、落盘，保留可回溯的完整日志。根据当前片段推断，这个目录的设计目标是让上层 `AgentHarness` 只关心“拿到一段可靠、可读、可追溯的结果”，而不用重复处理字节数、换行、二进制脏字符和临时文件保存。

## 相关目录和文件
这里的核心文件只有两个：`packages/agent/src/harness/utils/truncate.ts` 和 `packages/agent/src/harness/utils/shell-output.ts`。前者实现通用截断策略，后者实现 shell 输出采集。它们位于 `packages/agent/src/harness/` 之下，和同层的 `agent-harness.ts`、`messages.ts`、`types.ts`、`session/`、`compaction/` 一起构成 agent 运行时的支撑面。

从导出关系看，`packages/agent/src/index.ts` 会把 `./harness/utils/shell-output.ts`、`./harness/utils/truncate.ts` 直接重新导出，说明这是对外可见的公共能力，不只是内部私有实现。`shell-output.ts` 又依赖 `../types.ts` 里的 `ExecutionEnv`、`ExecutionEnvExecOptions`、`ExecutionError`、`Result`、`ok`、`err`、`toError`，因此它本质上是 harness 执行抽象上的一个适配器。

## 核心对象
`truncate.ts` 的核心对象是 `TruncationResult`、`TruncationOptions` 和三个常量 `DEFAULT_MAX_LINES`、`DEFAULT_MAX_BYTES`、`GREP_MAX_LINE_LENGTH`。围绕它们提供了 `truncateHead`、`truncateTail`、`truncateLine`、`formatSize` 四类能力：前两者按头/尾保留完整行，`truncateLine` 专门处理 grep 这类单行结果，`formatSize` 负责可读化字节数。

`shell-output.ts` 的核心对象是 `ShellCaptureOptions`、`ShellCaptureResult`、`sanitizeBinaryOutput`、`executeShellWithCapture`。其中 `ShellCaptureResult` 额外保留了 `fullOutputPath`，表示当输出过长时，完整内容会被写入临时日志文件，而不是只留截断尾部。`sanitizeBinaryOutput` 则负责去掉控制字符，防止终端输出污染上层消息。

## 运行流程
典型流程是：上层传入 `ExecutionEnv` 和命令字符串，`executeShellWithCapture` 通过 `env.exec` 执行命令，同时把 stdout 和 stderr 都接到同一个 chunk 处理器里。每个 chunk 会先做二进制字符清洗，再去掉 `\r`，随后累计字节数。若总量超过 `DEFAULT_MAX_BYTES`，函数会创建临时文件并把完整输出继续追加进去；否则只保留内存里的尾部片段。

命令结束后，函数再对尾部内容做 `truncateTail`，确保最终返回值符合展示上限。若执行被中止，则返回 `cancelled: true`，`exitCode` 置空；若出现异常，则统一包装成 `ExecutionError`。这个流程把“运行、截断、持久化、错误归一化”串成了一条线。

## 上下游依赖
上游依赖主要是 `ExecutionEnv` 抽象。也就是说，这里并不关心具体是 Node、Bun 还是其他宿主，只要实现了文件系统和 shell 接口，就能工作。`truncate.ts` 还会依赖运行时的 `Buffer` 能力；如果没有 `Buffer`，它会退回到手写的 UTF-8 字节计数逻辑，这说明它要兼容更宽的执行环境。

下游依赖主要是 `AgentHarness` 和消息层。`agent-harness.ts` 负责整个 agent turn 的编排，shell 输出的采集结果会被包装成消息或事件，进入会话记录、调试输出或上下文构建链路。`messages.ts` 里也有把 bash 执行结果转成文本消息的逻辑，和这里的 `ShellCaptureResult` 形成配套。整体上，这个目录处在“执行环境”与“agent 可见消息”之间的中间层。

## 修改时最容易踩的坑
最容易出问题的是字节数和字符数混用。这里的截断上限是按 UTF-8 字节计算，不是按 `string.length`。如果改动时只看字符数，中文、emoji 或组合字符都会让截断行为偏离预期。

第二个坑是破坏“完整输出可追溯”这条语义。`executeShellWithCapture` 在输出过长时会把完整内容写到临时文件，并把路径带回去；如果删掉这个分支，上层只能看到尾部片段，排障能力会明显下降。

第三个坑是把控制字符过滤得过度。当前只清理会污染显示的控制码，但保留了制表、换行和回车的处理边界；如果清洗策略变严，可能会损坏原始命令输出的结构。

## 推荐阅读顺序
先读 `packages/agent/src/harness/utils/truncate.ts`，理解截断策略和返回结构。再读 `packages/agent/src/harness/utils/shell-output.ts`，看它如何把截断策略接到 `ExecutionEnv` 上。然后看 `packages/agent/src/harness/types.ts`，把 `ExecutionEnv`、`ExecutionError`、`Result` 这些基础类型补齐。最后回到 `packages/agent/src/harness/agent-harness.ts` 和 `packages/agent/src/index.ts`，理解这些工具是怎样被编排层消费并对外导出的。
