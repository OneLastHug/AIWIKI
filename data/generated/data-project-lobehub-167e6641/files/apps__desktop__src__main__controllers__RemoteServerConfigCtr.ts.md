# 文件：apps/desktop/src/main/controllers/RemoteServerConfigCtr.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import querystring from 'node:querystring';
import { URL } from 'node:url';

import type { DataSyncConfig } from '@lobechat/electron-client-ipc';
import { safeStorage, session as electronSession } from 'electron';

import { OFFICIAL_CLOUD_SERVER } from '@/const/env';
import GatewayConnectionService from '@/services/gatewayConnectionSrv';
import { appendVercelCookie } from '@/utils/http-headers';
import { createLogger } from '@/utils/logger';
import { netFetch } from '@/utils/net-fetch';

import { ControllerModule, IpcMethod } from './index';

/**
 * Non-retryable OIDC error codes
 * These errors indicate the refresh token is invalid and retry won't help
 */
const NON_RETRYABLE_OIDC_ERRORS = [
  'invalid_grant', // refresh token is invalid, expired, or revoked
  'invalid_client', // client configuration error
  'unauthorized_client', // client not authorized
  'access_denied', // user denied access
  'invalid_scope', // requested scope is invalid
];

/**
 * Deterministic failures that will never succeed on retry
 * These are permanent state issues that require user intervention
 */
const DETERMINISTIC_FAILURES = [
  'no refresh token available', // refresh token is missing from storage
  'remote server is not active or configured', // config is invalid or disabled
  'missing tokens in refresh response', // server returned incomplete response
];

// Create logger
const logger = createLogger('controllers:RemoteServerConfigCtr');

/**
 * Remote Server Configuration Controller
 * Used to manage custom remote LobeChat server configuration
 */
export default class RemoteServerConfigCtr extends ControllerModule {
  static override readonly groupName = 'remoteServer';
  /**
   * Key used to store encrypted tokens in electron-store.
   */
  private readonly encryptedTokensKey = 'encryptedTokens';

  /**
   * Normalize legacy config that used local storageMode.
   * Local mode has been removed; fall back to cloud.
   */
  private normalizeConfig = (config: DataSyncConfig): DataSyncConfig => {
    // Use type assertion to handle legacy 'local' value from stored data
    if ((config.storageMode as string) !== 'local') return config;

    const nextConfig: DataSyncConfig = {
      ...config,
      remoteServerUrl: config.remoteServerUrl || OFFICIAL_CLOUD_SERVER,
      storageMode: 'cloud',
    };

    this.app.storeManager.set('dataSyncConfig', nextConfig);

    return nextConfig;
  };

  /**
   * Get remote server configuration
   */
  @IpcMethod()
  async getRemoteServerConfig() {
    logger.debug('Getting remote server configuration');
    const { storeManager } = this.app;

    const config: DataSyncConfig = storeManager.get('dataSyncConfig');
    const normalized = this.normalizeConfig(config);

    logger.debug(
      `Remote server config: active=${normalized.active}, storageMode=${normalized.storageMode}, url=${normalized.remoteServerUrl}`,
    );

    return normalized;
  }

  /**
   * Check if remote server is properly configured and ready for use
   * For 'cloud' mode, only checks if active (remoteServerUrl is undefined, uses OFFICIAL_CLOUD_SERVER)
   * For 'selfHost' mode, checks if active AND remoteServerUrl is configured
   * @param config Optional config object, if not provided will fetch current config
   * @returns true if remote server is properly configured
   */
  async isRemoteServerConfigured(config?: DataSyncConfig): Promise<boolean> {
    const effectiveConfig = config ?? (await this.getRemoteServerConfig());
    const isActive = Boolean(effectiveConfig.active);
    const isSelfHostConfigured =
      effectiveConfig.storageMode !== 'selfHost' ||
      this.isValidSelfHostRemoteUrl(effectiveConfig.remoteServerUrl);

    return isActive && isSelfHostConfigured;
  }

  private isValidSelfHostRemoteUrl(remoteServerUrl?: string): boolean {
    if (!remoteServerUrl) return false;
    const normalizedUrl = remoteServerUrl.trim();

    if (!normalizedUrl) return false;

    try {
      const parsedUrl = new URL(normalizedUrl);
      return parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:';
    } catch {
      return false;
    }
  }

  /**
   * Set remote server configuration
   */
  @IpcMethod()
  async setRemoteServerConfig(config: Partial<DataSyncConfig>) {
    logger.info(
      `Setting remote server storageMode: active=${config.active}, storageMode=${config.storageMode}, url=${config.remoteServerUrl}`,
    );
    const { storeManager } = this.app;
    const prev: DataSyncConfig = storeManager.get('dataSyncConfig');

    // Save configuration with legacy local storage fallback
    const merged = this.normalizeConfig({ ...prev, ...config });
    storeManager.set('dataSyncConfig', merged);

    this.broadcastRemoteServerConfigUpdated();

    return true;
  }

