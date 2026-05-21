# 文件：src/server/routers/lambda/image/utils.ts

## 文件职责
这个文件位于 `src/server/routers/lambda/image`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
export function validateNoUrlsInConfig(obj: any, path: string = ''): void {
```

## 主要对外内容
```text
export function validateNoUrlsInConfig(obj: any, path: string = ''): void {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
/**
 * Recursively validate that no full URLs are present in the config
 * This is a defensive check to ensure only keys are stored in database
 */
export function validateNoUrlsInConfig(obj: any, path: string = ''): void {
  if (typeof obj === 'string') {
    if (obj.startsWith('http://') || obj.startsWith('https://')) {
      throw new Error(
        `Invalid configuration: Found full URL instead of key at ${path || 'root'}. ` +
          `URL: "${obj.slice(0, 100)}${obj.length > 100 ? '...' : ''}". ` +
          `All URLs must be converted to storage keys before database insertion.`,
      );
    }
  } else if (Array.isArray(obj)) {
    obj.forEach((item, index) => {
      validateNoUrlsInConfig(item, `${path}[${index}]`);
    });
  } else if (obj && typeof obj === 'object') {
    Object.entries(obj).forEach(([key, value]) => {
      const currentPath = path ? `${path}.${key}` : key;
      validateNoUrlsInConfig(value, currentPath);
    });
  }
}

```
