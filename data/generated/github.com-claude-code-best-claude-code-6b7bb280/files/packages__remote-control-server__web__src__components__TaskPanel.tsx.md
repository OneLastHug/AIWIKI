# 文件：packages/remote-control-server/web/src/components/TaskPanel.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';

interface TaskPanelProps {
  onClose: () => void;
}

export function TaskPanel({ onClose }: TaskPanelProps) {
  return (
    <Dialog
      open={true}
      onOpenChange={o => {
        if (!o) onClose();
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="fixed inset-y-0 right-0 top-auto left-auto translate-x-0 translate-y-0 w-full sm:w-80 h-full max-w-none max-h-none rounded-none border-l border-border bg-surface-1 p-4 sm:max-w-sm"
      >
        <DialogHeader>
          <DialogTitle className="font-display font-semibold text-text-primary">Tasks</DialogTitle>
        </DialogHeader>
        <div className="text-sm text-text-muted">No active tasks</div>
      </DialogContent>
    </Dialog>
  );
}

```
