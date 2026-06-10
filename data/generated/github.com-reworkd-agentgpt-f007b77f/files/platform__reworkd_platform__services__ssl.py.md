# 文件：platform/reworkd_platform/services/ssl.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
from ssl import SSLContext, create_default_context
from typing import List, Optional

from reworkd_platform.settings import Settings

MACOS_CERT_PATH = "/etc/ssl/cert.pem"
DOCKER_CERT_PATH = "/etc/ssl/certs/ca-certificates.crt"


def get_ssl_context(
    settings: Settings, paths: Optional[List[str]] = None
) -> SSLContext:
    if settings.db_ca_path:
        return create_default_context(cafile=settings.db_ca_path)

    for path in paths or [MACOS_CERT_PATH, DOCKER_CERT_PATH]:
        try:
            return create_default_context(cafile=path)
        except FileNotFoundError:
            continue

    raise ValueError(
        "No CA certificates found for your OS. To fix this, please run change "
        "db_ca_path in your settings.py to point to a valid CA certificate file."
    )

```
