# 文件：plugins/model-providers/gemini/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""Google Gemini provider profiles.

gemini:            Google AI Studio (API key) — uses GeminiNativeClient
google-gemini-cli: Google Cloud Code Assist (OAuth) — uses GeminiCloudCodeClient

Both report api_mode="chat_completions" but use custom native clients
that bypass the standard OpenAI transport. The profile captures auth
and endpoint metadata for auth.py / runtime_provider.py migration, and
carries the thinking_config translation hook so the transport's profile
path produces the same extra_body shape the legacy flag path did.
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class GeminiProfile(ProviderProfile):
    """Gemini — translate reasoning_config to thinking_config in extra_body."""

    def build_extra_body(
        self, *, session_id: str | None = None, **context: Any
    ) -> dict[str, Any]:
        """Emit extra_body.thinking_config (native) or extra_body.extra_body.google.thinking_config
        (OpenAI-compat /openai subpath), mirroring the legacy path's behavior.
        """
        from agent.transports.chat_completions import (
            _build_gemini_thinking_config,
            _is_gemini_openai_compat_base_url,
            _snake_case_gemini_thinking_config,
        )

        model = context.get("model") or ""
        reasoning_config = context.get("reasoning_config")
        base_url = context.get("base_url") or self.base_url

        raw_thinking_config = _build_gemini_thinking_config(model, reasoning_config)
        if not raw_thinking_config:
            return {}

        body: dict[str, Any] = {}
        if self.name == "gemini" and _is_gemini_openai_compat_base_url(base_url):
            thinking_config = _snake_case_gemini_thinking_config(raw_thinking_config)
            if thinking_config:
                body["extra_body"] = {"google": {"thinking_config": thinking_config}}
        else:
            body["thinking_config"] = raw_thinking_config
        return body


gemini = GeminiProfile(
    name="gemini",
    aliases=("google", "google-gemini", "google-ai-studio"),
    api_mode="chat_completions",
    env_vars=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    base_url="[URL已移除]",
    auth_type="api_key",
    default_aux_model="gemini-3-flash-preview",
)

google_gemini_cli = GeminiProfile(
    name="google-gemini-cli",
    aliases=("gemini-cli", "gemini-oauth"),
    api_mode="chat_completions",
    env_vars=(),  # OAuth — no API key
    base_url="cloudcode-pa://google",  # Cloud Code Assist internal scheme
    auth_type="oauth_external",
)

register_provider(gemini)
register_provider(google_gemini_cli)

```
