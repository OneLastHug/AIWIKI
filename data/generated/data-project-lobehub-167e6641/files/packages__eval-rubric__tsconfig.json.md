# 文件：packages/eval-rubric/tsconfig.json

## 文件职责
这个文件位于 `packages/eval-rubric`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
未在节选中发现明显 import/export 语句。
```

## 主要对外内容
```text
未在节选中发现明显导出的类型、函数或组件。
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
{
  "compilerOptions": {
    "module": "CommonJS",
    "target": "ESNext",
    "lib": ["dom", "dom.iterable", "esnext"],
    "sourceMap": true,
    "skipDefaultLibCheck": true,
    "allowSyntheticDefaultImports": true,
    "moduleResolution": "node",
    "forceConsistentCasingInFileNames": true,
    "noImplicitReturns": true,
    "noUnusedLocals": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "strict": true,
    "types": ["vitest/globals"]
  }
}

```
