# 文件：packages/electron-server-ipc/README.md

## 文件职责
这个文件位于 `packages/electron-server-ipc`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ElectronIPCEventHandler, ElectronIPCServer } from '@lobechat/electron-server-ipc';
import { ElectronIPCMethods, ElectronIpcClient } from '@lobechat/electron-server-ipc';
```

## 主要对外内容
```text
const eventHandler: ElectronIPCEventHandler = {
const server = new ElectronIPCServer(eventHandler);
const client = new ElectronIpcClient();
const dbPath = await client.sendRequest(ElectronIPCMethods.getDatabasePath);
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
# @lobechat/electron-server-ipc

IPC (Inter-Process Communication) module between LobeHub's Electron application and server, providing reliable cross-process communication capabilities.

## 📝 Introduction

`@lobechat/electron-server-ipc` is a core component of LobeHub's desktop application, responsible for handling communication between the Electron main process and Next.js server. It provides a simple yet robust API for passing data and executing remote method calls across different processes.

## 🛠️ Core Features

- **Reliable IPC Communication**: Socket-based communication mechanism ensuring stability and reliability of cross-process communication
- **Automatic Reconnection**: Client features automatic reconnection functionality to improve application stability
- **Type Safety**: Uses TypeScript to provide complete type definitions, ensuring type safety for API calls
- **Cross-Platform Support**: Supports Windows, macOS, and Linux platforms

## 🧩 Core Components

### IPC Server (ElectronIPCServer)

Responsible for listening to client requests and responding, typically runs in Electron's main process:

```typescript
import { ElectronIPCEventHandler, ElectronIPCServer } from '@lobechat/electron-server-ipc';

// Define handler functions
const eventHandler: ElectronIPCEventHandler = {
  getDatabasePath: async () => {
    return '/path/to/database';
  },
  // Other handler functions...
};

// Create and start server
const server = new ElectronIPCServer(eventHandler);
server.start();
```

### IPC Client (ElectronIpcClient)

Responsible for connecting to the server and sending requests, typically used in the server (such as Next.js service):

```typescript
import { ElectronIPCMethods, ElectronIpcClient } from '@lobechat/electron-server-ipc';

// Create client
const client = new ElectronIpcClient();

// Send request
const dbPath = await client.sendRequest(ElectronIPCMethods.getDatabasePath);
```

## 🤝 Contribution

IPC server implementations need to handle various communication scenarios and edge cases. We welcome community contributions to enhance reliability and functionality. You can participate in improvements through:

### How to Contribute

1. **Performance Optimization**: Improve IPC communication speed and reliability
2. **Error Handling**: Enhance error recovery and reconnection mechanisms
3. **New Features**: Add support for new IPC methods or communication patterns
4. **Documentation**: Improve code documentation and usage examples

### Contribution Process

1. Fork the [LobeHub repository]([URL已移除])
2. Implement your improvements to the IPC server package
3. Submit a Pull Request describing:

- Performance improvements or new features
- Testing methodology and results
- Compatibility considerations
- Usage examples

## 📌 Note

This is an internal module of LobeHub (`"private": true`), designed specifically for LobeHub desktop applications and not published as a standalone package.

```
