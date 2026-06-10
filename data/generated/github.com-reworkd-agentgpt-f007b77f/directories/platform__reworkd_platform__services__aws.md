# 子系统：platform/reworkd_platform/services/aws

## 解决什么问题

`platform/reworkd_platform/services/aws` 是平台后端对 AWS 能力的轻量封装层。当前目录只实现了 S3 相关能力，核心目标是把业务代码从 `boto3` 的原始调用细节中隔离出来，提供统一的对象存储接口：生成上传用 presigned POST、生成下载用 presigned URL、直接上传内存文件、下载单个对象、按前缀列出对象、按前缀批量下载以及按前缀批量删除。

从当前仓库片段看，这个子系统还不是一个完整的云服务编排层，而是一个窄口径的 S3 adapter。它不负责认证流程、配置加载、HTTP 路由或业务对象建模，只负责把 “bucket + object key” 翻译成 S3 SDK 调用。由于它位于 `services` 下，定位更接近基础设施服务封装，供上层 API、agent 任务、文件处理或未来的数据持久化流程复用。

## 相关目录和文件

`platform/reworkd_platform/services/aws/s3.py` 是主要实现文件，定义了 `PresignedPost` 和 `SimpleStorageService`。`platform/reworkd_platform/services/aws/__init__.py` 只是包初始化文件，当前没有额外导出逻辑。

相邻的 `platform/reworkd_platform/services` 目录还包含 `pinecone`、`tokenizer`、`security.py`、`anthropic.py`、`oauth_installers.py` 等服务封装，说明该层整体承担外部服务与基础能力接入职责。`platform/reworkd_platform/settings.py` 是应用配置入口，但当前 `s3.py` 没有从 `settings` 读取 bucket、region 或凭据，而是在构造 `SimpleStorageService` 时由调用方传入 bucket，并固定使用 `REGION = "us-east-1"`。

测试文件 `platform/reworkd_platform/tests/test_s3.py` 覆盖了 `create_presigned_upload_url` 的基本行为，通过 mock `boto3_client` 验证 `SimpleStorageService` 会把 AWS 返回的 presigned post 数据包装成 `PresignedPost` 兼容对象。

## 核心对象

`PresignedPost` 是一个 `pydantic.BaseModel`，包含 `url: str` 和 `fields: Dict[str, str]`。它对应 S3 `generate_presigned_post` 的返回结构，用来表达前端或其他客户端执行表单上传时需要提交的目标地址和字段集合。这里使用 Pydantic 的意义是给返回值提供结构约束，而不是直接暴露裸字典。

`SimpleStorageService` 是子系统的核心服务类。初始化时必须传入 `bucket`，如果为空会抛出 `ValueError("Bucket name must be provided")`。构造函数内部通过 `boto3_client("s3", region_name=REGION)` 创建 S3 客户端，并把 bucket 保存为实例字段。它的方法都围绕同一个 bucket 工作，因此一个实例通常代表一个具体 S3 bucket 的操作入口。

`REGION` 是模块级常量，当前固定为 `us-east-1`。这让实现简单，但也意味着多区域部署或按环境切换区域时需要修改代码或扩展配置。

## 运行流程

创建上传地址时，上层调用 `SimpleStorageService(bucket).create_presigned_upload_url(object_name)`。该方法调用 `generate_presigned_post`，传入 `Bucket` 和 `Key`，再把 SDK 返回结果解包进 `PresignedPost`。调用方拿到 `url` 和 `fields` 后，可以把它交给前端或其他客户端完成直传 S3。这个流程适合避免后端代理大文件上传。

创建下载地址时，上层调用 `create_presigned_download_url(object_name)`。服务内部调用 `generate_presigned_url("get_object", Params={...})`，返回一个字符串 URL。该 URL 可被调用方短期使用，用于下载指定对象。过期时间没有在代码中显式配置，因此使用 boto3 默认行为。

