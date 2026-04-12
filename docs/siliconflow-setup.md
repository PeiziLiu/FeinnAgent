# SiliconFlow Setup Guide

SiliconFlow is a China-based large model API platform providing access to various open-source and commercial models.

## Quick Setup

### 1. Get API Key

Visit [SiliconFlow Official Website](https://siliconflow.cn) to register and get an API Key.

### 2. Environment Variable Configuration

```bash
# .env file
SILICONFLOW_API_KEY=sk-your-api-key
DEFAULT_MODEL=siliconflow/Pro/zai-org/GLM-5.1
```

### 3. Use in Code

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="siliconflow/Pro/zai-org/GLM-5.1",
    config={
        "siliconflow_api_key": "sk-your-api-key",
    }
)

response = await agent.run("Hello, please introduce yourself")
print(response)
```

## Supported Models

SiliconFlow models can be used in the following format:

```python
# GLM series
agent = FeinnAgent(model="siliconflow/Pro/zai-org/GLM-5.1")
agent = FeinnAgent(model="siliconflow/THUDM/glm-4-9b-chat")

# Qwen series
agent = FeinnAgent(model="siliconflow/Qwen/Qwen2.5-72B-Instruct")

# DeepSeek series
agent = FeinnAgent(model="siliconflow/deepseek-ai/DeepSeek-V3")
agent = FeinnAgent(model="siliconflow/deepseek-ai/DeepSeek-R1")

# Llama series
agent = FeinnAgent(model="siliconflow/meta-llama/Llama-3.1-70B-Instruct")
```

## Complete Example

```python
import asyncio
from feinn_agent import FeinnAgent

async def main():
    agent = FeinnAgent(
        model="siliconflow/Pro/zai-org/GLM-5.1",
        config={
            "siliconflow_api_key": "sk-your-api-key",
            "max_tokens": 4096,
        }
    )

    # Simple conversation
    response = await agent.run("Explain the basic principles of quantum computing")
    print(response)

    # Use tools
    response = await agent.run(
        "Read the README.md file in the current directory and summarize its content",
        tools=["Read", "Glob"]
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## Comparison with curl

Your curl command:
```bash
curl --request POST \
  --url https://api.siliconflow.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-key" \
  -d '{
    "model": "Pro/zai-org/GLM-5.1",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant"},
      {"role": "user", "content": "Hello, please introduce yourself"}
    ]
  }'
```

Corresponding FeinnAgent configuration:
```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="siliconflow/Pro/zai-org/GLM-5.1",
    config={"siliconflow_api_key": "sk-key"}
)

response = await agent.run(
    "Hello, please introduce yourself",
    system="You are a helpful assistant"
)
```

## Troubleshooting

### Invalid API Key

```python
# Confirm API Key format is correct
# SiliconFlow API Key format: sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### Model Not Found

```python
# Check model name format
# Correct: siliconflow/Pro/zai-org/GLM-5.1
# Incorrect: Pro/zai-org/GLM-5.1 (missing siliconflow/ prefix)
```

### Connection Timeout

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="siliconflow/Pro/zai-org/GLM-5.1",
    config={
        "siliconflow_api_key": "sk-key",
        "timeout": 120,  # Increase timeout
    }
)
```
