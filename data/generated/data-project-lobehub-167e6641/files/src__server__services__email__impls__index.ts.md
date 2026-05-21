# 文件：src/server/services/email/impls/index.ts

## 文件职责
这个文件位于 `src/server/services/email/impls`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { NodemailerImpl } from './nodemailer';
import { ResendImpl } from './resend';
import { type EmailServiceImpl } from './type';
export enum EmailImplType {
export const createEmailServiceImpl = (
export type { EmailServiceImpl } from './type';
export type { EmailPayload, EmailResponse } from './type';
```

## 主要对外内容
```text
export const createEmailServiceImpl = (
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { NodemailerImpl } from './nodemailer';
import { ResendImpl } from './resend';
import { type EmailServiceImpl } from './type';

/**
 * Available email service implementations
 */
export enum EmailImplType {
  Nodemailer = 'nodemailer',
  Resend = 'resend',
  // Future providers can be added here:
  // SendGrid = 'sendgrid',
}

/**
 * Create an email service implementation instance
 */
export const createEmailServiceImpl = (
  type: EmailImplType = EmailImplType.Nodemailer,
): EmailServiceImpl => {
  switch (type) {
    case EmailImplType.Nodemailer: {
      return new NodemailerImpl();
    }
    case EmailImplType.Resend: {
      return new ResendImpl();
    }

    default: {
      return new NodemailerImpl();
    }
  }
};

export type { EmailServiceImpl } from './type';
export type { EmailPayload, EmailResponse } from './type';

```
