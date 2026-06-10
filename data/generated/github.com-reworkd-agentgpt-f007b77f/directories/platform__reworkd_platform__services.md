# 子系统：platform/reworkd_platform/services

## 解决什么问题

`platform/reworkd_platform/services` 是后端平台的“基础服务适配层”。它不直接承载某个业务 API 的完整流程，而是把业务层会反复用到的外部能力、平台级工具和横切能力封装成稳定对象，供 `web/api`、`db`、测试代码等上层模块调用。

从当前片段看，这个目录主要解决五类问题：一是安全相关的 token 加密与解密；二是 OAuth 第三方集成安装流程；三是 OpenAI/tiktoken 语境下的 token 计数和模型上下文预算控制；四是 S3 对象存储上传、下载、预签名 URL；五是 Pinecone、SSL、Anthropic 等外部服务的初始化或适配。换句话说，它是业务代码和外部基础设施之间的一层薄封装，目标是让上层只关心“我要加密”“我要生成上传地址”“我要计算可用 completion token”，而不是到处散落 SDK 细节、配置读取和异常处理。

## 相关目录和文件

`platform/reworkd_platform/services/security.py` 定义 `EncryptionService` 和模块级单例 `encryption_service`，使用 `settings.secret_signing_key` 初始化 `cryptography.fernet.Fernet`，为 OAuth token 等敏感数据提供加密存储能力。

`platform/reworkd_platform/services/oauth_installers.py` 定义 OAuth 安装器抽象类 `OAuthInstaller` 和当前实现 `SIDInstaller`，并通过 `installer_factory` 与 FastAPI 的依赖注入结合。它依赖 `OAuthCrud` 访问数据库中的 OAuth 安装记录。

`platform/reworkd_platform/services/tokenizer/token_service.py` 定义 `TokenService`，基于 `tiktoken` 做文本 token 化、反 token 化、计数，并根据 `LLM_MODEL_MAX_TOKENS` 计算模型剩余 completion 空间。`tokenizer/dependencies.py`、`tokenizer/lifetime.py` 根据命名和引用关系推断负责将该服务接入应用生命周期和依赖注入。

`platform/reworkd_platform/services/aws/s3.py` 封装 S3 操作，核心类是 `SimpleStorageService`，包括生成上传/下载预签名 URL、直接上传、下载文件夹、列举 key、删除文件夹等。

`platform/reworkd_platform/services/pinecone/` 根据目录结构包含 Pinecone 客户端或生命周期管理代码；`platform/reworkd_platform/services/ssl.py` 被 `platform/reworkd_platform/db/utils.py` 引用，用于数据库连接或外部访问时的 SSL 上下文；`platform/reworkd_platform/services/anthropic.py` 则根据文件名推断是 Anthropic 相关服务适配。

## 核心对象

`EncryptionService` 是安全能力的核心对象。它只暴露 `encrypt(text: str) -> bytes` 和 `decrypt(encoded_bytes) -> str` 两个方法。解密失败时不会返回底层异常，而是抛出 `forbidden()`，这说明它被设计为面向 Web 请求场景，非法 token 或错误密钥会被转成统一的 HTTP 禁止响应。

`OAuthInstaller` 是 OAuth 集成的抽象协议，要求实现 `install`、`install_callback`、`uninstall`。它还提供 `store_access_token`、`store_refresh_token` 两个静态方法，统一把明文 token 加密后写入 `OauthCredentials`。`SIDInstaller` 是具体 provider 实现，负责生成授权跳转地址、处理 callback code 换 token、保存 access token/refresh token 和过期时间，以及卸载时撤销 refresh token。

`TokenService` 是 LLM 调用前的预算工具。`get_completion_space(model, *prompts)` 会根据模型最大 token 数减去 prompt token 数，`calculate_max_tokens(model, *prompts)` 会直接收缩 `WrappedChatOpenAI.max_tokens`，并保证最小值为 1。这个对象影响 agent 执行时给模型分配多少输出空间。

`SimpleStorageService` 是 S3 包装器。它在构造时要求必须传入 bucket，并固定使用 `us-east-1`。返回结构 `PresignedPost` 是一个 Pydantic 模型，包含 `url` 和 `fields`，便于 API 层把 S3 直传参数返回给前端。

## 运行流程

典型 OAuth 安装流程是：`web/api/auth/views.py` 通过 `installer_factory` 注入具体 `OAuthInstaller`；factory 根据路径参数 `provider` 从 `integrations` 字典选择实现，目前可见的是 `sid`；`install` 先用 `OAuthCrud` 查询用户是否已有安装记录，没有则创建，随后组装授权参数并返回第三方授权地址。callback 阶段，`install_callback` 根据 `state` 找到数据库中的安装记录，再用授权 `code` 请求第三方 token 端点，得到 access token、refresh token 和过期时间后加密保存。卸载时，`uninstall` 读取并解密 refresh token，删除本地凭据，再调用外部撤销接口。

