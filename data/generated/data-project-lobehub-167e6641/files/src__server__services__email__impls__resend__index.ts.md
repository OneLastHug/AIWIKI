# 文件：src/server/services/email/impls/resend/index.ts

## 文件职责
这个文件位于 `src/server/services/email/impls/resend`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import { type CreateEmailOptions } from 'resend';
import { Resend } from 'resend';
import { emailEnv } from '@/envs/email';
import { type EmailPayload, type EmailResponse, type EmailServiceImpl } from '../type';
export class ResendImpl implements EmailServiceImpl {
```

## 主要对外内容
```text
const log = debug('lobe-email:Resend');
export class ResendImpl implements EmailServiceImpl {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { TRPCError } from '@trpc/server';
import debug from 'debug';
import { type CreateEmailOptions } from 'resend';
import { Resend } from 'resend';

import { emailEnv } from '@/envs/email';

import { type EmailPayload, type EmailResponse, type EmailServiceImpl } from '../type';

const log = debug('lobe-email:Resend');

/**
 * Resend implementation of the email service
 */
export class ResendImpl implements EmailServiceImpl {
  private client: Resend;

  constructor() {
    if (!emailEnv.RESEND_API_KEY) {
      throw new Error(
        'RESEND_API_KEY environment variable is required to use Resend email service. Please configure it in your .env file.',
      );
    }

    this.client = new Resend(emailEnv.RESEND_API_KEY);
    log('Initialized Resend client');
  }

  async sendMail(payload: EmailPayload): Promise<EmailResponse> {
    // Note: Use || to handle empty string from Dockerfile defaults
    const from = payload.from || emailEnv.RESEND_FROM;
    const html = payload.html;
    const text = payload.text;

    if (!from) {
      throw new TRPCError({
        code: 'PRECONDITION_FAILED',
        message:
          'Missing sender address. Provide payload.from or RESEND_FROM environment variable.',
      });
    }

    if (!html && !text) {
      throw new TRPCError({
        code: 'PRECONDITION_FAILED',
        message: 'Resend requires either html or text content in the email payload.',
      });
    }

    const attachments = payload.attachments?.map((attachment) => {
      if (attachment.content instanceof Buffer) {
        return {
          ...attachment,
          content: attachment.content.toString('base64'),
        };
      }

      return attachment;
    });

    try {
      log('Sending email via Resend: %o', {
        from,
        subject: payload.subject,
        to: payload.to,
      });

      const emailOptions: CreateEmailOptions = html
        ? {
            attachments,
            from,
            html,
            replyTo: payload.replyTo,
            subject: payload.subject,
            text,
            to: payload.to,
          }
        : {
            attachments,
            from,
            replyTo: payload.replyTo,
            subject: payload.subject,
            text: text!,
            to: payload.to,
          };

      const { data, error } = await this.client.emails.send(emailOptions);

      if (error) {
        log.extend('error')('Failed to send email via Resend: %o', error);
        throw new TRPCError({
          cause: error,
          code: 'SERVICE_UNAVAILABLE',
          message: `Failed to send email via Resend: ${error.message}`,
        });
      }

      if (!data?.id) {
        log.extend('error')('Resend sendMail returned no message id: %o', data);
        throw new TRPCError({
          code: 'SERVICE_UNAVAILABLE',
          message: 'Failed to send email via Resend: missing message id',
        });
      }

      return {
        messageId: data.id,
      };
    } catch (error) {
      if (error instanceof TRPCError) {
        throw error;
      }

      log.extend('error')('Unexpected Resend sendMail error: %o', error);
      throw new TRPCError({
        cause: error,
        code: 'SERVICE_UNAVAILABLE',
        message: `Failed to send email via Resend: ${(error as Error).message}`,
      });
    }
  }
}

```
