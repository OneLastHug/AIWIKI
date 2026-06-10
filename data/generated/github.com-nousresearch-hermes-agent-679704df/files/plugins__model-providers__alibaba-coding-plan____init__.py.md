# 文件：plugins/model-providers/alibaba-coding-plan/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""Alibaba Cloud Coding Plan provider profile.

Separate from the standard `alibaba` profile because it hits a different
endpoint (coding-intl.dashscope.aliyuncs.com) with a dedicated API key tier.
"""

from providers import register_provider
from providers.base import ProviderProfile

alibaba_coding_plan = ProviderProfile(
    name="alibaba-coding-plan",
    aliases=("alibaba_coding", "alibaba-coding", "dashscope-coding"),
    display_name="Alibaba Cloud (Coding Plan)",
    description="Alibaba Cloud Coding Plan — dedicated coding tier",
    signup_url="[URL已移除]",
    env_vars=("ALIBABA_CODING_PLAN_API_KEY", "DASHSCOPE_API_KEY", "ALIBABA_CODING_PLAN_BASE_URL"),
    base_url="[URL已移除]",
    auth_type="api_key",
)

register_provider(alibaba_coding_plan)

```
