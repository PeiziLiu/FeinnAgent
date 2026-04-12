# vLLM + Qwen3.5-35B 部署 Demo

完整的 FeinnAgent + vLLM + Qwen3.5-35B 部署指南。

## 硬件要求

| 配置 | 显存要求 | 推荐 GPU |
|------|---------|----------|
| FP16 | ~70 GB | 1x A100 80GB 或 2x A100 40GB |
| AWQ 量化 | ~20 GB | 1x RTX 4090 或 1x A100 40GB |
| GPTQ 量化 | ~18 GB | 1x RTX 4090 |

## 1. 启动 vLLM 服务

### 方式一：单卡部署（AWQ 量化）

```bash
# 下载并启动量化模型
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct-AWQ \
    --quantization awq \
    --dtype float16 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.90 \
    --port 8000
```

### 方式二：双卡部署（FP16）

```bash
# 使用张量并行在 2 张 GPU 上部署
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct \
    --tensor-parallel-size 2 \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.95 \
    --port 8000
```

### 方式三：Docker 部署

```bash
docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    -p 8000:8000 \
    vllm/vllm-openai:latest \
    --model Qwen/Qwen3.5-35B-Instruct-AWQ \
    --quantization awq \
    --dtype float16 \
    --max-model-len 32768
```

## 2. 验证 vLLM 服务

```bash
# 测试模型列表
curl http://localhost:8000/v1/models

# 测试对话
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-35B-Instruct",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 3. FeinnAgent 配置

### 创建 .env 文件

```bash
cat > .env << 'EOF'
# vLLM 服务端点
VLLM_BASE_URL=http://localhost:8000/v1

# 默认模型（使用 vLLM 部署的 Qwen3.5-35B）
DEFAULT_MODEL=vllm/Qwen/Qwen3.5-35B-Instruct

# 可选：如果 vLLM 启用了 API Key 认证
# VLLM_API_KEY=your-secret-key

# FeinnAgent 配置
MAX_ITERATIONS=50
PERMISSION_MODE=ASK
LOG_LEVEL=INFO
EOF
```

### Python 代码示例

```python
import asyncio
from feinn_agent import FeinnAgent

async def main():
    # 初始化 Agent（自动从 .env 读取配置）
    agent = FeinnAgent(
        model="vllm/Qwen/Qwen3.5-35B-Instruct",
        # 或显式指定配置
        # config={"vllm_base_url": "http://localhost:8000/v1"}
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

## 4. 高级配置

### 启用工具调用

Qwen3.5-35B 支持原生工具调用，FeinnAgent 会自动处理：

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="vllm/Qwen/Qwen3.5-35B-Instruct",
    tools=["Bash", "Read", "Write", "Edit", "Grep"],
    config={
        "vllm_base_url": "http://localhost:8000/v1",
        "max_tokens": 4096,
    }
)

# Agent 会自动调用工具完成任务
response = await agent.run(
    "查找当前目录下所有 Python 文件，统计代码行数"
)
```

### 流式输出

```python
from feinn_agent import FeinnAgent

async def stream_demo():
    agent = FeinnAgent(model="vllm/Qwen/Qwen3.5-35B-Instruct")

    async for chunk in agent.run_stream("写一首关于 AI 的诗"):
        if chunk.type == "text":
            print(chunk.text, end="", flush=True)
        elif chunk.type == "thinking":
            print(f"[思考: {chunk.thinking}]", end="", flush=True)

asyncio.run(stream_demo())
```

### 批量任务处理

```python
from feinn_agent import FeinnAgent
import asyncio

async def batch_process():
    agent = FeinnAgent(model="vllm/Qwen/Qwen3.5-35B-Instruct")

    tasks = [
        "总结机器学习的主要分支",
        "解释深度学习的反向传播算法",
        "比较 CNN 和 Transformer 的优缺点",
    ]

    results = await asyncio.gather(
        *[agent.run(task) for task in tasks]
    )

    for task, result in zip(tasks, results):
        print(f"\n=== {task} ===")
        print(result[:500] + "...")

asyncio.run(batch_process())
```

## 5. 性能优化

### vLLM 启动参数优化

```bash
# 高吞吐量配置
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct-AWQ \
    --quantization awq \
    --dtype float16 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.95 \
    --max-num-seqs 256 \
    --max-num-batched-tokens 32768 \
    --num-scheduler-steps 8 \
    --enable-chunked-prefill \
    --port 8000
```

### 关键参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--max-num-seqs` | 最大并发序列数 | 256-512 |
| `--max-num-batched-tokens` | 最大批处理 token 数 | 32768 |
| `--num-scheduler-steps` | 调度步数 | 8-16 |
| `--enable-chunked-prefill` | 启用分块预填充 | 启用 |
| `--gpu-memory-utilization` | GPU 内存利用率 | 0.90-0.95 |

## 6. 生产部署

### 使用 systemd 服务

```ini
# /etc/systemd/system/vllm-qwen.service
[Unit]
Description=vLLM Qwen3.5-35B Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
Environment="CUDA_VISIBLE_DEVICES=0,1"
Environment="HF_HOME=/home/ubuntu/.cache/huggingface"
ExecStart=/usr/bin/python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct \
    --tensor-parallel-size 2 \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable vllm-qwen
sudo systemctl start vllm-qwen
sudo systemctl status vllm-qwen
```

### 使用 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  vllm:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - HF_HOME=/root/.cache/huggingface
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8000:8000"
    command: >
      --model Qwen/Qwen3.5-35B-Instruct-AWQ
      --quantization awq
      --dtype float16
      --max-model-len 32768
      --gpu-memory-utilization 0.95
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  feinn-agent:
    image: feinn-agent:latest
    environment:
      - VLLM_BASE_URL=http://vllm:8000/v1
      - DEFAULT_MODEL=vllm/Qwen/Qwen3.5-35B-Instruct
      - PERMISSION_MODE=ASK
    depends_on:
      - vllm
    ports:
      - "8080:8080"
```

## 7. 故障排除

### 显存不足

```bash
# 使用量化模型
--model Qwen/Qwen3.5-35B-Instruct-AWQ
--quantization awq

# 或降低 max-model-len
--max-model-len 16384

# 或降低 GPU 内存利用率
--gpu-memory-utilization 0.85
```

### 模型下载失败

```bash
# 设置 HuggingFace 镜像
export HF_ENDPOINT=https://hf-mirror.com

# 或使用代理
export HTTPS_PROXY=http://proxy.example.com:8080
```

### 连接超时

```python
# FeinnAgent 配置中添加超时
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="vllm/Qwen/Qwen3.5-35B-Instruct",
    config={
        "vllm_base_url": "http://localhost:8000/v1",
        "timeout": 120,  # 秒
    }
)
```

## 8. 监控指标

```bash
# 启用 Prometheus 指标
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct-AWQ \
    --enable-metrics \
    --metrics-port 8001

# 查看指标
curl http://localhost:8001/metrics | grep vllm
```

关键指标：
- `vllm:gpu_cache_usage_perc` - GPU 缓存利用率
- `vllm:num_requests_running` - 当前运行请求数
- `vllm:time_to_first_token_seconds` - 首 token 延迟
- `vllm:time_per_output_token_seconds` - 每 token 生成时间
