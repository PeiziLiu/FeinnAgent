"""FeinnAgent multi-provider LLM abstraction layer.

Supports Anthropic, OpenAI, OpenAI-compatible endpoints (Gemini, Qwen,
DeepSeek, Moonshot, Ollama, vLLM, local), and custom providers.
All streaming is async, returning a uniform stream of typed events.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from .types import AssistantTurn, Message, Role, TextChunk, ThinkingChunk, ToolCall

logger = logging.getLogger(__name__)

# ── Provider registry ───────────────────────────────────────────────

_PROVIDER_RULES: list[tuple[str, str]] = [
    # (pattern, provider_name)
    (r"^claude", "anthropic"),
    (r"^anthropic/", "anthropic"),
    (r"^gpt", "openai"),
    (r"^o[1-4]", "openai"),
    (r"^openai/", "openai"),
    (r"^gemini", "gemini"),
    (r"^google/", "gemini"),
    (r"^qwen", "qwen"),
    (r"^deepseek", "deepseek"),
    (r"^kimi", "moonshot"),
    (r"^moonshot", "moonshot"),
    (r"^siliconflow/", "siliconflow"),
    (r"^openrouter/", "openrouter"),
    (r"^ollama/", "ollama"),
    (r"^vllm/", "vllm"),
    (r"^lmstudio/", "lmstudio"),
    (r"^custom/", "custom"),
]

_CONTEXT_LIMITS: dict[str, int] = {
    "anthropic": 200_000,
    "openai": 128_000,
    "azure": 128_000,
    "gemini": 1_000_000,
    "qwen": 1_000_000,
    "deepseek": 128_000,
    "moonshot": 128_000,
    "siliconflow": 128_000,
    "openrouter": 200_000,
    "ollama": 128_000,
    "vllm": 128_000,
    "lmstudio": 128_000,
    "custom": 128_000,
}

_OPENAI_COMPAT_PROVIDERS = {
    "openai",
    "azure",
    "gemini",
    "qwen",
    "deepseek",
    "moonshot",
    "siliconflow",
    "openrouter",
    "ollama",
    "vllm",
    "lmstudio",
    "custom",
}


@dataclass
class ProviderInfo:
    """Resolved provider details."""

    provider: str
    model: str  # actual model name sent to API (prefix stripped)
    context_limit: int


def detect_provider(model: str) -> ProviderInfo:
    """Auto-detect provider from model name prefix."""
    # Strip provider prefix: "anthropic/claude-..." → "claude-..."
    if "/" in model:
        prefix, rest = model.split("/", 1)
        for _, prov in _PROVIDER_RULES:
            if prefix.lower() == prov:
                return ProviderInfo(provider=prov, model=rest, context_limit=_CONTEXT_LIMITS.get(prov, 128_000))

    # Match by model name pattern
    for pattern, prov in _PROVIDER_RULES:
        if re.match(pattern, model, re.IGNORECASE):
            return ProviderInfo(provider=prov, model=model, context_limit=_CONTEXT_LIMITS.get(prov, 128_000))

    # Default: OpenAI-compatible with custom base URL
    return ProviderInfo(provider="custom", model=model, context_limit=128_000)


def get_base_url(provider: str, config: dict[str, Any]) -> str:
    """Return the base URL for a provider."""
    urls: dict[str, str] = {
        "openai": "https://api.openai.com/v1",
        "azure": "",  # Azure uses full deployment URL
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "siliconflow": "https://api.siliconflow.cn/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "ollama": "http://localhost:11434/v1",
        "vllm": "http://localhost:8000/v1",
        "lmstudio": "http://localhost:1234/v1",
    }
    if provider == "custom":
        return config.get("custom_base_url", os.environ.get("CUSTOM_BASE_URL", ""))
    if provider == "azure":
        return config.get("azure_base_url", os.environ.get("AZURE_OPENAI_URL", ""))
    if provider == "siliconflow":
        return config.get("siliconflow_base_url", os.environ.get("SILICONFLOW_BASE_URL", urls["siliconflow"]))
    if provider == "vllm":
        # vLLM supports custom base URL via config or environment
        return config.get("vllm_base_url", os.environ.get("VLLM_BASE_URL", urls["vllm"]))
    return urls.get(provider, "")


# ── Streaming entry point ───────────────────────────────────────────


async def stream(
    model: str,
    system: str,
    messages: list[Message],
    tool_schemas: list[dict[str, Any]],
    config: dict[str, Any],
) -> AsyncIterator[TextChunk | ThinkingChunk | AssistantTurn]:
    """Stream from LLM, yielding typed events regardless of provider."""
    info = detect_provider(model)
    logger.info(f"Streaming from provider: {info.provider}, model: {info.model}")
    logger.debug(f"Context limit: {info.context_limit}, messages: {len(messages)}, tools: {len(tool_schemas)}")

    if info.provider == "anthropic":
        async for event in _stream_anthropic(info, system, messages, tool_schemas, config):
            yield event
    else:
        async for event in _stream_openai_compat(info, system, messages, tool_schemas, config):
            yield event


# ── Anthropic native streaming ──────────────────────────────────────


async def _stream_anthropic(
    info: ProviderInfo,
    system: str,
    messages: list[Message],
    tool_schemas: list[dict[str, Any]],
    config: dict[str, Any],
) -> AsyncIterator[TextChunk | ThinkingChunk | AssistantTurn]:
    """Stream using the Anthropic SDK (native tool calling + thinking)."""
    logger.info(f"Starting Anthropic stream for model: {info.model}")
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.error("anthropic package not installed")
        raise ImportError("anthropic package required: pip install anthropic")

    api_key = config.get("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("Anthropic API key not configured")
        raise ValueError(
            "Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable or config.anthropic_api_key"
        )

    client = AsyncAnthropic(api_key=api_key)
    logger.debug("Anthropic client initialized")

    # Convert messages to Anthropic format
    api_messages, system_blocks = _to_anthropic_messages(messages, system)
    logger.debug(f"Converted {len(messages)} messages to Anthropic format")

    # Build request kwargs
    kwargs: dict[str, Any] = {
        "model": info.model,
        "max_tokens": config.get("max_tokens", 16384),
        "messages": api_messages,
        "system": system_blocks,
    }
    if tool_schemas:
        kwargs["tools"] = tool_schemas
        logger.debug(f"Added {len(tool_schemas)} tools to request")

    if config.get("thinking_enabled"):
        kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": config.get("thinking_budget", 10_000),
        }
        logger.debug("Thinking mode enabled")

    text_parts: list[str] = []
    thinking_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    input_tokens = 0
    output_tokens = 0

    logger.info("Sending request to Anthropic API")
    async with client.messages.stream(**kwargs) as stream_resp:
        async for event in stream_resp:
            if event.type == "message_start":
                usage = getattr(event.message, "usage", None)
                if usage:
                    input_tokens = getattr(usage, "input_tokens", 0)
            elif event.type == "content_block_delta":
                delta = event.delta
                if hasattr(delta, "text") and delta.text:
                    text_parts.append(delta.text)
                    yield TextChunk(text=delta.text)
                elif hasattr(delta, "thinking") and delta.thinking:
                    thinking_parts.append(delta.thinking)
                    yield ThinkingChunk(thinking=delta.thinking)
            elif event.type == "content_block_start":
                cb = event.content_block
                if hasattr(cb, "type") and cb.type == "tool_use":
                    tc = ToolCall(id=cb.id, name=cb.name, input={})
                    tool_calls.append(tc)
            elif event.type == "content_block_stop":
                pass  # tool input collected via input_json_delta
            elif event.type == "input_json_delta":
                if tool_calls and hasattr(event, "partial_json"):
                    pass  # partial input, collected in final message

        # Get final message for complete tool inputs + usage
        final = await stream_resp.get_final_message()
        output_tokens = getattr(final.usage, "output_tokens", 0) if final.usage else 0

        # Reconstruct tool calls from final message
        tool_calls = []
        for block in final.content:
            if block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

    logger.info(
        f"Anthropic stream complete: input_tokens={input_tokens}, output_tokens={output_tokens}, tool_calls={len(tool_calls)}"
    )
    yield AssistantTurn(
        text="".join(text_parts),
        reasoning="".join(thinking_parts),
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


# ── OpenAI-compatible streaming ─────────────────────────────────────


@dataclass
class _OAIToolCallAccum:
    """Accumulator for a streaming tool call from OpenAI-compatible APIs."""

    id: str = ""
    name: str = ""
    arguments: str = ""


async def _stream_openai_compat(
    info: ProviderInfo,
    system: str,
    messages: list[Message],
    tool_schemas: list[dict[str, Any]],
    config: dict[str, Any],
) -> AsyncIterator[TextChunk | ThinkingChunk | AssistantTurn]:
    """Stream using any OpenAI-compatible endpoint."""
    logger.info(f"Starting OpenAI-compatible stream for provider: {info.provider}, model: {info.model}")
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.error("openai package not installed")
        raise ImportError("openai package required: pip install openai")

    base_url = get_base_url(info.provider, config)
    logger.debug(f"Using base_url: {base_url[:50]}..." if base_url else "No base_url configured")
    api_key = config.get(f"{info.provider}_api_key", "") or "unused"

    # vLLM may have API key authentication enabled
    if info.provider == "vllm":
        api_key = config.get("vllm_api_key", os.environ.get("VLLM_API_KEY", "unused"))
        logger.debug(f"vLLM API key configured: {bool(api_key and api_key != 'unused')}")

    # Azure OpenAI
    if info.provider == "azure":
        api_key = config.get("azure_api_key", os.environ.get("AZURE_OPENAI_API_KEY", ""))
        if not api_key:
            logger.error("Azure OpenAI API key not configured")
            raise ValueError("Azure OpenAI API key not configured")

    # SiliconFlow
    if info.provider == "siliconflow":
        api_key = config.get("siliconflow_api_key", "") or os.environ.get("SILICONFLOW_API_KEY", "")
        if not api_key:
            logger.error("SiliconFlow API key not configured")
            raise ValueError(
                "SiliconFlow API key not configured. Set SILICONFLOW_API_KEY environment variable or config.siliconflow_api_key"
            )

    # OpenRouter
    if info.provider == "openrouter":
        api_key = config.get("openrouter_api_key", "") or os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.error("OpenRouter API key not configured")
            raise ValueError(
                "OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable or config.openrouter_api_key"
            )
        # OpenRouter requires specific headers
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None,
            default_headers={
                "HTTP-Referer": "https://feinn-agent.local",
                "X-Title": "FeinnAgent",
            },
        )
    else:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url if base_url else None)
    logger.debug("OpenAI client initialized")

    # Convert messages to OpenAI format
    api_messages = _to_openai_messages(messages, system)
    logger.debug(f"Converted {len(messages)} messages to OpenAI format")

    kwargs: dict[str, Any] = {
        "model": info.model,
        "messages": api_messages,
        "stream": True,
    }

    # SiliconFlow doesn't accept max_tokens in the same way
    if info.provider != "siliconflow":
        kwargs["max_tokens"] = config.get("max_tokens", 16384)

    if tool_schemas:
        kwargs["tools"] = tool_schemas
        logger.debug(f"Added {len(tool_schemas)} tools to request")

    text_parts: list[str] = []
    tc_accum: dict[int, _OAIToolCallAccum] = {}
    input_tokens = 0
    output_tokens = 0

    logger.info(f"Sending request to {info.provider} API")
    response = await client.chat.completions.create(**kwargs)

    async for chunk in response:
        if not chunk.choices:
            # Usage info may come in a final chunk with no choices
            if hasattr(chunk, "usage") and chunk.usage:
                input_tokens = getattr(chunk.usage, "prompt_tokens", 0)
                output_tokens = getattr(chunk.usage, "completion_tokens", 0)
            continue

        choice = chunk.choices[0]
        delta = choice.delta

        if hasattr(delta, "content") and delta.content:
            text_parts.append(delta.content)
            yield TextChunk(text=delta.content)

        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tc_accum:
                    tc_accum[idx] = _OAIToolCallAccum()
                acc = tc_accum[idx]
                if tc_delta.id:
                    acc.id = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        acc.name = tc_delta.function.name
                    if tc_delta.function.arguments:
                        acc.arguments += tc_delta.function.arguments

        if hasattr(chunk, "usage") and chunk.usage:
            input_tokens = getattr(chunk.usage, "prompt_tokens", 0) or input_tokens
            output_tokens = getattr(chunk.usage, "completion_tokens", 0) or output_tokens

    # Build final tool calls
    tool_calls: list[ToolCall] = []
    for idx in sorted(tc_accum):
        acc = tc_accum[idx]
        try:
            args = json.loads(acc.arguments) if acc.arguments else {}
        except json.JSONDecodeError:
            args = {"raw": acc.arguments}
        tool_calls.append(ToolCall(id=acc.id, name=acc.name, input=args))

    logger.info(
        f"OpenAI-compatible stream complete: input_tokens={input_tokens}, output_tokens={output_tokens}, tool_calls={len(tool_calls)}"
    )
    yield AssistantTurn(
        text="".join(text_parts),
        reasoning="",
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


# ── Message format converters ───────────────────────────────────────


def _to_anthropic_messages(messages: list[Message], system: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert neutral messages to Anthropic API format."""
    system_blocks: list[dict[str, Any]] = [{"type": "text", "text": system}]
    api_messages: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == Role.SYSTEM:
            system_blocks.append({"type": "text", "text": msg.content})
            continue

        if msg.role == Role.USER:
            content: list[dict[str, Any]] = []
            if msg.images:
                for img in msg.images:
                    content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": img["media_type"],
                                "data": img["data"],
                            },
                        }
                    )
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            api_messages.append({"role": "user", "content": content or msg.content})

        elif msg.role == Role.ASSISTANT:
            content_blocks: list[dict[str, Any]] = []
            if msg.reasoning:
                content_blocks.append({"type": "thinking", "thinking": msg.reasoning})
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    }
                )
            api_messages.append({"role": "assistant", "content": content_blocks})

        elif msg.role == Role.TOOL:
            api_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                }
            )

    return api_messages, system_blocks


