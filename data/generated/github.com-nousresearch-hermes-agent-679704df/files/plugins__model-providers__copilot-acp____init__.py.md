# 文件：plugins/model-providers/copilot-acp/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""GitHub Copilot ACP provider profile.

copilot-acp uses an external ACP subprocess — NOT the standard
transport. api_mode="copilot_acp" is handled separately in run_agent.py.
The profile captures auth + endpoint metadata for registry migration.
"""

from providers import register_provider
from providers.base import ProviderProfile


class CopilotACPProfile(ProviderProfile):
    """GitHub Copilot ACP — external process, no REST models endpoint."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Model listing is handled by the ACP subprocess."""
        return None


copilot_acp = CopilotACPProfile(
    name="copilot-acp",
    aliases=("github-copilot-acp", "copilot-acp-agent"),
    api_mode="chat_completions",  # ACP subprocess uses chat_completions routing
    env_vars=(),  # Managed by ACP subprocess
    base_url="acp://copilot",  # ACP internal scheme
    auth_type="external_process",
)

register_provider(copilot_acp)

```
