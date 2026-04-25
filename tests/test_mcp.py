"""Tests for FeinnAgent MCP client functionality."""

import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.mcp.client import MCPClient, MCPServerConfig


class TestMCPServerConfig(unittest.TestCase):
    """Test MCPServerConfig functionality."""

    def test_server_config_creation(self):
        """Test MCPServerConfig creation."""
        config = MCPServerConfig(
            name="test_server",
            command="test_script.py",
            args=["--verbose"],
        )
        self.assertEqual(config.name, "test_server")
        self.assertEqual(config.command, "test_script.py")
        self.assertEqual(config.args, ["--verbose"])


class TestMCPClient(unittest.TestCase):
    """Test MCPClient functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = MCPClient()

    def test_load_config(self):
        """Test loading MCP config."""
        config = {
            "mcp_servers": {
                "test_server": {
                    "command": "test_script.py",
                    "args": ["--test"],
                    "disabled": False
                }
            }
        }
        self.client.load_config(config)

    def test_add_server(self):
        """Test adding an MCP server."""
        server_config = {
            "command": "test_script.py",
            "args": ["--test"],
            "disabled": False
        }
        self.client.add_server("test_server", server_config)

    def test_stop_all(self):
        """Test stopping all MCP connections."""
        # This should not raise any exceptions
        self.client.stop_all()


if __name__ == "__main__":
    unittest.main()
