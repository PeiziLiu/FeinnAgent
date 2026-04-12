# Azure OpenAI 配置指南

## 快速配置

### 1. 环境变量方式

```bash
# .env 文件
AZURE_OPENAI_API_KEY=bbbbcfc845394f2aaeaf25d9ad7d3a7f
AZURE_OPENAI_URL=https://backups3-northcentralus.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2023-12-01-preview
DEFAULT_MODEL=azure/gpt-4
```

### 2. 代码配置方式

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="azure/gpt-4",
    config={
        "azure_api_key": "bbbbcfc845394f2aaeaf25d9ad7d3a7f",
        "azure_base_url": "https://backups3-northcentralus.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2023-12-01-preview",
    }
)
```

## 完整示例

```python
import asyncio
from feinn_agent import FeinnAgent

async def main():
    agent = FeinnAgent(
        model="azure/gpt-4",
        config={
            "azure_api_key": "bbbbcfc845394f2aaeaf25d9ad7d3a7f",
            "azure_base_url": "https://backups3-northcentralus.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2023-12-01-preview",
            "max_tokens": 4096,
        }
    )

    response = await agent.run("Hello, Azure OpenAI!")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## 支持的模型

Azure OpenAI 部署的模型可以使用以下格式：

```python
# 格式: azure/{deployment-name}
agent = FeinnAgent(model="azure/gpt-4")
agent = FeinnAgent(model="azure/gpt-4o")
agent = FeinnAgent(model="azure/gpt-35-turbo")
```

## 获取 Azure OpenAI 凭证

1. 登录 [Azure Portal](https://portal.azure.com)
2. 找到你的 Azure OpenAI 资源
3. 进入 **Keys and Endpoint** 页面
4. 复制 **Key** 和 **Endpoint**
5. 构建完整的 URL：
   ```
   {endpoint}/openai/deployments/{deployment-name}/chat/completions?api-version={api-version}
   ```

## API 版本

支持的 API 版本：
- `2023-12-01-preview`
- `2024-02-15-preview`
- `2024-06-01`
- `2024-10-01-preview`

在 URL 中指定你需要的版本。
