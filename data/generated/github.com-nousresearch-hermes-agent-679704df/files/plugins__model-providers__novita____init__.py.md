# 文件：plugins/model-providers/novita/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""NovitaAI provider profile."""

from providers import register_provider
from providers.base import ProviderProfile


novita = ProviderProfile(
    name="novita",
    aliases=("novita-ai", "novitaai"),
    display_name="NovitaAI",
    description="NovitaAI — AI-native cloud for builders and agents",
    signup_url="[URL已移除]",
    env_vars=("NOVITA_API_KEY", "NOVITA_BASE_URL"),
    base_url="[URL已移除]",
    auth_type="api_key",
    default_aux_model="deepseek/deepseek-v3-0324",
    fallback_models=(
        "moonshotai/kimi-k2.5",
        "minimax/minimax-m2.7",
        "zai-org/glm-5",
        "deepseek/deepseek-v3-0324",
        "deepseek/deepseek-r1-0528",
        "qwen/qwen3-235b-a22b-fp8",
    ),
)

register_provider(novita)

```