典型 agent 调用流程是：`web/api/agent/agent_service/agent_service_provider.py` 或 `open_ai_agent_service.py` 通过 `get_token_service` 获得 `TokenService`；在构造或调用 `WrappedChatOpenAI` 前，把 prompt 传给 `calculate_max_tokens`；服务根据模型名查 `LLM_MODEL_MAX_TOKENS`，计算 prompt 已占空间，最后调整 `model.max_tokens`，避免请求超过模型上下文窗口。

典型对象存储流程是：上层创建 `SimpleStorageService(bucket)`；如果是前端直传，调用 `create_presigned_upload_url(object_name)` 返回 S3 presigned post；如果是服务端上传，传入 `io.BytesIO` 到 `upload_to_bucket`；下载和批量文件夹操作则通过 key prefix 间接完成。

## 上下游依赖

上游调用者主要在 `platform/reworkd_platform/web/api` 和 `platform/reworkd_platform/db`。例如认证 API 使用 `oauth_installers.py`，agent 服务使用 tokenizer，SID 搜索工具使用 `security.py` 解密凭据，数据库工具使用 `ssl.py`。测试位于 `platform/reworkd_platform/tests/test_token_service.py`、`test_oauth_installers.py`、`test_security.py`、`test_s3.py`，说明这些服务被视为可独立验证的边界对象。

下游依赖包括 `settings` 配置、`OAuthCrud` 数据访问、`OauthCredentials` 模型、`UserBase` schema、`cryptography.fernet`、`aiohttp`、`boto3`、`tiktoken`、`loguru`、`pydantic`，以及外部的 OAuth provider、S3、Pinecone、Anthropic 等服务。注意文档中不展开真实外部地址；源码里这些地址应被视为部署配置和安全审查点。

## 修改时最容易踩的坑

第一，`EncryptionService` 的密钥必须是 Fernet 可接受的格式。修改 `settings.secret_signing_key` 的生成方式会直接影响历史 token 是否还能解密，进而影响已安装的 OAuth 集成。

第二，`OAuthInstaller.store_access_token` 和 `store_refresh_token` 写入的是加密后的 bytes。数据库字段、序列化逻辑和测试 mock 如果假设是普通字符串，容易出现隐蔽兼容问题。

第三，`SIDInstaller.install` 入参有 `redirect_uri`，但当前实现组装授权参数时使用的是 `settings.sid_redirect_uri`。如果要支持动态 redirect URI，需要同时检查安装记录、callback 校验和 provider 配置，不能只改一个参数。

第四，`TokenService.calculate_max_tokens` 会原地修改传入的 `WrappedChatOpenAI` 对象。调用方如果复用同一个 model 实例，多轮 prompt 可能互相影响，需要确认生命周期是否符合预期。

第五，`SimpleStorageService.delete_folder` 在 prefix 没有对象时仍会调用 `delete_objects`，而它构造的 `Objects` 可能为空。不同 boto3/S3 mock 对空删除的行为可能不同，改动批量删除逻辑时要覆盖空目录场景。

第六，`SimpleStorageService` 当前是同步 boto3 客户端，文件里也标注了异步化 TODO。不要在不调整调用链和测试的情况下直接换成异步客户端，否则 API 层、后台任务和测试都会受影响。

## 推荐阅读顺序

先读 `platform/reworkd_platform/services/security.py`，理解本目录对敏感凭据的统一处理方式。然后读 `platform/reworkd_platform/services/oauth_installers.py`，它串起了配置、数据库、加密、外部 HTTP 请求和 FastAPI 依赖注入，是最能体现 services 层职责的文件。

接着读 `platform/reworkd_platform/services/tokenizer/token_service.py`，再顺着引用看 `platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py` 和 `platform/reworkd_platform/web/api/agent/agent_service/agent_service_provider.py`，理解 token 预算如何影响 agent 调用。

之后读 `platform/reworkd_platform/services/aws/s3.py` 和 `platform/reworkd_platform/tests/test_s3.py`，掌握对象存储边界。最后补看 `platform/reworkd_platform/services/pinecone/`、`platform/reworkd_platform/services/ssl.py`、`platform/reworkd_platform/services/anthropic.py`，再结合 `platform/reworkd_platform/web/lifetime.py` 和 `platform/reworkd_platform/db/utils.py` 理解这些外部资源如何在应用启动、数据库连接和业务工具中被接入。
