# Azure OpenAI Setup Guide

## Quick Setup

### 1. Environment Variables

```bash
# .env file
AZURE_OPENAI_API_KEY=bbbbcfc845394f2aaeaf25d9ad7d3a7f
AZURE_OPENAI_URL=https://backups3-northcentralus.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2023-12-01-preview
DEFAULT_MODEL=azure/gpt-4
```

### 2. Code Configuration

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

## Complete Example

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

## Supported Models

Azure OpenAI deployed models can use the following format:

```python
# Format: azure/{deployment-name}
agent = FeinnAgent(model="azure/gpt-4")
agent = FeinnAgent(model="azure/gpt-4o")
agent = FeinnAgent(model="azure/gpt-35-turbo")
```

## Getting Azure OpenAI Credentials

1. Log in to [Azure Portal](https://portal.azure.com)
2. Find your Azure OpenAI resource
3. Go to the **Keys and Endpoint** page
4. Copy the **Key** and **Endpoint**
5. Build the complete URL:
   ```
   {endpoint}/openai/deployments/{deployment-name}/chat/completions?api-version={api-version}
   ```

## API Versions

Supported API versions:
- `2023-12-01-preview`
- `2024-02-15-preview`
- `2024-06-01`
- `2024-10-01-preview`

Specify your required version in the URL.
