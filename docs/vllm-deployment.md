# vLLM Deployment Guide

FeinnAgent supports vLLM for self-hosted LLM inference, enabling enterprise deployments with full control over data privacy and model selection.

## Quick Start

### 1. Start vLLM Server

```bash
# Single GPU
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-72B-Instruct \
    --tensor-parallel-size 1 \
    --port 8000

# Multi-GPU (tensor parallelism)
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-72B-Instruct \
    --tensor-parallel-size 4 \
    --port 8000
```

### 2. Configure FeinnAgent

```bash
# .env file
VLLM_BASE_URL=http://localhost:8000/v1
DEFAULT_MODEL=vllm/Qwen2.5-72B-Instruct
```

### 3. Test Connection

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(model="vllm/Qwen2.5-72B-Instruct")
response = await agent.run("Hello, world!")
print(response)
```

## Deployment Options

### Single Node (Single/Multi-GPU)

```bash
# 1x A100 80GB
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --dtype bfloat16 \
    --max-model-len 32768

# 4x A100 40GB (tensor parallelism)
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --tensor-parallel-size 4 \
    --dtype bfloat16 \
    --max-model-len 32768
```

### Multi-Node (Pipeline Parallelism)

```bash
# Node 0 (head)
vllm serve meta-llama/Llama-3.1-405B-Instruct \
    --tensor-parallel-size 8 \
    --pipeline-parallel-size 2 \
    --node-rank 0 \
    --master-addr <head-node-ip> \
    --master-port 29500

# Node 1 (worker)
vllm serve meta-llama/Llama-3.1-405B-Instruct \
    --tensor-parallel-size 8 \
    --pipeline-parallel-size 2 \
    --node-rank 1 \
    --master-addr <head-node-ip> \
    --master-port 29500
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm
  template:
    metadata:
      labels:
        app: vllm
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        args:
        - --model
        - Qwen/Qwen2.5-72B-Instruct
        - --tensor-parallel-size
        - "4"
        ports:
        - containerPort: 8000
        resources:
          limits:
            nvidia.com/gpu: "4"
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-service
spec:
  selector:
    app: vllm
  ports:
  - port: 8000
    targetPort: 8000
```

## Authentication

### Enable API Key Auth

```bash
vllm serve Qwen/Qwen2.5-72B-Instruct \
    --api-key sk-vllm-secret-key
```

### FeinnAgent Configuration

```bash
# .env
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_API_KEY=sk-vllm-secret-key
```

## Performance Tuning

### Memory Optimization

```bash
vllm serve Qwen/Qwen2.5-72B-Instruct \
    --dtype bfloat16 \
    --quantization awq \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.95
```

### Throughput Optimization

```bash
vllm serve Qwen/Qwen2.5-72B-Instruct \
    --max-num-seqs 256 \
    --max-num-batched-tokens 32768 \
    --num-scheduler-steps 8
```

### Recommended Models

| Model | Size | VRAM Required | Use Case |
|-------|------|---------------|----------|
| Qwen2.5-7B-Instruct | 7B | ~16 GB | Development, testing |
| Qwen2.5-32B-Instruct | 32B | ~64 GB | Production, general tasks |
| Qwen2.5-72B-Instruct | 72B | ~144 GB | Complex reasoning |
| Llama-3.1-70B-Instruct | 70B | ~140 GB | General purpose |
| Llama-3.1-405B-Instruct | 405B | ~810 GB | Maximum capability |
| DeepSeek-V3 | 671B | ~1.3 TB | Advanced reasoning |

## Troubleshooting

### Out of Memory

```bash
# Reduce max sequence length
vllm serve ... --max-model-len 8192

# Enable quantization
vllm serve ... --quantization gptq

# Reduce GPU memory utilization
vllm serve ... --gpu-memory-utilization 0.85
```

### Connection Issues

```bash
# Test vLLM endpoint
curl http://localhost:8000/v1/models

# Test with FeinnAgent
python -c "
from feinn_agent.providers import detect_provider
info = detect_provider('vllm/Qwen2.5-72B-Instruct')
print(f'Provider: {info.provider}')
print(f'Model: {info.model}')
"
```

### Slow Response

- Enable CUDA graph: `--enforce-eager false`
- Adjust batch size: `--max-num-seqs 512`
- Use faster attention: `--attention-flash-attn`

## Advanced Configuration

### Custom Chat Template

```bash
vllm serve my-model \
    --chat-template /path/to/template.jinja
```

### Tool Calling Support

vLLM supports OpenAI-compatible tool calling:

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="vllm/Qwen2.5-72B-Instruct",
    tools=["Bash", "Read", "Write"]
)
```

### Load Balancing

```nginx
# nginx.conf
upstream vllm_backend {
    server vllm-1:8000;
    server vllm-2:8000;
    server vllm-3:8000;
}

server {
    listen 80;
    location /v1/ {
        proxy_pass http://vllm_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Security Best Practices

1. **Enable Authentication**: Always use `--api-key` in production
2. **Network Isolation**: Run vLLM in private network/VPC
3. **TLS Termination**: Use reverse proxy (nginx/traefik) for HTTPS
4. **Rate Limiting**: Implement rate limiting at proxy level
5. **Monitoring**: Enable Prometheus metrics `--enable-metrics`

## Monitoring

```bash
# Enable Prometheus metrics
vllm serve ... --enable-metrics --metrics-port 8001

# Metrics available at http://localhost:8001/metrics
```

Key metrics:
- `vllm:num_requests_running` - Current requests
- `vllm:gpu_cache_usage_perc` - GPU cache utilization
- `vllm:time_to_first_token_seconds` - TTFT latency
- `vllm:time_per_output_token_seconds` - TPOT latency
