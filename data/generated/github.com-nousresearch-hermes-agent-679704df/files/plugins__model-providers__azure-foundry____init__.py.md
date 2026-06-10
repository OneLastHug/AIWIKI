# 文件：plugins/model-providers/azure-foundry/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""Microsoft Foundry provider profile.

Azure Foundry exposes an OpenAI-compatible endpoint; users supply their own
base URL at setup since endpoints are per-resource.
"""

from providers import register_provider
from providers.base import ProviderProfile

azure_foundry = ProviderProfile(
    name="azure-foundry",
    aliases=("azure", "azure-ai-foundry", "azure-ai"),
    display_name="Azure Foundry",
    description="Microsoft Foundry - OpenAI-compatible endpoint (user-supplied base URL)",
    signup_url="[URL已移除]",
    env_vars=("AZURE_FOUNDRY_API_KEY", "AZURE_FOUNDRY_BASE_URL"),
    base_url="",  # per-resource; user provides at setup
    auth_type="api_key",
)

register_provider(azure_foundry)

```