直接上传时，调用方传入 `io.BytesIO`，`upload_to_bucket` 会读取 `file.getvalue()` 并通过 `put_object` 写入 S3。这里捕获的是 `aiohttp.ClientError`，记录日志后重新抛出。根据当前片段推断，这可能是作者希望统一处理网络客户端异常；但 boto3 常见异常来源通常是 `botocore.exceptions.ClientError`，这一点修改时需要特别确认。

批量读取和删除都基于 S3 prefix。`list_keys(prefix)` 调用 `list_objects_v2`，如果返回中没有 `Contents` 就返回空列表，否则提取每个对象的 `Key`。`download_folder(prefix, path)` 会遍历这些 key，把每个对象下载到本地目录 `path` 下，文件名取 key 最后一段。`delete_folder(prefix)` 会把所有 key 组装成 `delete_objects` 的 `Objects` 列表并提交删除。

## 上下游依赖

上游调用方当前在扫描片段中没有发现生产代码直接引用 `SimpleStorageService`，只有 `platform/reworkd_platform/tests/test_s3.py` 直接导入测试。因此，根据当前片段推断，这个模块可能是预留能力、历史功能残留，或由仓库外部/未来代码路径调用。判断依据是 `rg` 搜索只命中了测试导入和测试中的 mock 路径。

下游依赖主要是 `boto3` 的 S3 client、`pydantic.BaseModel`、`loguru.logger`、`io.BytesIO` 和本地文件系统路径操作。AWS 凭据没有在该模块中显式传入，默认依赖 boto3 的标准凭据解析链，例如环境变量、共享凭据文件、实例角色或容器角色。bucket 名称由构造参数提供，不走全局 `settings`。

它与 `settings.py` 的关系较弱。`settings.py` 管理 OpenAI、Pinecone、数据库、Kafka、Pusher、Sentry 等配置，但没有看到 S3 bucket 或 AWS region 字段。若未来把该服务接入正式业务，通常需要在配置层补充 bucket、region、可选 endpoint 等字段，再由依赖注入或 service provider 创建 `SimpleStorageService`。

## 修改时最容易踩的坑

第一，异常类型可能不准确。`upload_to_bucket` 捕获的是 `aiohttp.ClientError`，但 `boto3` 的 S3 操作通常不会抛这个类型。若要增强错误处理，应确认实际异常来源，避免日志分支永远不生效。

第二，`delete_folder` 在 key 为空时仍会调用 `delete_objects`，传入 `Delete={"Objects": []}`。S3 对空删除请求的行为需要确认，稳妥做法通常是空列表直接返回。

第三，`list_objects_v2` 默认最多返回一页结果。当前 `list_keys` 没有处理 pagination，因此 prefix 下对象超过单页限制时会漏数据。任何把它用于真实“文件夹”同步或清理的功能，都要先补分页。

第四，`download_folder` 只保留 key 的最后一段文件名。如果不同子目录下存在同名对象，会在本地路径中互相覆盖。它也不会创建目标目录，调用方必须确保 `path` 已存在。

第五，region 固定为 `us-east-1`。如果 bucket 在其他区域，某些操作可能出现重定向、签名问题或延迟问题。将 region 配置化时要注意测试中 mock 的 `boto3_client` 断言也可能需要调整。

第六，`PresignedPost` 的 `fields` 类型是 `Dict[str, str]`。AWS 返回字段通常是字符串，但如果未来加入复杂策略字段或 SDK 返回值类型变化，模型校验可能变成隐性失败点。

## 推荐阅读顺序

1. 先读 `platform/reworkd_platform/services/aws/s3.py`，理解这个目录的全部公开能力和 `SimpleStorageService` 的方法边界。
2. 再读 `platform/reworkd_platform/tests/test_s3.py`，确认现有测试如何 mock `boto3_client`，以及当前唯一被验证的行为是什么。
3. 接着浏览 `platform/reworkd_platform/services` 下其他服务封装，例如 `platform/reworkd_platform/services/pinecone`、`platform/reworkd_platform/services/tokenizer`，对比项目中外部服务 adapter 的组织方式。
4. 最后查看 `platform/reworkd_platform/settings.py`，理解全局配置模式，并评估如果要正式启用 S3，应该把 bucket、region 和凭据策略接入到哪里。