  /**
   * Clear remote server configuration
   */
  @IpcMethod()
  async clearRemoteServerConfig() {
    logger.info('Clearing remote server configuration');
    const { storeManager } = this.app;

    // Clear instance configuration
    storeManager.set('dataSyncConfig', { active: false, storageMode: 'cloud' });

    // Clear tokens (if any)
    await this.clearTokens();

    this.broadcastRemoteServerConfigUpdated();

    return true;
  }

  private broadcastRemoteServerConfigUpdated() {
    logger.debug('Broadcasting remoteServerConfigUpdated event to all windows');
    this.app.browserManager.broadcastToAllWindows('remoteServerConfigUpdated', undefined);
  }

  /**
   * Encrypted tokens
   * Stored in memory for quick access, loaded from persistent storage on init.
   */
  private encryptedAccessToken?: string;
  private encryptedRefreshToken?: string;

  /**
   * Token expiration time (timestamp in milliseconds)
   * Used for automatic token refresh
   */
  private tokenExpiresAt?: number;

  /**
   * Last token refresh time (timestamp in milliseconds)
   * Used to control refresh frequency on app startup/activate
   */
  private lastRefreshAt?: number;

  /**
   * Promise representing the ongoing token refresh operation.
   * Used to prevent concurrent refreshes and allow callers to wait.
   */
  private refreshPromise: Promise<{ error?: string; success: boolean }> | null = null;

  /**
   * Encrypt and store tokens
   * @param accessToken Access token
   * @param refreshToken Refresh token
   * @param expiresIn Token expiration time in seconds (optional)
   */
  async saveTokens(accessToken: string, refreshToken: string, expiresIn?: number) {
    logger.info('Saving encrypted tokens');

    // Calculate expiration time if provided
    if (expiresIn) {
      this.tokenExpiresAt = Date.now() + expiresIn * 1000;
      logger.debug(`Token expires at: ${new Date(this.tokenExpiresAt).toISOString()}`);
    } else {
      this.tokenExpiresAt = undefined;
    }

    // Update last refresh time
    this.lastRefreshAt = Date.now();
    logger.debug(`Token last refreshed at: ${new Date(this.lastRefreshAt).toISOString()}`);

    // If platform doesn't support secure storage, store raw tokens
    if (!safeStorage.isEncryptionAvailable()) {
      logger.warn('Safe storage not available, storing tokens unencrypted');
      this.encryptedAccessToken = accessToken;
      this.encryptedRefreshToken = refreshToken;
      // Persist unencrypted tokens (consider security implications)
      this.app.storeManager.set(this.encryptedTokensKey, {
        accessToken: this.encryptedAccessToken,
        expiresAt: this.tokenExpiresAt,
        lastRefreshAt: this.lastRefreshAt,
        refreshToken: this.encryptedRefreshToken,
      });
      return;
    }

    // Encrypt tokens
    logger.debug('Encrypting tokens using safe storage');
    this.encryptedAccessToken = Buffer.from(safeStorage.encryptString(accessToken)).toString(
      'base64',
    );

    this.encryptedRefreshToken = Buffer.from(safeStorage.encryptString(refreshToken)).toString(
      'base64',
    );

    // Persist encrypted tokens
    logger.debug(`Persisting encrypted tokens to store key: ${this.encryptedTokensKey}`);
    this.app.storeManager.set(this.encryptedTokensKey, {
      accessToken: this.encryptedAccessToken,
      expiresAt: this.tokenExpiresAt,
      lastRefreshAt: this.lastRefreshAt,
      refreshToken: this.encryptedRefreshToken,
    });
  }

  /**
   * Get decrypted access token
   */
  async getAccessToken(): Promise<string | null> {
    // Try loading from memory first
    if (!this.encryptedAccessToken) {
      logger.debug('Access token not in memory, trying to load from store...');
      this.loadTokensFromStore(); // Attempt to load from persistent storage
    }

    if (!this.encryptedAccessToken) {
      logger.debug('No access token found in memory or store.');
      return null;
    }

    // If platform doesn't support secure storage, return stored token
    if (!safeStorage.isEncryptionAvailable()) {
      logger.debug(
        'Safe storage not available, returning potentially unencrypted token from memory/store',
      );
      return this.encryptedAccessToken;
    }

    try {
      // Decrypt token
      logger.debug('Decrypting access token');
      const encryptedData = Buffer.from(this.encryptedAccessToken, 'base64');
      return safeStorage.decryptString(encryptedData);
    } catch (error) {
      logger.error('Failed to decrypt access token:', error);
      return null;
    }
  }

