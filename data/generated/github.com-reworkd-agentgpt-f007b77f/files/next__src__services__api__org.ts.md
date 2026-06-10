# 文件：next/src/services/api/org.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { z } from "zod";

import { get } from "../fetch-utils";

const OrganizationUsersSchema = z.object({
  id: z.string(),
  name: z.string(),
  users: z.array(
    z.object({
      id: z.string(),
      role: z.string(),
      user: z.object({
        id: z.string(),
        name: z.string(),
        email: z.string(),
      }),
    })
  ),
});

export class OrganizationApi {
  readonly accessToken?: string;

  constructor(accessToken?: string) {
    this.accessToken = accessToken;
  }

  async get(name: string) {
    return await get(`/api/auth/organization/${name}`, OrganizationUsersSchema, this.accessToken);
  }
}

```
