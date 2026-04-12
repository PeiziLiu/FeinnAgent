# SiliconFlow 配置指南

SiliconFlow 是中国的大模型 API 平台，提供多种开源和商业模型的访问。

## 快速配置

### 1. 获取 API Key

访问 [SiliconFlow 官网](https://siliconflow.cn) 注册并获取 API Key。

### 2. 环境变量配置

```bash
# .env 文件
SILICONFLOW_API_KEY=sk-your-api-key
DEFAULT_MODEL=siliconflow/Pro/zai-org/GLM-5.1
```

### 3. 代码中使用

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="siliconflow/Pro/zai-org/GLM-5.1",
    config={
        "siliconflow_api_key": "sk-your-api-key",
    }
)

response = await agent.run("你好，请介绍一下你自己")
print(response)
```

## 支持的模型

SiliconFlow 提供的模型可以使用以下格式：

```python
# GLM 系列
agent = FeinnAgent(model="siliconflow/Pro/zai-org/GLM-5.1")
agent = FeinnAgent(model="siliconflow/THUDM/glm-4-9b-chat")

# Qwen 系列
agent = FeinnAgent(model="siliconflow/Qwen/Qwen2.5-72B-Instruct")

# DeepSeek 系列
agent = FeinnAgent(model="siliconflow/deepseek-ai/DeepSeek-V3")
agent = FeinnAgent(model="siliconflow/deepseek-ai/DeepSeek-R1")

# Llama 系列
agent = FeinnAgent(model="siliconflow/meta-llama/Llama-3.1-70B-Instruct")
```

## 完整示例

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

    # 简单对话
    response = await agent.run("解释量子计算的基本原理")
    print(response)

    # 使用工具
    response = await agent.run(
        "读取当前目录下的 README.md 文件并总结内容",
        tools=["Read", "Glob"]
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## 与 curl 对比

你的 curl 命令：
```bash
curl --request POST \
  --url https://api.siliconflow.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-key" \
  -d '{
    "model": "Pro/zai-org/GLM-5.1",
    "messages": [
      {"role": "system", "content": "你是一个有用的助手"},
      {"role": "user", "content": "你好，请介绍一下你自己"}
    ]
  }'
```

对应的 FeinnAgent 配置：
```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="siliconflow/Pro/zai-org/GLM-5.1",
    config={"siliconflow_api_key": "sk-key"}
)

response = await agent.run(
    "你好，请介绍一下你自己",
    system="你是一个有用的助手"
)
```

## 故障排除

### API Key 无效

```python
# 确认 API Key 格式正确
# SiliconFlow API Key 格式: sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 模型不存在

```python
# 检查模型名称格式
# 正确: siliconflow/Pro/zai-org/GLM-5.1
# 错误: Pro/zai-org/GLM-5.1 (缺少 siliconflow/ 前缀)
```

### 连接超时

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="siliconflow/Pro/zai-org/GLM-5.1",
    config={
        "siliconflow_api_key": "sk-key",
        "timeout": 120,  # 增加超时时间
    }
)
```
