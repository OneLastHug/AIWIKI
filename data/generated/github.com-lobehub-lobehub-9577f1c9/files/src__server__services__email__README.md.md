# 文件：src/server/services/email/README.md

## 一句话定位

`src/server/services/email/README.md` 是服务端邮件服务的使用与扩展说明文档，帮助开发者理解 `EmailService` 如何屏蔽底层邮件供应商差异，并通过统一的 `sendMail`、`verify` 能力支撑注册、登录、找回密码等认证邮件场景。

## 它暴露/定义了什么

这个 README 本身不参与运行时编译，也不导出代码；它定义的是邮件服务模块的开发约定和使用方式。文档围绕 `src/server/services/email/index.ts` 暴露的 `EmailService` 展开，说明可传入的 `EmailPayload` 字段，包括 `from`、`to`、`subject`、`text`、`html`、`replyTo`、`attachments`，以及返回的 `EmailResponse`，主要是 `messageId` 和测试场景下可能出现的 `previewUrl`。

它还说明了两类邮件实现：默认的 `NodemailerImpl`，以及可选的 `ResendImpl`。供应商选择通过构造参数 `EmailImplType` 或环境变量 `EMAIL_SERVICE_PROVIDER` 完成。README 中还记录了 SMTP、Resend 所需的环境变量，例如 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`SMTP_FROM`、`RESEND_API_KEY`、`RESEND_FROM`。

## 谁调用它

README 文件本身没有运行时调用者，它的直接读者是维护邮件服务、认证流程和部署配置的开发者。

根据当前片段推断，README 所描述的 `EmailService` 主要被 `src/libs/better-auth/define-config.ts` 调用。搜索结果显示该文件多处 `new EmailService()`，随后调用 `sendMail`，用于 Better Auth 的邮件验证、密码重置、magic link 登录、欢迎邮件或相关认证邮件发送流程。对应测试在 `src/libs/better-auth/define-config.test.ts` 中 mock 了 `EmailService`。

模块自身的行为由 `src/server/services/email/index.test.ts`、`src/server/services/email/impls/index.test.ts` 覆盖，重点验证默认实现选择、指定实现选择、`sendMail` 转发、`verify` 兼容实现差异等。

## 它调用谁

README 描述的调用链核心是 `EmailService` 调用 `createEmailServiceImpl`，再由工厂按类型创建具体实现。

`src/server/services/email/index.ts` 会读取 `emailEnv.EMAIL_SERVICE_PROVIDER`，在没有显式传入实现类型时使用环境变量决定供应商，最终默认回退到 `EmailImplType.Nodemailer`。`createEmailServiceImpl` 位于 `src/server/services/email/impls/index.ts`，会创建 `NodemailerImpl` 或 `ResendImpl`。

`NodemailerImpl` 调用 `nodemailer.createTransport` 创建 SMTP transporter，发送时调用 `this.transporter.sendMail`，并通过 `nodemailer.getTestMessageUrl` 获取测试邮件预览地址。`ResendImpl` 调用 `new Resend(emailEnv.RESEND_API_KEY)` 创建客户端，发送时调用 `this.client.emails.send`。两个实现都会使用 `debug` 打日志，并在失败时抛出 `TRPCError` 或普通配置错误。

## 核心流程

第一步是实例化 `EmailService`。如果调用方传入 `EmailImplType`，就使用该类型；否则在服务端环境读取 `EMAIL_SERVICE_PROVIDER`；如果仍为空，则默认使用 `nodemailer`。代码中特意判断 `typeof window === 'undefined'`，避免在浏览器化测试环境中访问服务端环境变量。

第二步是工厂创建具体实现。`nodemailer` 实现要求 `SMTP_USER` 和 `SMTP_PASS` 存在，并组装 `host`、`port`、`secure`、`auth` 配置；`resend` 实现要求 `RESEND_API_KEY` 存在。

第三步是调用 `sendMail(payload)`。`EmailService` 不加工 payload，只转发给当前实现。`NodemailerImpl` 会补齐默认 `from`，优先级是 `payload.from`、`SMTP_FROM`、`SMTP_USER`，然后把附件、正文、收件人、回复地址等传给 SMTP transporter。`ResendImpl` 会补齐 `from`，并校验必须有 `html` 或 `text`，同时把 Buffer 类型附件内容转成 base64，以适配 Resend API。

第四步是错误处理。SMTP 发送失败、Resend 返回错误或缺少 message id，都会转成 `SERVICE_UNAVAILABLE`；Resend 缺少发件人或正文时抛 `PRECONDITION_FAILED`。配置缺失在构造阶段就会失败。

## 关键函数的高层作用

`EmailService.constructor` 是供应商选择入口，负责把显式参数、环境变量和默认值收敛成一个 `EmailImplType`，再创建实现实例。

`EmailService.sendMail` 是统一门面方法，调用方不需要知道底层是 SMTP 还是 Resend，只需要提交 `EmailPayload`。

`EmailService.verify` 是可选能力适配层。如果底层实现有 `verify` 方法，就调用它；没有则返回 `true`。这让 Resend 这类没有连接验证语义的实现也能符合统一服务接口。

`createEmailServiceImpl` 是供应商工厂，集中维护 `EmailImplType` 到实现类的映射。新增供应商时，README 建议同步扩展 enum 和 switch 分支。

`NodemailerImpl.sendMail` 负责 SMTP 邮件发送和测试预览 URL 提取，是当前默认路径。`ResendImpl.sendMail` 负责 Resend API 发送、参数校验和附件格式转换。

## 修改风险

最大风险是认证链路受影响。`EmailService` 被 Better Auth 的关键邮件流程使用，修改 payload 字段、默认发件人规则、异常类型或供应商选择逻辑，可能导致密码重置、邮箱验证、magic link 登录等功能不可用。

第二个风险是环境变量兼容性。`NodemailerImpl` 当前强依赖 `SMTP_USER`、`SMTP_PASS`，并把 `SMTP_FROM` 作为可选默认发件人；`ResendImpl` 依赖 `RESEND_API_KEY` 和可选 `RESEND_FROM`。如果 README 与实现不一致，部署人员可能按错误变量配置，最终在运行时才暴露问题。

第三个风险是供应商差异被门面掩盖。`Nodemailer` 支持测试预览 URL，`Resend` 不返回 `previewUrl`；`verify` 也只对有该方法的实现真实生效。调用方如果把这些能力当作所有供应商都支持，会产生隐性兼容问题。

第四个风险是错误语义变化。当前实现用 `TRPCError` 的 `SERVICE_UNAVAILABLE`、`PRECONDITION_FAILED` 区分外部服务失败和前置配置/参数问题。随意改 message 或 code，可能影响上层错误处理、测试断言和用户侧提示。
