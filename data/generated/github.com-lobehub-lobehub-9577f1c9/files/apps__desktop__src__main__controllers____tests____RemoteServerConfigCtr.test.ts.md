# 文件：apps/desktop/src/main/controllers/__tests__/RemoteServerConfigCtr.test.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { DataSyncConfig } from '@lobechat/electron-client-ipc';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { App } from '@/core/App';

import RemoteServerConfigCtr from '../RemoteServerConfigCtr';

const { ipcMainHandleMock, mockFetch } = vi.hoisted(() => ({
  ipcMainHandleMock: vi.fn(),
  mockFetch: vi.fn(),
}));

vi.mock('@/utils/net-fetch', () => ({
  netFetch: mockFetch,
}));

// Mock logger
vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
  }),
}));

// Mock electron
vi.mock('electron', () => ({
  ipcMain: {
    handle: ipcMainHandleMock,
  },
  safeStorage: {
    decryptString: vi.fn((buffer: Buffer) => buffer.toString()),
    encryptString: vi.fn((str: string) => Buffer.from(str)),
    isEncryptionAvailable: vi.fn(() => true),
  },
}));

// Mock @/const/env
vi.mock('@/const/env', () => ({
  OFFICIAL_CLOUD_SERVER: '[URL已移除]',
}));

// Mock storeManager
const mockStoreManager = {
  delete: vi.fn(),
  get: vi.fn(),
  set: vi.fn(),
};

const mockBrowserManager = {
  broadcastToAllWindows: vi.fn(),
};

const mockGatewayConnectionSrv = {
  disconnect: vi.fn().mockResolvedValue({ success: true }),
};

const mockApp = {
  browserManager: mockBrowserManager,
  getController: vi.fn(),
  getService: vi.fn().mockReturnValue(mockGatewayConnectionSrv),
  storeManager: mockStoreManager,
} as unknown as App;

