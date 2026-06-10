# 文件：next/src/services/agent/agent-work/create-task-work.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type AgentWork from "./agent-work";
import type { Task } from "../../../types/task";
import type AutonomousAgent from "../autonomous-agent";

export default class CreateTaskWork implements AgentWork {
  taskValues: string[] = [];

  constructor(private parent: AutonomousAgent, private task: Task) {}

  run = async () => {
    this.taskValues = await this.parent.api.getAdditionalTasks(
      {
        current: this.task.value,
        remaining: this.parent.model.getRemainingTasks().map((task) => task.value),
        completed: this.parent.model.getCompletedTasks().map((task) => task.value),
      },
      this.task.result || ""
    );
  };

  conclude = async () => {
    const TIMEOUT_LONG = 1000;
    this.parent.api.saveMessages(await this.parent.createTaskMessages(this.taskValues));
    await new Promise((r) => setTimeout(r, TIMEOUT_LONG));
  };

  next = () => undefined;

  // Ignore errors and simply avoid creating more tasks
  onError = (): boolean => false;
}

```
