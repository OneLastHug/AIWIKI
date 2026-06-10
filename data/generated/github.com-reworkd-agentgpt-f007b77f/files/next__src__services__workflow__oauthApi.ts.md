# 文件：next/src/services/workflow/oauthApi.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { Session } from "next-auth";
import { z } from "zod";

import { env } from "../../env/client.mjs";
import { get } from "../fetch-utils";

export default class OauthApi {
  readonly accessToken?: string;
  readonly organizationId?: string;

  constructor(accessToken?: string, organizationId?: string) {
    this.accessToken = accessToken;
    this.organizationId = organizationId;
  }

  static fromSession(session: Session | null) {
    return new OauthApi(session?.accessToken, session?.user?.organizations[0]?.id);
  }

  async install(provider: string, redirectUri?: string) {
    const url = `${env.NEXT_PUBLIC_VERCEL_URL}${redirectUri || ""}`;

    return await get(
      `/api/auth/${provider}?redirect=${encodeURIComponent(url)}`,
      z.string().url(),
      this.accessToken,
      this.organizationId
    );
  }

  async uninstall(provider: string) {
    return await get(
      `/api/auth/${provider}/uninstall`,
      z.object({
        success: z.boolean(),
      }),
      this.accessToken,
      this.organizationId
    );
  }
  // TODO: decouple this
  async get_info(provider: string) {
    return await get(
      `/api/auth/${provider}/info`,
      z
        .object({
          name: z.string(),
          id: z.string(),
        })
        .array(),
      this.accessToken,
      this.organizationId
    );
  }

  async get_info_sid() {
    return await get(
      `/api/auth/sid/info`,
      z.object({
        connected: z.boolean(),
      }),
      this.accessToken,
      this.organizationId
    );
  }
}

```
