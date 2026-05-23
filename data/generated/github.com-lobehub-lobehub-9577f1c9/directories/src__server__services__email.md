# 目录：src/server/services/email

## 它负责什么

这个目录是后端邮件发送能力的统一入口，目标是把“怎么发邮件”从业务代码里抽出来，封装成一个可替换 provider 的服务层。根据当前片段推断，它主要承担三件事：一是提供 `EmailService` 这层稳定的调用接口，二是按环境或显式参数选择具体实现，三是把 SMTP/Resend 这类差异收敛到 `impls/` 下面。

从职责划分看，这里不是“写邮件内容”的地方，而是“发送与适配”的地方。真正的业务场景，比如重置密码、邮箱验证、通知邮件，通常会在别的模块里构造 `EmailPayload`，再交给这里完成投递。

## 直接子目录地图

这个目录本身不大，直接子项清晰，主要是“门面 + 实现 + 测试 + 文档”四类：

- `src/server/services/email/index.ts`：服务门面，外部最常引用的入口。
- `src/server/services/email/impls/`：具体实现工厂和 provider 适配层。
- `src/server/services/email/index.test.ts`：`EmailService` 的行为测试。
- `src/server/services/email/README.md`：使用说明、环境变量、扩展指南。

`impls/` 下面又分成几个小块：

- `src/server/services/email/impls/index.ts`：实现类型枚举与工厂函数。
- `src/server/services/email/impls/type.ts`：`EmailPayload`、`EmailResponse`、`EmailServiceImpl` 等共享类型。
- `src/server/services/email/impls/nodemailer/`：SMTP 方案的实现。
- `src/server/services/email/impls/resend/`：Resend 方案的实现。
- `src/server/services/email/impls/index.test.ts`：工厂分发逻辑测试。

如果只看目录形态，这里已经能看出一个很典型的 provider pattern：上层稳定接口，下面挂多个实现。

## 关键入口

最重要的入口是 `src/server/services/email/index.ts`。它定义了 `EmailService` 类，构造时会先解析 provider，再调用 `createEmailServiceImpl(...)` 生成具体实现，之后 `sendMail()` 只是简单转发，`verify()` 则做能力探测，有 `verify` 方法就调用，没有就默认通过。

第二个关键入口是 `src/server/services/email/impls/index.ts`。它定义了 `EmailImplType`，目前可见的值是 `nodemailer` 和 `resend`，并且把“类型字符串 -> 具体类”的映射集中在这里。这个文件是新增 provider 时最先要改的地方。

第三个入口是 `src/envs/email.ts`。这里把邮件相关环境变量集中成 `emailEnv`，包括 `EMAIL_SERVICE_PROVIDER`、`RESEND_API_KEY`、`RESEND_FROM`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_SECURE`、`SMTP_USER`、`SMTP_PASS` 等。也就是说，provider 选择和连接参数都从这里来。

## 主流程位置

主流程可以概括成“配置读取 -> provider 选择 -> 实现初始化 -> sendMail 转发 -> 具体 provider 发送”。

根据当前片段推断，核心链路是这样的：

1. 外部代码创建 `new EmailService()`。
2. `EmailService` 在构造函数里读取 `emailEnv.EMAIL_SERVICE_PROVIDER`，如果调用方没显式传 `implType`，就用环境变量；如果环境变量也没有，就回退到 `EmailImplType.Nodemailer`。
3. `createEmailServiceImpl()` 根据类型实例化 `NodemailerImpl` 或 `ResendImpl`。
4. 业务层调用 `emailService.sendMail(payload)`，这里不会再做复杂逻辑，而是直接转发到具体实现。
5. 具体实现内部再处理各自的配置校验、默认 `from` 地址、参数整理、底层 SDK 调用，以及错误转换。

其中，Nodemailer 这一支通常走 SMTP 配置，Resend 这一支则依赖 `RESEND_API_KEY` 和 `RESEND_FROM`。两条实现都属于“适配层”，不是业务层。

## 推荐阅读顺序

建议按这个顺序看，会比较顺：

1. 先看 `src/server/services/email/index.ts`，建立服务门面和调用方式的整体印象。
2. 再看 `src/server/services/email/impls/index.ts`，理解 provider 枚举和工厂分发。
3. 接着看 `src/envs/email.ts`，把环境变量和默认值对上。
4. 然后看 `src/server/services/email/impls/type.ts`，明确 payload 和 response 的形状。
5. 再分别看 `src/server/services/email/impls/nodemailer/index.ts`、`src/server/services/email/impls/resend/index.ts`，理解两种 provider 的细节。
6. 最后看 `index.test.ts` 和 `impls/index.test.ts`，确认默认实现、回退逻辑和测试覆盖点。

如果你只想先抓主线，看前 3 个文件就够了。

## 常见误区

最常见的误区是把这里当成“邮件业务编排层”。实际上它更像基础设施适配层，业务邮件模板和触发时机通常不在这里。

第二个误区是忽略 provider 选择顺序。根据当前片段推断，优先级是“构造参数 > 环境变量 > Nodemailer 默认值”，如果只改环境变量不改代码，最终走哪条实现要看 `EmailService` 构造逻辑。

第三个误区是只看 `EmailService.sendMail()`，却没看 `impls/`。真正的差异都藏在具体实现里，比如 SMTP 认证、默认发件人、错误信息、预览链接，这些都不是门面层负责的。

第四个误区是新增 provider 时只加一个类，不改工厂和类型。这个目录的扩展点很集中，通常至少要同步改 `impls/index.ts`、实现目录、对应测试，必要时还要补环境变量定义和 README 说明。
