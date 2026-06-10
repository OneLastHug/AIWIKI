# 文件：platform/reworkd_platform/web/api/models/views.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from reworkd_platform.schemas.agent import LLM_MODEL_MAX_TOKENS
from reworkd_platform.schemas.user import UserBase
from reworkd_platform.web.api.dependencies import get_current_user

router = APIRouter()


class ModelWithAccess(BaseModel):
    name: str
    max_tokens: int
    has_access: bool = Field(
        default=False, description="Whether the user has access to this model"
    )

    @staticmethod
    def from_model(name: str, max_tokens: int, user: UserBase) -> "ModelWithAccess":
        has_access = user is not None
        return ModelWithAccess(name=name, max_tokens=max_tokens, has_access=has_access)


@router.get("")
async def get_models(
    user: UserBase = Depends(get_current_user),
) -> List[ModelWithAccess]:
    return [
        ModelWithAccess.from_model(name=model, max_tokens=tokens, user=user)
        for model, tokens in LLM_MODEL_MAX_TOKENS.items()
    ]

```
