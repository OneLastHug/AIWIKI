# 文件：src/routes/(main)/settings/provider/features/CreateNewProvider/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/features/CreateNewProvider`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { ProviderIcon } from '@lobehub/icons';
import { type FormItemProps } from '@lobehub/ui';
import { Flexbox, FormModal, Icon, Input, InputPassword, Select, TextArea } from '@lobehub/ui';
import { App } from 'antd';
import { BrainIcon } from 'lucide-react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAiInfraStore } from '@/store/aiInfra/store';
import { type CreateAiProviderParams } from '@/types/aiProvider';
import { KeyVaultsConfigKey, LLMProviderApiTokenKey, LLMProviderBaseUrlKey } from '../../const';
import { CUSTOM_PROVIDER_SDK_OPTIONS } from '../customProviderSdkOptions';
import { normalizeProviderSettings } from '../providerSettings';
export default CreateNewProvider;
```

## 主要对外内容
```text
interface CreateNewProviderProps {
const CreateNewProvider = memo<CreateNewProviderProps>(({ onClose, open }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { ProviderIcon } from '@lobehub/icons';
import { type FormItemProps } from '@lobehub/ui';
import { Flexbox, FormModal, Icon, Input, InputPassword, Select, TextArea } from '@lobehub/ui';
import { App } from 'antd';
import { BrainIcon } from 'lucide-react';
import { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { useAiInfraStore } from '@/store/aiInfra/store';
import { type CreateAiProviderParams } from '@/types/aiProvider';

import { KeyVaultsConfigKey, LLMProviderApiTokenKey, LLMProviderBaseUrlKey } from '../../const';
import { CUSTOM_PROVIDER_SDK_OPTIONS } from '../customProviderSdkOptions';
import { normalizeProviderSettings } from '../providerSettings';

interface CreateNewProviderProps {
  onClose?: () => void;
  open?: boolean;
}

const CreateNewProvider = memo<CreateNewProviderProps>(({ onClose, open }) => {
  const { t } = useTranslation('modelProvider');
  const [loading, setLoading] = useState(false);
  const createNewAiProvider = useAiInfraStore((s) => s.createNewAiProvider);
  const { message } = App.useApp();
  const navigate = useNavigate();
  const onFinish = async (values: CreateAiProviderParams) => {
    setLoading(true);

    try {
      // If name is empty, use id as the name
      const finalValues = {
        ...values,
        name: values.name || values.id,
        settings: normalizeProviderSettings({
          nextSettings: values.settings,
        }) as CreateAiProviderParams['settings'],
      };

      await createNewAiProvider(finalValues);
      setLoading(false);
      navigate(`/settings/provider/${values.id}`);
      message.success(t('createNewAiProvider.createSuccess'));
      onClose?.();
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  const basicItems: FormItemProps[] = [
    {
      children: (
        <Input autoFocus placeholder={t('createNewAiProvider.id.placeholder')} variant={'filled'} />
      ),
      desc: t('createNewAiProvider.id.desc'),
      label: t('createNewAiProvider.id.title'),
      minWidth: 400,
      name: 'id',
      rules: [
        { message: t('createNewAiProvider.id.required'), required: true },
        {
          message: t('createNewAiProvider.id.format'),
          pattern: /^[\d_a-z-]+$/,
        },
        {
          message: t('createNewAiProvider.id.duplicate'),
          validator: (_, value: string) => {
            const list = useAiInfraStore.getState().aiProviderList;
            if (value && list.some((p) => p.id === value)) {
              return Promise.reject();
            }
            return Promise.resolve();
          },
        },
      ],
    },
    {
      children: (
        <Input placeholder={t('createNewAiProvider.name.placeholder')} variant={'filled'} />
      ),
      label: t('createNewAiProvider.name.title'),
      minWidth: 400,
      name: 'name',
    },
    {
      children: (
        <TextArea
          placeholder={t('createNewAiProvider.description.placeholder')}
          style={{ minHeight: 80 }}
          variant={'filled'}
        />
      ),
      label: t('createNewAiProvider.description.title'),
      minWidth: 400,
      name: 'description',
    },
    {
      children: (
        <Input
          allowClear
          placeholder={t('createNewAiProvider.logo.placeholder')}
          variant={'filled'}
        />
      ),
      label: t('createNewAiProvider.logo.title'),
      minWidth: 400,
      name: 'logo',
    },
  ];

  const configItems: FormItemProps[] = [
    {
      children: (
        <Select
          options={CUSTOM_PROVIDER_SDK_OPTIONS}
          placeholder={t('createNewAiProvider.sdkType.placeholder')}
          variant={'filled'}
          optionRender={({ label, value }) => {
            // Map 'router' to 'newapi' for displaying the correct icon
            const iconProvider = value === 'router' ? 'newapi' : (value as string);
            return (
              <Flexbox horizontal align={'center'} gap={8}>
                <ProviderIcon provider={iconProvider} size={18} />
                {label}
              </Flexbox>
            );
          }}
        />
      ),
      label: t('createNewAiProvider.sdkType.title'),
      minWidth: 400,
      name: ['settings', 'sdkType'],
      rules: [{ message: t('createNewAiProvider.sdkType.required'), required: true }],
    },
    {
      children: <Input allowClear placeholder={t('createNewAiProvider.proxyUrl.placeholder')} />,
      label: t('createNewAiProvider.proxyUrl.title'),
      minWidth: 400,
      name: [KeyVaultsConfigKey, LLMProviderBaseUrlKey],
      rules: [{ message: t('createNewAiProvider.proxyUrl.required'), required: true }],
    },
    {
      children: (
        <InputPassword
          autoComplete={'new-password'}
          placeholder={t('createNewAiProvider.apiKey.placeholder')}
          variant={'filled'}
        />
      ),
      label: t('createNewAiProvider.apiKey.title'),
      minWidth: 400,
      name: [KeyVaultsConfigKey, LLMProviderApiTokenKey],
    },
  ];

  return (
    <FormModal
      destroyOnHidden
      open={open}
      scrollToFirstError={{ behavior: 'instant', block: 'end', focus: true }}
      submitLoading={loading}
      submitText={t('createNewAiProvider.confirm')}
      items={[
        {
          children: basicItems,
          title: t('createNewAiProvider.basicTitle'),
        },
        {
          children: configItems,
          title: t('createNewAiProvider.configTitle'),
        },
      ]}
      title={
        <Flexbox horizontal gap={8}>
          <Icon icon={BrainIcon} />
          {t('createNewAiProvider.title')}
        </Flexbox>
      }
      onCancel={onClose}
      onFinish={onFinish}
    />
  );
});

export default CreateNewProvider;

```
