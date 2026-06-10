# 文件：platform/reworkd_platform/services/security.py

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
from typing import Union

from cryptography.fernet import Fernet, InvalidToken

from reworkd_platform.settings import settings
from reworkd_platform.web.api.http_responses import forbidden


class EncryptionService:
    def __init__(self, secret: bytes):
        self.fernet = Fernet(secret)

    def encrypt(self, text: str) -> bytes:
        return self.fernet.encrypt(text.encode("utf-8"))

    def decrypt(self, encoded_bytes: Union[bytes, str]) -> str:
        try:
            return self.fernet.decrypt(encoded_bytes).decode("utf-8")
        except InvalidToken:
            raise forbidden()


encryption_service = EncryptionService(settings.secret_signing_key.encode())

```
