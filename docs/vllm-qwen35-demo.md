# vLLM + Qwen3.5-35B Deployment Demo

Complete FeinnAgent + vLLM + Qwen3.5-35B deployment guide.

## Hardware Requirements

| Configuration | VRAM Required | Recommended GPU |
|---------------|---------------|-----------------|
| FP16 | ~70 GB | 1x A100 80GB or 2x A100 40GB |
| AWQ Quantization | ~20 GB | 1x RTX 4090 or 1x A100 40GB |
| GPTQ Quantization | ~18 GB | 1x RTX 4090 |

## 1. Start vLLM Service

### Method 1: Single GPU Deployment (AWQ Quantization)

```bash
# Download and start quantized model
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct-AWQ \
    --quantization awq \
    --dtype float16 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.90 \
    --port 8000
```

### Method 2: Dual GPU Deployment (FP16)

```bash
# Deploy using tensor parallelism on 2 GPUs
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct \
    --tensor-parallel-size 2 \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.95 \
    --port 8000
```

### Method 3: Docker Deployment

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

## 2. Verify vLLM Service

```bash
# Test model list
curl http://localhost:8000/v1/models

# Test chat
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-35B-Instruct",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 3. FeinnAgent Configuration

### Create .env File

```bash
cat > .env << 'EOF'
# vLLM server endpoint
VLLM_BASE_URL=http://localhost:8000/v1

# Default model (using vLLM deployed Qwen3.5-35B)
DEFAULT_MODEL=vllm/Qwen/Qwen3.5-35B-Instruct

# Optional: if vLLM has API Key authentication enabled
# VLLM_API_KEY=your-secret-key

# FeinnAgent configuration
MAX_ITERATIONS=50
PERMISSION_MODE=ASK
LOG_LEVEL=INFO
EOF
```

### Python Code Example

```python
import asyncio
from feinn_agent import FeinnAgent

async def main():
    # Initialize Agent (automatically reads from .env)
    agent = FeinnAgent(
        model="vllm/Qwen/Qwen3.5-35B-Instruct",
        # Or explicitly specify configuration
        # config={"vllm_base_url": "http://localhost:8000/v1"}
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

## 4. Advanced Configuration

### Enable Tool Calling

Qwen3.5-35B supports native tool calling, FeinnAgent handles it automatically:

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

# Agent will automatically call tools to complete tasks
response = await agent.run(
    "Find all Python files in the current directory and count lines of code"
)
```

### Streaming Output

```python
from feinn_agent import FeinnAgent

async def stream_demo():
    agent = FeinnAgent(model="vllm/Qwen/Qwen3.5-35B-Instruct")

    async for chunk in agent.run_stream("Write a poem about AI"):
        if chunk.type == "text":
            print(chunk.text, end="", flush=True)
        elif chunk.type == "thinking":
            print(f"[thinking: {chunk.thinking}]", end="", flush=True)

asyncio.run(stream_demo())
```

### Batch Task Processing

```python
from feinn_agent import FeinnAgent
import asyncio

async def batch_process():
    agent = FeinnAgent(model="vllm/Qwen/Qwen3.5-35B-Instruct")

    tasks = [
        "Summarize the main branches of machine learning",
        "Explain the backpropagation algorithm in deep learning",
        "Compare the advantages and disadvantages of CNN and Transformer",
    ]

    results = await asyncio.gather(
        *[agent.run(task) for task in tasks]
    )

    for task, result in zip(tasks, results):
        print(f"\n=== {task} ===")
        print(result[:500] + "...")

asyncio.run(batch_process())
```

## 5. Performance Optimization

### vLLM Startup Parameter Optimization

```bash
# High throughput configuration
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

### Key Parameter Explanation

| Parameter | Description | Recommended Value |
|-----------|-------------|-------------------|
| `--max-num-seqs` | Maximum concurrent sequences | 256-512 |
| `--max-num-batched-tokens` | Maximum batched tokens | 32768 |
| `--num-scheduler-steps` | Scheduler steps | 8-16 |
| `--enable-chunked-prefill` | Enable chunked prefill | Enabled |
| `--gpu-memory-utilization` | GPU memory utilization | 0.90-0.95 |

## 6. Production Deployment

### Using systemd Service

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

### Using Docker Compose

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

## 7. Troubleshooting

### Out of Memory

```bash
# Use quantized model
--model Qwen/Qwen3.5-35B-Instruct-AWQ
--quantization awq

# Or reduce max-model-len
--max-model-len 16384

# Or reduce GPU memory utilization
--gpu-memory-utilization 0.85
```

### Model Download Failed

```bash
# Set HuggingFace mirror
export HF_ENDPOINT=https://hf-mirror.com

# Or use proxy
export HTTPS_PROXY=http://proxy.example.com:8080
```

### Connection Timeout

```python
# Add timeout in FeinnAgent configuration
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="vllm/Qwen/Qwen3.5-35B-Instruct",
    config={
        "vllm_base_url": "http://localhost:8000/v1",
        "timeout": 120,  # seconds
    }
)
```

## 8. Monitoring Metrics

```bash
# Enable Prometheus metrics
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-Instruct-AWQ \
    --enable-metrics \
    --metrics-port 8001

# View metrics
curl http://localhost:8001/metrics | grep vllm
```

Key metrics:
- `vllm:gpu_cache_usage_perc` - GPU cache utilization
- `vllm:num_requests_running` - Current running requests
- `vllm:time_to_first_token_seconds` - Time to first token latency
- `vllm:time_per_output_token_seconds` - Time per output token
