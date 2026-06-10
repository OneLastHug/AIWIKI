# 文件：plugins/model-providers/deepseek/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""DeepSeek provider profile.

DeepSeek's V4 family (and the legacy ``deepseek-reasoner``) defaults to
thinking-mode ON when ``extra_body.thinking`` is unset.  The API then returns
``reasoning_content`` and starts enforcing the contract that subsequent turns
echo it back; combined with how Hermes replays history this lands on the
notorious HTTP 400 ``reasoning_content must be passed back`` error after the
first tool call (#15700, #17212, #17825).

This profile overrides :meth:`build_api_kwargs_extras` to mirror the Kimi /
Moonshot wire shape that DeepSeek's OpenAI-compat endpoint expects:

    {"reasoning_effort": "<low|medium|high|max>",
     "extra_body": {"thinking": {"type": "enabled" | "disabled"}}}

Non-thinking models (only ``deepseek-chat`` today, which is V3) are left as
no-ops so we don't perturb the V3 wire format.
"""

from __future__ import annotations

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


def _model_supports_thinking(model: str | None) -> bool:
    """DeepSeek thinking-capable model families.

    Currently covers the V4 family (``deepseek-v4-pro``, ``deepseek-v4-flash``,
    and any future ``deepseek-v4-*`` variants) and the legacy
    ``deepseek-reasoner`` (R1).  ``deepseek-chat`` is V3 with no thinking mode.
    """
    m = (model or "").strip().lower()
    if not m:
        return False
    if m.startswith("deepseek-v") and not m.startswith("deepseek-v3"):
        # deepseek-v4-*, deepseek-v5-*, etc. — every V4+ generation has
        # thinking. v3 explicitly excluded.
        return True
    if m == "deepseek-reasoner":
        return True
    return False


class DeepSeekProfile(ProviderProfile):
    """DeepSeek — extra_body.thinking + top-level reasoning_effort."""

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        if not _model_supports_thinking(model):
            # V3 / unknown — leave wire format untouched, current behavior.
            return extra_body, top_level

        # Determine enabled/disabled.  Default is enabled to match DeepSeek's
        # API default; the API requires this to be set explicitly to avoid the
        # reasoning_content echo trap on subsequent turns.
        enabled = True
        if isinstance(reasoning_config, dict) and reasoning_config.get("enabled") is False:
            enabled = False

        extra_body["thinking"] = {"type": "enabled" if enabled else "disabled"}

        if not enabled:
            return extra_body, top_level

        # Effort mapping.  Pass low/medium/high through; xhigh/max → max.
        # When no effort is set we omit reasoning_effort so DeepSeek applies
        # its server default (currently high).
        if isinstance(reasoning_config, dict):
            effort = (reasoning_config.get("effort") or "").strip().lower()
            if effort in {"xhigh", "max"}:
                top_level["reasoning_effort"] = "max"
            elif effort in {"low", "medium", "high"}:
                top_level["reasoning_effort"] = effort

        return extra_body, top_level


deepseek = DeepSeekProfile(
    name="deepseek",
    aliases=("deepseek-chat",),
    env_vars=("DEEPSEEK_API_KEY",),
    display_name="DeepSeek",
    description="DeepSeek — native DeepSeek API",
    signup_url="[URL已移除]",
    fallback_models=(
        "deepseek-chat",
        "deepseek-reasoner",
    ),
    base_url="[URL已移除]",
    default_aux_model="deepseek-chat",
)

register_provider(deepseek)

```
