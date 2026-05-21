# 文件：src/server/services/webhookUser/index.ts

## 文件职责
这个文件位于 `src/server/services/webhookUser`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type LobeChatDatabase } from '@lobechat/database';
import { and, eq } from 'drizzle-orm';
import { NextResponse } from 'next/server';
import { UserModel } from '@/database/models/user';
import { type UserItem } from '@/database/schemas';
import { account, nextauthAccounts, session, users } from '@/database/schemas';
export class WebhookUserService {
```

## 主要对外内容
```text
export class WebhookUserService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type LobeChatDatabase } from '@lobechat/database';
import { and, eq } from 'drizzle-orm';
import { NextResponse } from 'next/server';

import { UserModel } from '@/database/models/user';
import { type UserItem } from '@/database/schemas';
import { account, nextauthAccounts, session, users } from '@/database/schemas';

export class WebhookUserService {
  private db: LobeChatDatabase;

  constructor(db: LobeChatDatabase) {
    this.db = db;
  }

  /**
   * Find user by provider account info.
   * First checks Better Auth accounts table, then falls back to NextAuth accounts table
   * for users who performed simple migration (without migrating accounts data).
   */
  private getUserByAccount = async ({
    providerId,
    accountId,
  }: {
    accountId: string;
    providerId: string;
  }) => {
    // First, try Better Auth accounts table
    const betterAuthAccount = await this.db.query.account.findFirst({
      where: and(eq(account.providerId, providerId), eq(account.accountId, accountId)),
    });

    if (betterAuthAccount) {
      return this.db.query.users.findFirst({
        where: eq(users.id, betterAuthAccount.userId),
      });
    }

    // Fallback to NextAuth accounts table for simple migration users
    const nextAuthAccount = await this.db
      .select({ users })
      .from(nextauthAccounts)
      .innerJoin(users, eq(nextauthAccounts.userId, users.id))
      .where(
        and(
          eq(nextauthAccounts.provider, providerId),
          eq(nextauthAccounts.providerAccountId, accountId),
        ),
      )
      .then((res) => res[0]);

    return nextAuthAccount?.users ?? null;
  };

  /**
   * Safely update user data from webhook
   */
  safeUpdateUser = async (
    { accountId, providerId }: { accountId: string; providerId: string },
    data: Partial<UserItem>,
  ) => {
    console.info(`updating user "${JSON.stringify({ accountId, providerId })}" due to webhook`);

    const user = await this.getUserByAccount({ accountId, providerId });

    if (user?.id) {
      const userModel = new UserModel(this.db, user.id);
      await userModel.updateUser({
        avatar: data?.avatar,
        email: data?.email,
        fullName: data?.fullName,
      });
    } else {
      console.warn(
        `[${providerId}]: Webhook user "${JSON.stringify({ accountId, providerId })}" update for "${JSON.stringify(data)}", but no user was found.`,
      );
    }

    return NextResponse.json({ message: 'user updated', success: true }, { status: 200 });
  };

  /**
   * Safely sign out user (delete all sessions)
   */
  safeSignOutUser = async ({
    accountId,
    providerId,
  }: {
    accountId: string;
    providerId: string;
  }) => {
    console.info(`Signing out user "${JSON.stringify({ accountId, providerId })}"`);

    const user = await this.getUserByAccount({ accountId, providerId });

    if (user?.id) {
      await this.db.delete(session).where(eq(session.userId, user.id));
    } else {
      console.warn(
        `[${providerId}]: Webhook user "${JSON.stringify({ accountId, providerId })}" signout, but no user was found.`,
      );
    }

    return NextResponse.json({ message: 'user signed out', success: true }, { status: 200 });
  };
}

```