describe('RemoteServerConfigCtr', () => {
  let controller: RemoteServerConfigCtr;

  beforeEach(() => {
    vi.clearAllMocks();
    ipcMainHandleMock.mockClear();
    mockStoreManager.get.mockReturnValue({
      active: false,
      storageMode: 'cloud',
    });
    controller = new RemoteServerConfigCtr(mockApp);
  });

  describe('getRemoteServerConfig', () => {
    it('should return stored configuration', async () => {
      const config: DataSyncConfig = {
        active: true,
        remoteServerUrl: '[URL已移除]',
        storageMode: 'selfHost',
      };
      mockStoreManager.get.mockReturnValue(config);

      const result = await controller.getRemoteServerConfig();

      expect(result).toEqual(config);
      expect(mockStoreManager.get).toHaveBeenCalledWith('dataSyncConfig');
    });
  });

  describe('setRemoteServerConfig', () => {
    it('should update configuration', async () => {
      const prevConfig: DataSyncConfig = {
        active: false,
        storageMode: 'cloud',
      };
      mockStoreManager.get.mockReturnValue(prevConfig);

      const newConfig: Partial<DataSyncConfig> = {
        active: true,
        remoteServerUrl: '[URL已移除]',
        storageMode: 'selfHost',
      };

      const result = await controller.setRemoteServerConfig(newConfig);

      expect(result).toBe(true);
      expect(mockStoreManager.set).toHaveBeenCalledWith('dataSyncConfig', {
        ...prevConfig,
        ...newConfig,
      });
    });
  });

  describe('clearRemoteServerConfig', () => {
    it('should clear configuration and tokens', async () => {
      const result = await controller.clearRemoteServerConfig();

      expect(result).toBe(true);
      expect(mockStoreManager.set).toHaveBeenCalledWith('dataSyncConfig', {
        active: false,
        storageMode: 'cloud',
      });
      expect(mockStoreManager.delete).toHaveBeenCalledWith('encryptedTokens');
    });
  });

  describe('saveTokens', () => {
    it('should save encrypted tokens with expiration', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      await controller.saveTokens('access-token', 'refresh-token', 3600);

      expect(safeStorage.encryptString).toHaveBeenCalledWith('access-token');
      expect(safeStorage.encryptString).toHaveBeenCalledWith('refresh-token');
      expect(mockStoreManager.set).toHaveBeenCalledWith(
        'encryptedTokens',
        expect.objectContaining({
          accessToken: expect.any(String),
          expiresAt: expect.any(Number),
          refreshToken: expect.any(String),
        }),
      );
    });

    it('should save tokens without expiration', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      await controller.saveTokens('access-token', 'refresh-token');

      expect(mockStoreManager.set).toHaveBeenCalledWith(
        'encryptedTokens',
        expect.objectContaining({
          accessToken: expect.any(String),
          expiresAt: undefined,
          refreshToken: expect.any(String),
        }),
      );
    });

    it('should save unencrypted tokens when encryption is not available', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(false);

      await controller.saveTokens('access-token', 'refresh-token', 3600);

      expect(safeStorage.encryptString).not.toHaveBeenCalled();
      expect(mockStoreManager.set).toHaveBeenCalledWith(
        'encryptedTokens',
        expect.objectContaining({
          accessToken: 'access-token',
          refreshToken: 'refresh-token',
        }),
      );
    });
  });

  describe('getAccessToken', () => {
    it('should return decrypted access token', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      // First save a token
      await controller.saveTokens('test-access-token', 'test-refresh-token');

      const result = await controller.getAccessToken();

      expect(result).toBe('test-access-token');
    });

    it('should load token from store if not in memory', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);
      vi.mocked(safeStorage.decryptString).mockReturnValue('stored-access-token');

      mockStoreManager.get.mockImplementation((key) => {
        if (key === 'encryptedTokens') {
          return {
            accessToken: Buffer.from('stored-access-token').toString('base64'),
            refreshToken: Buffer.from('stored-refresh-token').toString('base64'),
          };
        }
        return { active: false, storageMode: 'cloud' };
      });

      // Create new controller to test loading from store
      const newController = new RemoteServerConfigCtr(mockApp);
      const result = await newController.getAccessToken();

      expect(result).toBe('stored-access-token');
    });

    it('should return null when no token exists', async () => {
      mockStoreManager.get.mockImplementation((key) => {
        if (key === 'encryptedTokens') {
          return null;
        }
        return { active: false, storageMode: 'cloud' };
      });

      const newController = new RemoteServerConfigCtr(mockApp);
      const result = await newController.getAccessToken();

      expect(result).toBeNull();
    });

    it('should return raw token when encryption is not available', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(false);

      await controller.saveTokens('raw-access-token', 'raw-refresh-token');
      const result = await controller.getAccessToken();

      expect(result).toBe('raw-access-token');
    });

    it('should return null on decryption error', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);
      vi.mocked(safeStorage.decryptString).mockImplementation(() => {
        throw new Error('Decryption failed');
      });

      mockStoreManager.get.mockImplementation((key) => {
        if (key === 'encryptedTokens') {
          return {
            accessToken: 'invalid-encrypted-token',
            refreshToken: 'invalid-encrypted-token',
          };
        }
        return { active: false, storageMode: 'cloud' };
      });

      const newController = new RemoteServerConfigCtr(mockApp);
      const result = await newController.getAccessToken();

      expect(result).toBeNull();
    });
  });

  describe('getRefreshToken', () => {
    it('should return decrypted refresh token', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);
      vi.mocked(safeStorage.decryptString).mockImplementation((buffer: Buffer) =>
        buffer.toString(),
      );

      await controller.saveTokens('test-access-token', 'test-refresh-token');

      const result = await controller.getRefreshToken();

      expect(result).toBe('test-refresh-token');
    });

    it('should return null when no token exists', async () => {
      mockStoreManager.get.mockImplementation((key) => {
        if (key === 'encryptedTokens') {
          return null;
        }
        return { active: false, storageMode: 'cloud' };
      });

      const newController = new RemoteServerConfigCtr(mockApp);
      const result = await newController.getRefreshToken();

      expect(result).toBeNull();
    });
  });

  describe('clearTokens', () => {
    it('should clear all tokens from memory and store', async () => {
      await controller.saveTokens('access', 'refresh', 3600);
      await controller.clearTokens();

      expect(mockStoreManager.delete).toHaveBeenCalledWith('encryptedTokens');

      // Verify tokens are cleared from memory
      const accessToken = await controller.getAccessToken();
      expect(accessToken).toBeNull();
    });

    it('should disconnect gateway when tokens are cleared', async () => {
      await controller.saveTokens('access', 'refresh', 3600);
      await controller.clearTokens();

      expect(mockGatewayConnectionSrv.disconnect).toHaveBeenCalled();
    });
  });

  describe('getTokenExpiresAt', () => {
    it('should return expiration time after saving tokens with expiration', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      const beforeSave = Date.now();
      await controller.saveTokens('access', 'refresh', 3600);
      const afterSave = Date.now();

      const expiresAt = controller.getTokenExpiresAt();

      expect(expiresAt).toBeDefined();
      expect(expiresAt).toBeGreaterThanOrEqual(beforeSave + 3600 * 1000);
      expect(expiresAt).toBeLessThanOrEqual(afterSave + 3600 * 1000);
    });

    it('should return undefined when no expiration is set', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      await controller.saveTokens('access', 'refresh');

      const expiresAt = controller.getTokenExpiresAt();

      expect(expiresAt).toBeUndefined();
    });
  });

  describe('isTokenExpiringSoon', () => {
    it('should return false when no expiration is set', () => {
      const result = controller.isTokenExpiringSoon();

      expect(result).toBe(false);
    });

    it('should return false when token is not expiring soon', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      // Token expires in 2 days (well beyond the 24-hour default buffer)
      await controller.saveTokens('access', 'refresh', 2 * 24 * 3600);

      // Default buffer is 24 hours
      const result = controller.isTokenExpiringSoon();

      expect(result).toBe(false);
    });

    it('should return true when token is within buffer time', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      // Token expires in 2 minutes
      await controller.saveTokens('access', 'refresh', 120);

      // Default buffer is 5 minutes, so token is expiring soon
      const result = controller.isTokenExpiringSoon();

      expect(result).toBe(true);
    });

    it('should respect custom buffer time', async () => {
      const { safeStorage } = await import('electron');
      vi.mocked(safeStorage.isEncryptionAvailable).mockReturnValue(true);

      // Token expires in 10 minutes
      await controller.saveTokens('access', 'refresh', 600);

      // With 15 minute buffer, should be expiring soon
      const result = controller.isTokenExpiringSoon(15 * 60 * 1000);

      expect(result).toBe(true);
    });
  });

  describe('isNonRetryableError', () => {
    it('should return false for null/undefined error', () => {
      expect(controller.isNonRetryableError(undefined)).toBe(false);
      expect(controller.isNonRetryableError('')).toBe(false);
    });

    it('should return true for OIDC error codes', () => {
      expect(controller.isNonRetryableError('invalid_grant')).toBe(true);
      expect(controller.isNonRetryableError('Token refresh failed: invalid_client')).toBe(true);
      expect(controller.isNonRetryableError('unauthorized_client error')).toBe(true);
      expect(controller.isNonRetryableError('access_denied by user')).toBe(true);
      expect(controller.isNonRetryableError('invalid_scope requested')).toBe(true);
    });

    it('should return true for deterministic failures', () => {
      expect(controller.isNonRetryableError('No refresh token available')).toBe(true);
      expect(controller.isNonRetryableError('Remote server is not active or configured')).toBe(
        true,
      );
      expect(controller.isNonRetryableError('Missing tokens in refresh response')).toBe(true);
    });

    it('should return false for transient/network errors', () => {
      expect(controller.isNonRetryableError('Network error')).toBe(false);
      expect(controller.isNonRetryableError('fetch failed')).toBe(false);
      expect(controller.isNonRetryableError('ETIMEDOUT')).toBe(false);
      expect(controller.isNonRetry
...[truncated]
```
