# 文件：packages/electron-client-ipc/README.md

## 文件职责
这个文件位于 `packages/electron-client-ipc`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

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
# @lobechat/electron-client-ipc

This package is a client-side toolkit for handling IPC (Inter-Process Communication) in LobeHub's Electron environment.

## Introduction

In Electron applications, IPC (Inter-Process Communication) serves as a bridge connecting the Main Process, Renderer Process, and NextJS Process. To better organize and manage these communications, we have split the IPC-related code into two packages:

- `@lobechat/electron-client-ipc`: **Client-side IPC package**
- `@lobechat/electron-server-ipc`: **Server-side IPC package**

## Key Differences

### electron-client-ipc (This Package)

- Runtime Environment: Runs in the Renderer Process
- Main Responsibilities:
  - Provides interface definitions for renderer process to call main process methods
  - Encapsulates `ipcRenderer.invoke` related methods
  - Handles communication requests with the main process

### electron-server-ipc

- Runtime Environment: Runs in both Electron main process and Next.js server process
- Main Responsibilities:
  - Provides Socket-based IPC communication mechanism
  - Implements server-side (ElectronIPCServer) and client-side (ElectronIpcClient) communication components
  - Handles cross-process requests and responses
  - Provides automatic reconnection and error handling mechanisms
  - Ensures type-safe API calls

## Use Cases

When the renderer process needs to:

- Access system APIs
- Perform file operations
- Call main process specific functions

All such operations need to be initiated through the methods provided by the `electron-client-ipc` package.

## Technical Notes

This separated package design follows the principle of separation of concerns, ensuring that:

- IPC communication interfaces are clear and maintainable
- Client-side and server-side code are decoupled
- TypeScript type definitions are shared, ensuring type safety

## 🤝 Contribution

IPC communication needs vary across different use cases and platforms. We welcome community contributions to improve and extend the IPC functionality. You can participate in improvements through:

### How to Contribute

1. **Bug Reports**: Report issues with IPC communication or type definitions
2. **Feature Requests**: Suggest new IPC methods or improvements to existing interfaces
3. **Code Contributions**: Submit pull requests for bug fixes or new features

### Contribution Process

1. Fork the [LobeHub repository]([URL已移除])
2. Make your changes to the IPC client package
3. Submit a Pull Request describing:

- The problem being solved
- Implementation details
- Test cases or usage examples
- Impact on existing functionality

## 📌 Note

This is an internal module of LobeHub (`"private": true`), designed specifically for LobeHub and not published as a standalone package.

```
