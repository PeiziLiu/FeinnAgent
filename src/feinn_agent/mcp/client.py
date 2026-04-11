"""FeinnAgent MCP (Model Context Protocol) client.

Supports stdio, SSE, and HTTP transports for connecting to MCP servers.
Tools are auto-discovered and registered in the tool registry.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..tools.registry import deregister, register
from ..types import ToolDef

logger = logging.getLogger(__name__)


# ── Transport types ─────────────────────────────────────────────────


class MCPTransport(StrEnum):
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    transport: MCPTransport = MCPTransport.STDIO
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    disabled: bool = False


# ── Stdio transport ─────────────────────────────────────────────────


class StdioTransport:
    """JSON-RPC 2.0 over subprocess stdin/stdout."""

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._process: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._pending: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def start(self) -> None:
        """Spawn the subprocess and start the reader thread."""
        env = dict(os.environ)
        env.update(self._config.env)
        # Filter out None values
        env = {k: v for k, v in env.items() if v is not None}

        self._process = subprocess.Popen(
            [self._config.command] + self._config.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _read_loop(self) -> None:
        """Background thread that reads JSON-RPC responses from stdout."""
        if not self._process or not self._process.stdout:
            return

        for line in self._process.stdout:
            try:
                msg = json.loads(line)
                req_id = msg.get("id")
                if req_id is not None:
                    with self._lock:
                        if req_id in self._pending:
                            self._pending[req_id]["result"] = msg
                            self._pending[req_id]["event"].set()
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Send a JSON-RPC request and wait for response."""
        if not self._process or not self._process.stdin:
            return None

        with self._lock:
            req_id = self._next_id
            self._next_id += 1

        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params:
            msg["params"] = params

        event = threading.Event()
        with self._lock:
            self._pending[req_id] = {"event": event, "result": None}

        line = (json.dumps(msg) + "\n").encode("utf-8")
        self._process.stdin.write(line)
        self._process.stdin.flush()

        event.wait(timeout=self._config.timeout)
        with self._lock:
            entry = self._pending.pop(req_id, None)

        return entry["result"] if entry else None

    def stop(self) -> None:
        """Terminate the subprocess."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None


# ── MCP client ──────────────────────────────────────────────────────


class MCPClient:
    """Manages connections to MCP servers and registers their tools."""

    def __init__(self) -> None:
        self._servers: dict[str, StdioTransport] = {}
        self._registered_tools: dict[str, str] = {}  # qualified_name → server_name

    def load_config(self, config: dict[str, Any]) -> None:
        """Load MCP server configs and connect."""
        mcp_config = config.get("mcp_servers", {})
        if isinstance(mcp_config, str):
            # Could be a path to a config file
            path = Path(mcp_config).expanduser()
            if path.exists():
                mcp_config = json.loads(path.read_text(encoding="utf-8"))
            else:
                return

        for server_name, server_cfg in mcp_config.items():
            if server_cfg.get("disabled", False):
                continue
            self.add_server(server_name, server_cfg)

    def add_server(self, name: str, cfg: dict[str, Any]) -> None:
        """Add and connect to an MCP server."""
        transport_str = cfg.get("type", cfg.get("transport", "stdio"))
        transport = MCPTransport(transport_str)

        server_config = MCPServerConfig(
            name=name,
            transport=transport,
            command=cfg.get("command", ""),
            args=cfg.get("args", []),
            env=cfg.get("env", {}),
            url=cfg.get("url", ""),
            headers=cfg.get("headers", {}),
            timeout=cfg.get("timeout", 30),
            disabled=cfg.get("disabled", False),
        )

        if server_config.disabled:
            return

        if transport == MCPTransport.STDIO:
            self._connect_stdio(name, server_config)
        elif transport in (MCPTransport.SSE, MCPTransport.HTTP):
            self._connect_http(name, server_config)
        else:
            logger.warning("Unsupported MCP transport: %s", transport)

    def _connect_stdio(self, name: str, config: MCPServerConfig) -> None:
        """Connect to a stdio MCP server and register its tools."""
        transport = StdioTransport(config)
        try:
            transport.start()
            self._servers[name] = transport

            # Initialize
            init_result = transport.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "feinn-agent", "version": "0.1.0"},
                },
            )

            if init_result is None:
                logger.warning("MCP server %s: initialization failed", name)
                return

            # Discover tools
            tools_result = transport.request("tools/list", {})
            if tools_result and "result" in tools_result:
                tools = tools_result["result"].get("tools", [])
                for tool_info in tools:
                    self._register_mcp_tool(name, tool_info, transport)

            logger.info(
                "MCP server %s: connected, %d tools registered",
                name,
                len(tools_result.get("result", {}).get("tools", [])) if tools_result else 0,
            )

        except Exception as e:
            logger.warning("Failed to connect MCP server %s: %s", name, e)

    def _connect_http(self, name: str, config: MCPServerConfig) -> None:
        """Connect to an HTTP/SSE MCP server (placeholder for future)."""
        logger.info("HTTP/SSE MCP transport not yet implemented for %s", name)

    def _register_mcp_tool(
        self,
        server_name: str,
        tool_info: dict[str, Any],
        transport: StdioTransport,
    ) -> None:
        """Register an MCP tool in the global tool registry."""
        tool_name = tool_info.get("name", "unknown")
        qualified_name = f"mcp__{server_name}__{tool_name}"

        async def mcp_handler(params: dict[str, Any], config: dict[str, Any]) -> str:
            result = transport.request(
                "tools/call",
                {
                    "name": tool_name,
                    "arguments": params,
                },
            )
            if result and "result" in result:
                content = result["result"].get("content", [])
                parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(item["text"])
                    elif isinstance(item, str):
                        parts.append(item)
                return "\n".join(parts) if parts else json.dumps(result["result"])
            return json.dumps(result) if result else "No result from MCP server"

        register(
            ToolDef(
                name=qualified_name,
                description=f"[MCP:{server_name}] {tool_info.get('description', '')}",
                input_schema=tool_info.get("inputSchema", {"type": "object", "properties": {}}),
                handler=mcp_handler,
                read_only=True,
                concurrent_safe=True,
            )
        )
        self._registered_tools[qualified_name] = server_name

    def stop_all(self) -> None:
        """Disconnect from all MCP servers."""
        # Deregister MCP tools
        for qualified_name in list(self._registered_tools):
            deregister(qualified_name)
        self._registered_tools.clear()

        # Stop transports
        for name, transport in self._servers.items():
            transport.stop()
        self._servers.clear()


# ── Module-level client ─────────────────────────────────────────────

_client: MCPClient | None = None


def get_client() -> MCPClient:
    global _client
    if _client is None:
        _client = MCPClient()
    return _client


def init_mcp(config: dict[str, Any]) -> None:
    """Initialize MCP client from config and connect to servers."""
    client = get_client()
    client.load_config(config)


def shutdown_mcp() -> None:
    """Shutdown all MCP connections."""
    global _client
    if _client:
        _client.stop_all()
        _client = None
