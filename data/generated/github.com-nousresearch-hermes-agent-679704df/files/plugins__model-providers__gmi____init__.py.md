# 文件：plugins/model-providers/gmi/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""GMI Cloud provider profile."""

from hermes_cli import __version__ as _HERMES_VERSION
from providers import register_provider
from providers.base import ProviderProfile

gmi = ProviderProfile(
    name="gmi",
    aliases=("gmi-cloud", "gmicloud"),
    display_name="GMI Cloud",
    description="GMI Cloud — multi-model direct API (slash-form model IDs)",
    signup_url="[URL已移除]",
    env_vars=("GMI_API_KEY", "GMI_BASE_URL"),
    base_url="[URL已移除]",
    auth_type="api_key",
    # Attribution so GMI can identify traffic from Hermes Agent.
    # The generic profile.default_headers fallback in run_agent.py and
    # agent/auxiliary_client.py picks this up at client construction time.
    default_headers={"User-Agent": f"HermesAgent/{_HERMES_VERSION}"},
    default_aux_model="google/gemini-3.1-flash-lite-preview",
    fallback_models=(
        "zai-org/GLM-5.1-FP8",
        "deepseek-ai/DeepSeek-V3.2",
        "moonshotai/Kimi-K2.5",
        "google/gemini-3.1-flash-lite-preview",
        "anthropic/claude-sonnet-4.6",
        "openai/gpt-5.4",
    ),
)

register_provider(gmi)

```
