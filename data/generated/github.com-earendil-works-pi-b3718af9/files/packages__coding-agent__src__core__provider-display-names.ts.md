# 文件：packages/coding-agent/src/core/provider-display-names.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
export const BUILT_IN_PROVIDER_DISPLAY_NAMES: Record<string, string> = {
	anthropic: "Anthropic",
	"amazon-bedrock": "Amazon Bedrock",
	"ant-ling": "Ant Ling",
	"azure-openai-responses": "Azure OpenAI Responses",
	cerebras: "Cerebras",
	"cloudflare-ai-gateway": "Cloudflare AI Gateway",
	"cloudflare-workers-ai": "Cloudflare Workers AI",
	deepseek: "DeepSeek",
	fireworks: "Fireworks",
	google: "Google Gemini",
	"google-vertex": "Google Vertex AI",
	groq: "Groq",
	huggingface: "Hugging Face",
	"kimi-coding": "Kimi For Coding",
	mistral: "Mistral",
	minimax: "MiniMax",
	"minimax-cn": "MiniMax (China)",
	moonshotai: "Moonshot AI",
	"moonshotai-cn": "Moonshot AI (China)",
	nvidia: "NVIDIA NIM",
	opencode: "OpenCode Zen",
	"opencode-go": "OpenCode Go",
	openai: "OpenAI",
	openrouter: "OpenRouter",
	together: "Together AI",
	"vercel-ai-gateway": "Vercel AI Gateway",
	xai: "xAI",
	zai: "ZAI",
	"zai-coding-cn": "ZAI Coding Plan (China)",
	xiaomi: "Xiaomi MiMo",
	"xiaomi-token-plan-cn": "Xiaomi MiMo Token Plan (China)",
	"xiaomi-token-plan-ams": "Xiaomi MiMo Token Plan (Amsterdam)",
	"xiaomi-token-plan-sgp": "Xiaomi MiMo Token Plan (Singapore)",
};

```
