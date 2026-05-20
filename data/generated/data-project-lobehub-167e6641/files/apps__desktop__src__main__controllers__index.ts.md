# 文件：apps/desktop/src/main/controllers/index.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { DesktopHotkeyId } from '@lobechat/types';

import type { App } from '@/core/App';
import { IoCContainer } from '@/core/infrastructure/IoCContainer';
import { IpcService } from '@/utils/ipc';

const shortcutDecorator = (name: string) => (target: any, methodName: string, descriptor?: any) => {
  const actions = IoCContainer.shortcuts.get(target.constructor) || [];
  actions.push({ methodName, name });

  IoCContainer.shortcuts.set(target.constructor, actions);

  return descriptor;
};

/**
 *  shortcut inject decorator
 */
type DesktopHotkeyIdCompatible = DesktopHotkeyId | 'quickComposer';

export const shortcut = (method: DesktopHotkeyIdCompatible) => shortcutDecorator(method);

const protocolDecorator =
  (urlType: string, action: string) => (target: any, methodName: string, descriptor?: any) => {
    const handlers = IoCContainer.protocolHandlers.get(target.constructor) || [];
    handlers.push({ action, methodName, urlType });

    IoCContainer.protocolHandlers.set(target.constructor, handlers);

    return descriptor;
  };

/**
 * Protocol handler decorator
 * @param urlType Protocol URL type (e.g., 'plugin')
 * @param action Action type (e.g., 'install')
 */
export const createProtocolHandler = (urlType: string) => (action: string) =>
  protocolDecorator(urlType, action);

interface IControllerModule {
  afterAppReady?: () => void;
  app: App;
  beforeAppReady?: () => void;
}

export class ControllerModule extends IpcService implements IControllerModule {
  constructor(public app: App) {
    super();
    this.app = app;
  }
}

export type IControlModule = typeof ControllerModule;

export { IpcMethod } from '@/utils/ipc';

```
