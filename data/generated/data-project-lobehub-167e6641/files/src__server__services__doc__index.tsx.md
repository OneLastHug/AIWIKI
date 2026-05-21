# 文件：src/server/services/doc/index.tsx

## 文件职责
这个文件位于 `src/server/services/doc`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { existsSync, readdirSync,readFileSync } from 'node:fs';
import { join } from 'node:path';
import matter from 'gray-matter';
export class DocService {
```

## 主要对外内容
```text
const LAST_MODIFIED = new Date().toISOString();
export class DocService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { existsSync, readdirSync,readFileSync } from 'node:fs';
import { join } from 'node:path';

import matter from 'gray-matter';

const LAST_MODIFIED = new Date().toISOString();

export class DocService {
  async getDocByPath(locale: string, path: string) {
    const extra = locale === 'zh-CN' ? '.zh-CN.mdx' : '.mdx';

    const localPath = join(process.cwd(), 'docs/', path) + extra;

    const isLocalePathExist = existsSync(localPath);

    if (!isLocalePathExist) return;

    const text: string = readFileSync(localPath, 'utf8');

    if (!text) return;

    const { data, content } = matter(text);

    const regex = /^#\s(.+)/;
    const match = regex.exec(content);
    const matches = content.split(regex);
    const description = matches[1] ? matches[1].trim() : '';
    return {
      date: data?.date ? new Date(data.date) : new Date(LAST_MODIFIED),
      description: description.replaceAll('\n', '').replaceAll('  ', ' ').slice(0, 160),
      tags: [],
      title: match ? match[1] : '',
      ...data,
      content,
    };
  }
}

// Strangely, this `readdirSync` call is needed to read md files after Vercel deployment
// Otherwise, mdx files cannot be found properly
readdirSync(join(process.cwd(), 'docs'));

```
