# 文件：src/routes/(main)/settings/provider/detail/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/detail`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import Loading from '@/components/Loading/BrandTextLoading';
import dynamic from '@/libs/next/dynamic';
export default ProviderDetailPage;
```

## 主要对外内容
```text
const NewAPI = dynamic(() => import('./newapi'), {
const OpenAI = dynamic(() => import('./openai'), {
const VertexAI = dynamic(() => import('./vertexai'), {
const GitHub = dynamic(() => import('./github'), {
const Ollama = dynamic(() => import('./ollama'), {
const ComfyUI = dynamic(() => import('./comfyui'), {
const Cloudflare = dynamic(() => import('./cloudflare'), {
const Bedrock = dynamic(() => import('./bedrock'), {
const AzureAI = dynamic(() => import('./azureai'), {
const Azure = dynamic(() => import('./azure'), {
const ProviderGrid = dynamic(() => import('../(list)/ProviderGrid'), {
const DefaultPage = dynamic(() => import('./default/ProviderDetialPage'), {
type ProviderDetailPageProps = {
const ProviderDetailPage = (props: ProviderDetailPageProps) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import Loading from '@/components/Loading/BrandTextLoading';
import dynamic from '@/libs/next/dynamic';

const NewAPI = dynamic(() => import('./newapi'), {
  loading: () => <Loading debugId="Provider > NewAPI" />,
  ssr: false,
});
const OpenAI = dynamic(() => import('./openai'), {
  loading: () => <Loading debugId="Provider > OpenAI" />,
  ssr: false,
});
const VertexAI = dynamic(() => import('./vertexai'), {
  loading: () => <Loading debugId="Provider > VertexAI" />,
  ssr: false,
});
const GitHub = dynamic(() => import('./github'), {
  loading: () => <Loading debugId="Provider > GitHub" />,
  ssr: false,
});
const Ollama = dynamic(() => import('./ollama'), {
  loading: () => <Loading debugId="Provider > Ollama" />,
  ssr: false,
});
const ComfyUI = dynamic(() => import('./comfyui'), {
  loading: () => <Loading debugId="Provider > ComfyUI" />,
  ssr: false,
});
const Cloudflare = dynamic(() => import('./cloudflare'), {
  loading: () => <Loading debugId="Provider > Cloudflare" />,
  ssr: false,
});
const Bedrock = dynamic(() => import('./bedrock'), {
  loading: () => <Loading debugId="Provider > Bedrock" />,
  ssr: false,
});
const AzureAI = dynamic(() => import('./azureai'), {
  loading: () => <Loading debugId="Provider > AzureAI" />,
  ssr: false,
});
const Azure = dynamic(() => import('./azure'), {
  loading: () => <Loading debugId="Provider > Azure" />,
  ssr: false,
});
const ProviderGrid = dynamic(() => import('../(list)/ProviderGrid'), {
  loading: () => <Loading debugId="Provider > Grid" />,
  ssr: false,
});
const DefaultPage = dynamic(() => import('./default/ProviderDetialPage'), {
  loading: () => <Loading debugId="Provider > Default" />,
  ssr: false,
});

type ProviderDetailPageProps = {
  id?: string | null;
  onProviderSelect: (provider: string) => void;
};

const ProviderDetailPage = (props: ProviderDetailPageProps) => {
  const { id, onProviderSelect } = props;

  switch (id) {
    case 'all': {
      return <ProviderGrid onProviderSelect={onProviderSelect} />;
    }
    case 'azure': {
      return <Azure />;
    }
    case 'azureai': {
      return <AzureAI />;
    }
    case 'bedrock': {
      return <Bedrock />;
    }
    case 'cloudflare': {
      return <Cloudflare />;
    }
    case 'comfyui': {
      return <ComfyUI />;
    }
    case 'github': {
      return <GitHub />;
    }
    case 'ollama': {
      return <Ollama />;
    }
    case 'newapi': {
      return <NewAPI />;
    }
    case 'openai': {
      return <OpenAI />;
    }
    case 'vertexai': {
      return <VertexAI />;
    }
    default: {
      return <DefaultPage id={id} />;
    }
  }
};

export default ProviderDetailPage;

```
