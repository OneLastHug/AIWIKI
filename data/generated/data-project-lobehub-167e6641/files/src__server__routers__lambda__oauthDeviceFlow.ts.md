# 文件：src/server/routers/lambda/oauthDeviceFlow.ts

## 文件职责
这个文件位于 `src/server/routers/lambda`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { TRPCError } from '@trpc/server';
import { DEFAULT_MODEL_PROVIDER_LIST } from 'model-bank/modelProviders';
import { z } from 'zod';
import { AiProviderModel } from '@/database/models/aiProvider';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { KeyVaultsGateKeeper } from '@/server/modules/KeyVaultsEncrypt';
import {
export const oauthDeviceFlowRouter = router({
export type OAuthDeviceFlowRouter = typeof oauthDeviceFlowRouter;
```

## 主要对外内容
```text
const oauthProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
function getOAuthConfig(providerId: string) {
export const oauthDeviceFlowRouter = router({
export type OAuthDeviceFlowRouter = typeof oauthDeviceFlowRouter;
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { TRPCError } from '@trpc/server';
import { DEFAULT_MODEL_PROVIDER_LIST } from 'model-bank/modelProviders';
import { z } from 'zod';

import { AiProviderModel } from '@/database/models/aiProvider';
import { authedProcedure, router } from '@/libs/trpc/lambda';
import { serverDatabase } from '@/libs/trpc/lambda/middleware';
import { KeyVaultsGateKeeper } from '@/server/modules/KeyVaultsEncrypt';
import {
  getOAuthService,
  GithubCopilotOAuthService,
} from '@/server/services/oauthDeviceFlow/providers/githubCopilot';

const oauthProcedure = authedProcedure.use(serverDatabase).use(async (opts) => {
  const { ctx } = opts;
  const gateKeeper = await KeyVaultsGateKeeper.initWithEnvKey();

  return opts.next({
    ctx: {
      aiProviderModel: new AiProviderModel(ctx.serverDB, ctx.userId),
      gateKeeper,
    },
  });
});

/**
 * Get OAuth Device Flow config for a provider
 */
function getOAuthConfig(providerId: string) {
  const provider = DEFAULT_MODEL_PROVIDER_LIST.find((p) => p.id === providerId);

  if (!provider?.settings?.oauthDeviceFlow) {
    return null;
  }

  return provider.settings.oauthDeviceFlow;
}

export const oauthDeviceFlowRouter = router({
  /**
   * Get current OAuth authentication status for a provider
   */
  getAuthStatus: oauthProcedure
    .input(z.object({ providerId: z.string() }))
    .query(async ({ input, ctx }) => {
      const providerDetail = await ctx.aiProviderModel.getAiProviderById(
        input.providerId,
        KeyVaultsGateKeeper.getUserKeyVaults,
      );

      if (!providerDetail?.keyVaults) {
        return { isAuthenticated: false };
      }

      const keyVaults = providerDetail.keyVaults as Record<string, any>;

      // Check for OAuth token
      if (keyVaults.oauthAccessToken) {
        return {
          avatarUrl: keyVaults.githubAvatarUrl as string | undefined,
          expiresAt: keyVaults.oauthTokenExpiresAt || keyVaults.bearerTokenExpiresAt,
          isAuthenticated: true,
          username: keyVaults.githubUsername as string | undefined,
        };
      }

      return { isAuthenticated: false };
    }),

  /**
   * Initiate OAuth Device Flow - request a device code
   */
  initiateDeviceCode: oauthProcedure
    .input(z.object({ providerId: z.string() }))
    .mutation(async ({ input }) => {
      const config = getOAuthConfig(input.providerId);

      if (!config) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: `Provider ${input.providerId} does not support OAuth Device Flow`,
        });
      }

      const service = getOAuthService(input.providerId);
      const deviceCodeResponse = await service.initiateDeviceCode(config);

      return {
        deviceCode: deviceCodeResponse.deviceCode,
        expiresIn: deviceCodeResponse.expiresIn,
        interval: deviceCodeResponse.interval,
        userCode: deviceCodeResponse.userCode,
        verificationUri: deviceCodeResponse.verificationUri,
      };
    }),

  /**
   * Poll for authorization status and exchange tokens if authorized
   */
  pollAuthStatus: oauthProcedure
    .input(
      z.object({
        deviceCode: z.string(),
        providerId: z.string(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const config = getOAuthConfig(input.providerId);

      if (!config) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: `Provider ${input.providerId} does not support OAuth Device Flow`,
        });
      }

      const service = getOAuthService(input.providerId);

      // For GitHub Copilot, use the specialized service
      if (input.providerId === 'githubcopilot' && service instanceof GithubCopilotOAuthService) {
        try {
          const tokens = await service.completeAuthFlow(config, input.deviceCode);

          if (!tokens) {
            // Still pending
            const pollResult = await service.pollForToken(config, input.deviceCode);
            return { status: pollResult.status };
          }

          // Save tokens and user info to keyVaults
          await ctx.aiProviderModel.updateConfig(
            input.providerId,
            {
              keyVaults: {
                bearerToken: tokens.bearerToken,
                bearerTokenExpiresAt: String(tokens.bearerTokenExpiresAt),
                githubAvatarUrl: tokens.userInfo.avatarUrl,
                githubUsername: tokens.userInfo.username,
                oauthAccessToken: tokens.oauthAccessToken,
              },
            },
            ctx.gateKeeper.encrypt,
            KeyVaultsGateKeeper.getUserKeyVaults,
          );

          return { status: 'success' as const };
        } catch {
          // Probably still pending or error
          const pollResult = await service.pollForToken(config, input.deviceCode);
          return { status: pollResult.status };
        }
      }

      // Generic OAuth flow
      const pollResult = await service.pollForToken(config, input.deviceCode);

      if (pollResult.status === 'success' && pollResult.tokens) {
        // Save tokens to keyVaults
        await ctx.aiProviderModel.updateConfig(
          input.providerId,
          {
            keyVaults: {
              oauthAccessToken: pollResult.tokens.accessToken,
              oauthTokenExpiresAt: pollResult.tokens.expiresIn
                ? String(Date.now() + pollResult.tokens.expiresIn * 1000)
                : undefined,
            },
          },
          ctx.gateKeeper.encrypt,
          KeyVaultsGateKeeper.getUserKeyVaults,
        );
      }

      return { status: pollResult.status };
    }),

  /**
   * Revoke OAuth authorization for a provider
   */
  revokeAuth: oauthProcedure
    .input(z.object({ providerId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      // Clear OAuth tokens and user info from keyVaults
      await ctx.aiProviderModel.updateConfig(
        input.providerId,
        {
          keyVaults: {
            bearerToken: undefined,
            bearerTokenExpiresAt: undefined,
            githubAvatarUrl: undefined,
            githubUsername: undefined,
            oauthAccessToken: undefined,
            oauthTokenExpiresAt: undefined,
          },
        },
        ctx.gateKeeper.encrypt,
        KeyVaultsGateKeeper.getUserKeyVaults,
      );

      return { success: true };
    }),
});

export type OAuthDeviceFlowRouter = typeof oauthDeviceFlowRouter;

```