  /**
   * Get decrypted refresh token
   */
  async getRefreshToken(): Promise<string | null> {
    // Try loading from memory first
    if (!this.encryptedRefreshToken) {
      logger.debug('Refresh token not in memory, trying to load from store...');
      this.loadTokensFromStore(); // Attempt to load from persistent storage
    }

    if (!this.encryptedRefreshToken) {
      logger.debug('No refresh token found in memory or store.');
      return null;
    }

    // If platform doesn't support secure storage, return stored token
    if (!safeStorage.isEncryptionAvailable()) {
      logger.debug(
        'Safe storage not available, returning potentially unencrypted token from memory/store',
      );
      return this.encryptedRefreshToken;
    }

    try {
      // Decrypt token
      logger.debug('Decrypting refresh token');
      const encryptedData = Buffer.from(this.encryptedRefreshToken, 'base64');
      return safeStorage.decryptString(encryptedData);
    } catch (error) {
      logger.error('Failed to decrypt refresh token:', error);
      return null;
    }
  }

  /**
   * Clear tokens
   */
  async clearTokens() {
    logger.info('Clearing access and refresh tokens');
    this.encryptedAccessToken = undefined;
    this.encryptedRefreshToken = undefined;
    this.tokenExpiresAt = undefined;
    // Also clear from persistent storage
    logger.debug(`Deleting tokens from store key: ${this.encryptedTokensKey}`);
    this.app.storeManager.delete(this.encryptedTokensKey);

    // Disconnect gateway when tokens are cleared (logout / token refresh failure)
    const gatewaySrv = this.app.getService(GatewayConnectionService);
    if (gatewaySrv) {
      logger.debug('Disconnecting gateway due to token clear');
      await gatewaySrv.disconnect();
    }
  }

  /**
   * Get token expiration time
   */
  getTokenExpiresAt(): number | undefined {
    return this.tokenExpiresAt;
  }

  /**
   * Check if token is expired or will expire soon
   * @param bufferTimeMs Buffer time in milliseconds (default 1 day)
   * @returns true if token is expired or will expire soon
   */
  isTokenExpiringSoon(bufferTimeMs: number = 24 * 60 * 60 * 1000): boolean {
    if (!this.tokenExpiresAt) {
      return false; // No expiration time available
    }

    const currentTime = Date.now();
    const bufferTime = this.tokenExpiresAt - bufferTimeMs;

    return currentTime >= bufferTime;
  }

  /**
   * Check if an error is non-retryable
   * Includes OIDC errors (e.g., invalid_grant) and deterministic failures
   * (e.g., missing refresh token, invalid config)
   * @param error Error message to check
   * @returns true if the error should not be retried
   */
  isNonRetryableError(error?: string): boolean {
    if (!error) return false;
    const lowerError = error.toLowerCase();

    // Check OIDC error codes
    if (NON_RETRYABLE_OIDC_ERRORS.some((code) => lowerError.includes(code))) {
      return true;
    }

    // Check deterministic failures that require user intervention
    if (DETERMINISTIC_FAILURES.some((msg) => lowerError.includes(msg))) {
      return true;
    }

    return false;
  }

  /**
   * Refresh the access token using the stored refresh token (single attempt).
   * Concurrent callers share the in-progress refresh promise.
   */
  async refreshAccessToken(): Promise<{ error?: string; success: boolean }> {
    // If a refresh is already in progress, return the existing promise
    if (this.refreshPromise) {
      logger.debug('Token refresh already in progress, returning existing promise.');
      return this.refreshPromise;
    }

    logger.info('Initiating new token refresh operation.');

    // No retry: with refresh token rotation the server consumes the old token as soon
    // as the request lands. Resending it (e.g. after a lost response) triggers reuse
    // detection — invalid_grant + revocation of the whole grant — which logs the user
    // out. Transient failures are recovered by the next refresh cycle instead.
    this.refreshPromise = this.performTokenRefresh().finally(() => {
      logger.debug('Clearing the refresh promise reference.');
      this.refreshPromise = null;
    });

    return this.refreshPromise;
  }

  /**
   * Performs the actual token refresh logic.
   * This method is called by refreshAccessToken and wrapped in a promise.
   */
  private async performTokenRefresh(): Promise<{ error?: string; success: boolean }> {
    try {
      // Get configuration information
      const config = await this.getRemoteServerConfig();

      if (!(await this.isRemoteServerConfigured(config))) {
        logger.warn('Remote server not active or configured, skipping refresh.'
...[truncated]
```
