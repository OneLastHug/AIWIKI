# 文件：platform/reworkd_platform/db/models/agent.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import mapped_column

from reworkd_platform.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_run"

    user_id = mapped_column(String, nullable=False)
    goal = mapped_column(Text, nullable=False)
    create_date = mapped_column(
        DateTime, name="create_date", server_default=func.now(), nullable=False
    )


class AgentTask(Base):
    __tablename__ = "agent_task"

    run_id = mapped_column(String, nullable=False)
    type_ = mapped_column(String, nullable=False, name="type")
    create_date = mapped_column(
        DateTime, name="create_date", server_default=func.now(), nullable=False
    )

```
