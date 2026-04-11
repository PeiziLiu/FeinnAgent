"""FeinnAgent FastAPI server — enterprise-grade HTTP API.

Supports:
- Multi-session concurrent requests
- SSE streaming for real-time responses
- Session persistence and retrieval
- Health checks and metrics
- OpenAPI spec auto-generated
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import FeinnAgent
from .config import load_config
from .context import build_system_prompt
from .mcp import init_mcp, shutdown_mcp
from .types import (
    AgentDone,
    AgentEvent,
    AgentState,
    TextChunk,
    ThinkingChunk,
    ToolEnd,
    ToolStart,
    TurnDone,
)

logger = logging.getLogger(__name__)

# ── Pydantic models ─────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for /chat endpoint."""

    message: str
    session_id: str | None = None
    model: str | None = None
    images: list[dict[str, str]] | None = None
    stream: bool = True


class ChatResponse(BaseModel):
    """Non-streaming response."""

    session_id: str
    response: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    turn_count: int = 0


class SessionInfo(BaseModel):
    session_id: str
    turn_count: int
    total_input_tokens: int
    total_output_tokens: int


class HealthResponse(BaseModel):
    status: str = "ok"
    active_sessions: int = 0


# ── Session store ───────────────────────────────────────────────────

_sessions: dict[str, tuple[FeinnAgent, dict[str, Any]]] = {}


def _get_or_create_session(
    session_id: str | None, config: dict[str, Any]
) -> tuple[str, FeinnAgent, dict[str, Any]]:
    """Get existing session or create new one. Returns (session_id, agent, config)."""
    if session_id and session_id in _sessions:
        agent, cfg = _sessions[session_id]
        return session_id, agent, cfg

    new_id = session_id or uuid.uuid4().hex[:12]
    state = AgentState(session_id=new_id)
    cfg = dict(config)
    system = build_system_prompt(cfg)
    agent = FeinnAgent(config=cfg, system_prompt=system, state=state)
    _sessions[new_id] = (agent, cfg)
    return new_id, agent, cfg


# ── Lifespan ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    config = load_config()
    # Initialize MCP servers
    init_mcp(config)
    logger.info("FeinnAgent server started")
    yield
    # Cleanup
    shutdown_mcp()
    _sessions.clear()
    logger.info("FeinnAgent server stopped")


# ── App factory ─────────────────────────────────────────────────────


def create_app(config: dict[str, Any] | None = None) -> FastAPI:
    """Create the FastAPI application."""
    cfg = config or load_config()

    app = FastAPI(
        title="FeinnAgent",
        description="Enterprise-grade async AI agent API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store config in app state
    app.state.config = cfg

    # ── Routes ──────────────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(active_sessions=len(_sessions))

    @app.post("/chat", response_class=StreamingResponse)
    async def chat(req: ChatRequest):
        """Main chat endpoint. Returns SSE stream or JSON response."""
        config = app.state.config
        if req.model:
            config = dict(config)
            config["model"] = req.model

        session_id, agent, _ = _get_or_create_session(req.session_id, config)

        if req.stream:
            return StreamingResponse(
                _stream_response(agent, req.message, req.images, session_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Session-Id": session_id,
                },
            )
        else:
            # Non-streaming: collect full response
            response_text = []
            total_in = total_out = turns = 0
            async for event in agent.run(req.message, images=req.images or []):
                if isinstance(event, TextChunk):
                    response_text.append(event.text)
                elif isinstance(event, AgentDone):
                    total_in = event.total_input_tokens
                    total_out = event.total_output_tokens
                    turns = event.turn_count

            return ChatResponse(
                session_id=session_id,
                response="".join(response_text),
                total_input_tokens=total_in,
                total_output_tokens=total_out,
                turn_count=turns,
            )

    @app.get("/sessions", response_model=list[SessionInfo])
    async def list_sessions():
        """List all active sessions."""
        result = []
        for sid, (agent, _) in _sessions.items():
            result.append(
                SessionInfo(
                    session_id=sid,
                    turn_count=agent.state.turn_count,
                    total_input_tokens=agent.state.total_input_tokens,
                    total_output_tokens=agent.state.total_output_tokens,
                )
            )
        return result

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str):
        """Delete a session."""
        if session_id in _sessions:
            del _sessions[session_id]
            return {"status": "deleted"}
        raise HTTPException(status_code=404, detail="Session not found")

    @app.get("/sessions/{session_id}/history")
    async def get_session_history(session_id: str):
        """Get conversation history for a session."""
        if session_id not in _sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        agent, _ = _sessions[session_id]
        return {
            "session_id": session_id,
            "messages": [m.to_dict() for m in agent.state.messages],
        }

    return app


# ── SSE streaming helper ────────────────────────────────────────────


async def _stream_response(
    agent: FeinnAgent,
    message: str,
    images: list[dict[str, str]] | None,
    session_id: str,
) -> AsyncIterator[bytes]:
    """Yield SSE-formatted events from the agent loop."""
    try:
        async for event in agent.run(message, images=images or []):
            sse_data = _event_to_sse(event, session_id)
            if sse_data:
                yield f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n".encode()
    except Exception as e:
        error_data = {"type": "error", "error": str(e), "session_id": session_id}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n".encode()
    finally:
        done_data = {"type": "done", "session_id": session_id}
        yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n".encode()


def _event_to_sse(event: AgentEvent, session_id: str) -> dict[str, Any] | None:
    """Convert an AgentEvent to an SSE data dict."""
    if isinstance(event, TextChunk):
        return {"type": "text", "text": event.text, "session_id": session_id}
    elif isinstance(event, ThinkingChunk):
        return {"type": "thinking", "thinking": event.thinking, "session_id": session_id}
    elif isinstance(event, ToolStart):
        return {
            "type": "tool_start",
            "name": event.name,
            "inputs": event.inputs,
            "session_id": session_id,
        }
    elif isinstance(event, ToolEnd):
        return {"type": "tool_end", "name": event.name, "session_id": session_id}
    elif isinstance(event, TurnDone):
        return {
            "type": "turn_done",
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "session_id": session_id,
        }
    elif isinstance(event, AgentDone):
        return {
            "type": "agent_done",
            "total_input_tokens": event.total_input_tokens,
            "total_output_tokens": event.total_output_tokens,
            "turn_count": event.turn_count,
            "session_id": session_id,
        }
    return None


# ── Entry point ─────────────────────────────────────────────────────


def run_server(config: dict[str, Any] | None = None) -> None:
    """Run the FeinnAgent HTTP server."""
    import uvicorn

    cfg = config or load_config()
    app = create_app(cfg)

    uvicorn.run(
        app,
        host=cfg.get("server_host", "0.0.0.0"),
        port=cfg.get("server_port", 8000),
        log_level=cfg.get("log_level", "info").lower(),
    )
