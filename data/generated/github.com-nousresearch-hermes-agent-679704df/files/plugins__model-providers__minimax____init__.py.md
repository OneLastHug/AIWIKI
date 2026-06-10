# 文件：plugins/model-providers/minimax/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""MiniMax provider profiles (international + China).

Both use anthropic_messages api_mode — their inference_base_url
ends with /anthropic which triggers auto-detection to anthropic_messages.
"""

from providers import register_provider
from providers.base import ProviderProfile

minimax = ProviderProfile(
    name="minimax",
    aliases=("mini-max",),
    api_mode="anthropic_messages",
    env_vars=("MINIMAX_API_KEY",),
    base_url="[URL已移除]",
    auth_type="api_key",
    default_aux_model="MiniMax-M2.7",
)

minimax_cn = ProviderProfile(
    name="minimax-cn",
    aliases=("minimax-china", "minimax_cn"),
    api_mode="anthropic_messages",
    env_vars=("MINIMAX_CN_API_KEY",),
    base_url="[URL已移除]",
    auth_type="api_key",
    default_aux_model="MiniMax-M2.7",
)

minimax_oauth = ProviderProfile(
    name="minimax-oauth",
    aliases=("minimax_oauth", "minimax-oauth-io"),
    api_mode="anthropic_messages",
    display_name="MiniMax (OAuth)",
    description="MiniMax via OAuth browser flow — no API key required",
    signup_url="[URL已移除]",
    env_vars=(),  # OAuth — tokens in auth.json, not env
    base_url="[URL已移除]",
    auth_type="oauth_external",
    default_aux_model="MiniMax-M2.7-highspeed",
)

register_provider(minimax)
register_provider(minimax_cn)
register_provider(minimax_oauth)

```
