# 文件：src/routes/onboarding/_layout/index.tsx

## 文件职责
这个文件位于 `src/routes/onboarding/_layout`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { AGENT_ONBOARDING_ENABLED } from '@lobechat/business-const';
import { isDesktop } from '@lobechat/const';
import { Center, Flexbox, FluentEmoji, Text } from '@lobehub/ui';
import { Divider, Popconfirm } from 'antd';
import { cx, useTheme } from 'antd-style';
import { type FC, type MouseEvent, type PropsWithChildren, useCallback } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { ProductLogo } from '@/components/Branding';
import LangButton from '@/features/User/UserPanel/LangButton';
import ThemeButton from '@/features/User/UserPanel/ThemeButton';
import { useIsDark } from '@/hooks/useIsDark';
import { useServerConfigStore } from '@/store/serverConfig';
import { useUserStore } from '@/store/user';
import { styles } from './style';
export default OnBoardingContainer;
```

## 主要对外内容
```text
const OnBoardingContainer: FC<PropsWithChildren> = ({ children }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { AGENT_ONBOARDING_ENABLED } from '@lobechat/business-const';
import { isDesktop } from '@lobechat/const';
import { Center, Flexbox, FluentEmoji, Text } from '@lobehub/ui';
import { Divider, Popconfirm } from 'antd';
import { cx, useTheme } from 'antd-style';
import { type FC, type MouseEvent, type PropsWithChildren, useCallback } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';

import { ProductLogo } from '@/components/Branding';
import LangButton from '@/features/User/UserPanel/LangButton';
import ThemeButton from '@/features/User/UserPanel/ThemeButton';
import { useIsDark } from '@/hooks/useIsDark';
import { useServerConfigStore } from '@/store/serverConfig';
import { useUserStore } from '@/store/user';

import { styles } from './style';

const OnBoardingContainer: FC<PropsWithChildren> = ({ children }) => {
  const isDarkMode = useIsDark();
  const theme = useTheme();
  const { t } = useTranslation(['onboarding', 'common']);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const finishOnboarding = useUserStore((s) => s.finishOnboarding);
  const enableAgentOnboarding = useServerConfigStore((s) => s.featureFlags.enableAgentOnboarding);
  const serverConfigInit = useServerConfigStore((s) => s.serverConfigInit);
  const isAgentOnboarding = pathname.startsWith('/onboarding/agent');
  const isBranchOnboarding = isAgentOnboarding || pathname.startsWith('/onboarding/classic');

  const showModeSwitchAndSkipFooter =
    AGENT_ONBOARDING_ENABLED &&
    !isDesktop &&
    serverConfigInit &&
    !!enableAgentOnboarding &&
    isBranchOnboarding;

  const handleConfirmSkip = useCallback(() => {
    finishOnboarding();
    navigate('/');
  }, [finishOnboarding, navigate]);

  const switchMode = useCallback(
    (e: MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      navigate(isAgentOnboarding ? '/onboarding/classic' : '/onboarding/agent');
    },
    [isAgentOnboarding, navigate],
  );

  return (
    <Flexbox className={styles.outerContainer} height={'100%'} padding={8} width={'100%'}>
      <Flexbox
        className={cx(isDarkMode ? styles.innerContainerDark : styles.innerContainerLight)}
        height={'100%'}
        width={'100%'}
      >
        <Flexbox
          horizontal
          align={'center'}
          gap={8}
          justify={'space-between'}
          padding={16}
          width={'100%'}
        >
          <ProductLogo color={theme.colorText} size={28} type={'text'} />
          <Flexbox horizontal align={'center'} gap={16}>
            <Flexbox horizontal align={'center'}>
              <LangButton placement={'bottomRight'} size={18} />
              <Divider className={styles.divider} orientation={'vertical'} />
              <ThemeButton placement={'bottomRight'} size={18} />
            </Flexbox>
          </Flexbox>
        </Flexbox>
        <Center height={'100%'} width={'100%'}>
          {children}
        </Center>
        {showModeSwitchAndSkipFooter && (
          <Center paddingBlock={'0 8px'} paddingInline={16}>
            <Text fontSize={12} type={'secondary'}>
              <Trans
                i18nKey={'agent.layout.switchMessage'}
                ns={'onboarding'}
                components={{
                  modeLink: (
                    <a
                      href={isAgentOnboarding ? '/onboarding/classic' : '/onboarding/agent'}
                      onClick={switchMode}
                    />
                  ),
                  modeText: <Text as={'span'} />,
                  skipLink: (
                    <Popconfirm
                      arrow={false}
                      cancelButtonProps={{ type: 'text' }}
                      cancelText={t('cancel', { ns: 'common' })}
                      okText={t('agent.layout.skipConfirm.ok', { ns: 'onboarding' })}
                      style={{ cursor: 'pointer' }}
                      description={
                        <Text fontSize={13} style={{ marginBottom: 8 }} type={'secondary'}>
                          {t('agent.layout.skipConfirm.content', { ns: 'onboarding' })}
                        </Text>
                      }
                      icon={
                        <FluentEmoji
                          emoji={'😗'}
                          size={24}
                          style={{ marginRight: 8 }}
                          type={'anim'}
                        />
                      }
                      title={
                        <Text fontSize={15}>
                          {t('agent.completionTitle', { ns: 'onboarding' })}
                        </Text>
                      }
                      onConfirm={handleConfirmSkip}
                    />
                  ),
                  skipText: <Text as={'span'} style={{ cursor: 'pointer' }} />,
                }}
                values={{
                  mode: isAgentOnboarding
                    ? t('agent.layout.mode.classic')
                    : t('agent.layout.mode.agent'),
                  skip: t('agent.layout.skip'),
                }}
              />
            </Text>
          </Center>
        )}
      </Flexbox>
    </Flexbox>
  );
};

export default OnBoardingContainer;

```