def _to_openai_messages(messages: list[Message], system: str) -> list[dict[str, Any]]:
    """Convert neutral messages to OpenAI-compatible format."""
    api_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

    for msg in messages:
        if msg.role == Role.SYSTEM:
            api_messages.append({"role": "system", "content": msg.content})
        elif msg.role == Role.USER:
            content = msg.content
            if msg.images:
                parts: list[dict[str, Any]] = [{"type": "text", "text": content}]
                for img in msg.images:
                    parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{img['media_type']};base64,{img['data']}"},
                        }
                    )
                content = parts  # type: ignore[assignment]
            api_messages.append({"role": "user", "content": content})
        elif msg.role == Role.ASSISTANT:
            d: dict[str, Any] = {"role": "assistant"}
            if msg.content:
                d["content"] = msg.content
            if msg.tool_calls:
                d["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.input)},
                    }
                    for tc in msg.tool_calls
                ]
            api_messages.append(d)
        elif msg.role == Role.TOOL:
            api_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                }
            )

    return api_messages


# ── Cost calculation ────────────────────────────────────────────────

_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_1M, output_per_1M)
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-3.5": (0.80, 4.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.0),
    "deepseek-v3": (0.27, 1.10),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a given model and token usage."""
    for prefix, (in_price, out_price) in _PRICING.items():
        if prefix in model.lower():
            return (input_tokens * in_price + output_tokens * out_price) / 1_000_000
    return 0.0
