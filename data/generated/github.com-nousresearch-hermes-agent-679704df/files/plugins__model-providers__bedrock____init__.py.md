# 文件：plugins/model-providers/bedrock/__init__.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
"""AWS Bedrock provider profile."""

from providers import register_provider
from providers.base import ProviderProfile


class BedrockProfile(ProviderProfile):
    """AWS Bedrock — no REST /v1/models endpoint; uses AWS SDK."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Bedrock model listing requires AWS SDK, not a REST call."""
        return None


bedrock = BedrockProfile(
    name="bedrock",
    aliases=("aws", "aws-bedrock", "amazon-bedrock", "amazon"),
    api_mode="bedrock_converse",
    env_vars=(),  # AWS SDK credentials — not env vars
    base_url="[URL已移除]",
    auth_type="aws_sdk",
)

register_provider(bedrock)

```
