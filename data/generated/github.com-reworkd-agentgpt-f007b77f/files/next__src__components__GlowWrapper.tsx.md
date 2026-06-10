# 文件：next/src/components/GlowWrapper.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { ReactNode } from "react";
import clsx from "clsx";

type GlowWrapperProps = {
  children: ReactNode;
  className?: string;
};

const GlowWrapper = ({ children, className }: GlowWrapperProps) => {
  return (
    <div className="relative inline-flex items-center justify-center">
      <div
        className={clsx(
          className || "opacity-50",
          "absolute -inset-1 rounded-full bg-gradient-to-tr from-[#A02BFE] to-[#1152FA] blur-lg transition-all duration-1000"
        )}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
};

export default GlowWrapper;

```
