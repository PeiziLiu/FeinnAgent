"""Tests for FeinnAgent server functionality."""

import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock

from fastapi.testclient import TestClient
from feinn_agent.server import create_app


class TestServer(unittest.TestCase):
    """Test FastAPI server functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear existing sessions
        from feinn_agent.server import _sessions
        _sessions.clear()
        
        app = create_app()
        self.client = TestClient(app)

    def test_health_endpoint(self):
        """Test health endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["active_sessions"], 0)

    @patch('feinn_agent.server.FeinnAgent')
    def test_chat_endpoint(self, mock_agent_class):
        """Test chat endpoint."""
        mock_agent = Mock()
        mock_agent.run.return_value = []
        mock_agent_class.return_value = mock_agent

        response = self.client.post(
            "/chat",
            json={
                "message": "Hello",
                "model": "gpt-4o"
            }
        )

        self.assertEqual(response.status_code, 200)
        mock_agent.run.assert_called_once()

    @patch('feinn_agent.server.FeinnAgent')
    def test_chat_endpoint_with_images(self, mock_agent_class):
        """Test chat endpoint with images."""
        mock_agent = Mock()
        mock_agent.run.return_value = []
        mock_agent_class.return_value = mock_agent

        response = self.client.post(
            "/chat",
            json={
                "message": "What's in this image?",
                "images": [
                    {"url": "data:image/jpeg;base64,test"}
                ],
                "model": "gpt-4o"
            }
        )

        self.assertEqual(response.status_code, 200)
        mock_agent.run.assert_called_once()

    def test_chat_endpoint_missing_message(self):
        """Test chat endpoint with missing message."""
        response = self.client.post(
            "/chat",
            json={
                "model": "gpt-4o"
            }
        )

        self.assertEqual(response.status_code, 422)

    def test_list_sessions_endpoint(self):
        """Test list sessions endpoint."""
        response = self.client.get("/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_delete_session_endpoint(self):
        """Test delete session endpoint."""
        # Try to delete a non-existent session
        response = self.client.delete("/sessions/test-session")
        self.assertEqual(response.status_code, 404)

    def test_get_session_history_endpoint(self):
        """Test get session history endpoint."""
        # Try to get history for a non-existent session
        response = self.client.get("/sessions/test-session/history")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
