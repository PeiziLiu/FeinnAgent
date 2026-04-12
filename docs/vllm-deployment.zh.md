# vLLM 部署指南

FeinnAgent 支持使用 vLLM 进行自托管 LLM 推理，使企业能够完全控制数据隐私和模型选择。

## 快速开始

### 1. 启动 vLLM 服务器

```bash
# 单 GPU
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-72B-Instruct \
    --tensor-parallel-size 1 \
    --port 8000

# 多 GPU（张量并行）
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-72B-Instruct \
    --tensor-parallel-size 4 \
    --port 8000
```

### 2. 配置 FeinnAgent

```bash
# .env 文件
VLLM_BASE_URL=http://localhost:8000/v1
DEFAULT_MODEL=vllm/Qwen2.5-72B-Instruct
```

### 3. 测试连接

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(model="vllm/Qwen2.5-72B-Instruct")
response = await agent.run("你好，世界！")
print(response)
```

## 部署选项

### 单节点（单/多 GPU）

```bash
# 1x A100 80GB
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --dtype bfloat16 \
    --max-model-len 32768

# 4x A100 40GB（张量并行）
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --tensor-parallel-size 4 \
    --dtype bfloat16 \
    --max-model-len 32768
```

### 多节点（流水线并行）

```bash
# 节点 0（主节点）
vllm serve meta-llama/Llama-3.1-405B-Instruct \
    --tensor-parallel-size 8 \
    --pipeline-parallel-size 2 \
    --node-rank 0 \
    --master-addr <head-node-ip> \
    --master-port 29500

# 节点 1（工作节点）
vllm serve meta-llama/Llama-3.1-405B-Instruct \
    --tensor-parallel-size 8 \
    --pipeline-parallel-size 2 \
    --node-rank 1 \
    --master-addr <head-node-ip> \
    --master-port 29500
```

### Kubernetes 部署

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

## 认证

### 启用 API 密钥认证

```bash
vllm serve Qwen/Qwen2.5-72B-Instruct \
    --api-key sk-vllm-secret-key
```

### FeinnAgent 配置

```bash
# .env
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_API_KEY=sk-vllm-secret-key
```

## 性能调优

### 内存优化

```bash
vllm serve Qwen/Qwen2.5-72B-Instruct \
    --dtype bfloat16 \
    --quantization awq \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.95
```

### 吞吐量优化

```bash
vllm serve Qwen/Qwen2.5-72B-Instruct \
    --max-num-seqs 256 \
    --max-num-batched-tokens 32768 \
    --num-scheduler-steps 8
```

### 推荐模型

| 模型 | 大小 | 显存需求 | 使用场景 |
|------|------|----------|----------|
| Qwen2.5-7B-Instruct | 7B | ~16 GB | 开发、测试 |
| Qwen2.5-32B-Instruct | 32B | ~64 GB | 生产、通用任务 |
| Qwen2.5-72B-Instruct | 72B | ~144 GB | 复杂推理 |
| Llama-3.1-70B-Instruct | 70B | ~140 GB | 通用目的 |
| Llama-3.1-405B-Instruct | 405B | ~810 GB | 最大能力 |
| DeepSeek-V3 | 671B | ~1.3 TB | 高级推理 |

## 故障排除

### 内存不足

```bash
# 降低最大序列长度
vllm serve ... --max-model-len 8192

# 启用量化
vllm serve ... --quantization gptq

# 降低 GPU 内存利用率
vllm serve ... --gpu-memory-utilization 0.85
```

### 连接问题

```bash
# 测试 vLLM 端点
curl http://localhost:8000/v1/models

# 使用 FeinnAgent 测试
python -c "
from feinn_agent.providers import detect_provider
info = detect_provider('vllm/Qwen2.5-72B-Instruct')
print(f'Provider: {info.provider}')
print(f'Model: {info.model}')
"
```

### 响应缓慢

- 启用 CUDA graph: `--enforce-eager false`
- 调整批处理大小: `--max-num-seqs 512`
- 使用更快的 attention: `--attention-flash-attn`

## 高级配置

### 自定义聊天模板

```bash
vllm serve my-model \
    --chat-template /path/to/template.jinja
```

### 工具调用支持

vLLM 支持 OpenAI 兼容的工具调用：

```python
from feinn_agent import FeinnAgent

agent = FeinnAgent(
    model="vllm/Qwen2.5-72B-Instruct",
    tools=["Bash", "Read", "Write"]
)
```

### 负载均衡

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

## 安全最佳实践

1. **启用认证**: 生产环境始终使用 `--api-key`
2. **网络隔离**: 在私有网络/VPC 中运行 vLLM
3. **TLS 终止**: 使用反向代理（nginx/traefik）实现 HTTPS
4. **速率限制**: 在代理层实现速率限制
5. **监控**: 启用 Prometheus 指标 `--enable-metrics`

## 监控

```bash
# 启用 Prometheus 指标
vllm serve ... --enable-metrics --metrics-port 8001

# 指标可在 http://localhost:8001/metrics 访问
```

关键指标：
- `vllm:num_requests_running` - 当前请求数
- `vllm:gpu_cache_usage_perc` - GPU 缓存利用率
- `vllm:time_to_first_token_seconds` - TTFT 延迟
- `vllm:time_per_output_token_seconds` - TPOT 延迟
