"""Tests for FeinnAgent browser tools."""

import asyncio
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.tools.browser import (
    _validate_url,
    _is_private_url,
    _get_browser_provider,
    _get_or_create_session,
    _execute_browser_command,
    cleanup_browser,
    cleanup_all_browsers,
    _browser_navigate,
    _browser_snapshot,
    _browser_click,
    _browser_type,
    _browser_scroll,
    _browser_back,
    _browser_press,
    _browser_get_images,
)
from feinn_agent.tools.browser_providers.local import LocalBrowserProvider
from feinn_agent.tools.browser_providers.browserbase import BrowserbaseProvider
from feinn_agent.tools.browser_providers.browseruse import BrowserUseProvider
from feinn_agent.tools.browser_providers.firecrawl import FirecrawlProvider


class TestBrowserTools(unittest.TestCase):
    """Test browser tools functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing sessions
        from feinn_agent.tools.browser import _active_sessions, _session_last_activity
        _active_sessions.clear()
        _session_last_activity.clear()
        
        # Reset provider cache for each test
        import feinn_agent.tools.browser
        feinn_agent.tools.browser._cached_provider = None
        feinn_agent.tools.browser._provider_resolved = False

    def test_is_private_url(self):
        """Test private URL detection."""
        # Test private URLs
        self.assertTrue(_is_private_url("http://localhost:8080"))
        self.assertTrue(_is_private_url("http://127.0.0.1"))
        self.assertTrue(_is_private_url("http://192.168.1.1"))
        self.assertTrue(_is_private_url("http://10.0.0.1"))
        self.assertTrue(_is_private_url("http://example.local"))
        
        # Test public URLs
        self.assertFalse(_is_private_url("http://example.com"))
        self.assertFalse(_is_private_url("https://google.com"))
        self.assertFalse(_is_private_url("http://1.1.1.1"))

    def test_validate_url(self):
        """Test URL validation."""
        # Test public URL
        self.assertTrue(_validate_url("http://example.com"))
        
        # Test private URL with allow_private_urls=True
        with patch('feinn_agent.tools.browser._allow_private_urls', return_value=True):
            self.assertTrue(_validate_url("http://localhost:8080"))
        
        # Test private URL with allow_private_urls=False
        with patch('feinn_agent.tools.browser._allow_private_urls', return_value=False):
            with self.assertRaises(ValueError):
                _validate_url("http://localhost:8080")

    def test_get_browser_provider_local(self):
        """Test getting local browser provider."""
        # Test with no environment variables
        with patch.dict(os.environ, {}, clear=True):
            provider = _get_browser_provider()
            self.assertIsInstance(provider, LocalBrowserProvider)

    def test_get_browser_provider_browserbase(self):
        """Test getting Browserbase provider."""
        # Test with Browserbase credentials
        with patch.dict(os.environ, {
            "BROWSERBASE_API_KEY": "test_key",
            "BROWSERBASE_PROJECT_ID": "test_project"
        }):
            provider = _get_browser_provider()
            self.assertIsInstance(provider, BrowserbaseProvider)

    def test_get_browser_provider_browseruse(self):
        """Test getting Browser Use provider."""
        # Test with Browser Use credentials
        with patch.dict(os.environ, {
            "BROWSER_USE_API_KEY": "test_key"
        }):
            provider = _get_browser_provider()
            self.assertIsInstance(provider, BrowserUseProvider)

    def test_get_browser_provider_firecrawl(self):
        """Test getting Firecrawl provider."""
        # Test with Firecrawl credentials
        with patch.dict(os.environ, {
            "FIRECRAWL_API_KEY": "test_key"
        }):
            provider = _get_browser_provider()
            self.assertIsInstance(provider, FirecrawlProvider)

    @patch('feinn_agent.tools.browser._get_browser_provider')
    async def test_get_or_create_session(self, mock_get_provider):
        """Test session creation."""
        # Create mock provider
        mock_provider = Mock()
        mock_provider.create_session.return_value = {
            "session_name": "test_session",
            "session_id": "test_session_id",
            "features": {"local": True}
        }
        mock_get_provider.return_value = mock_provider
        
        # Test session creation
        session = await _get_or_create_session("test_task")
        self.assertEqual(session["session_id"], "test_session_id")
        mock_provider.create_session.assert_called_once_with("test_task")

    @patch('feinn_agent.tools.browser._get_or_create_session')
    @patch('feinn_agent.tools.browser._get_browser_provider')
    async def test_execute_browser_command(self, mock_get_provider, mock_get_session):
        """Test browser command execution."""
        # Create mock objects
        mock_session = {
            "session_id": "test_session_id"
        }
        mock_provider = Mock()
        mock_provider.execute_command.return_value = "Command executed successfully"
        
        mock_get_session.return_value = mock_session
        mock_get_provider.return_value = mock_provider
        
        # Test command execution
        result = await _execute_browser_command("test_task", "navigate", url="http://example.com")
        self.assertEqual(result, "Command executed successfully")
        mock_provider.execute_command.assert_called_once_with(
            "test_session_id", "navigate", url="http://example.com"
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_navigate(self, mock_execute):
        """Test browser_navigate tool."""
        mock_execute.return_value = "Navigated to http://example.com"
        
        result = await _browser_navigate(
            {"url": "http://example.com"}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Navigated to http://example.com")
        mock_execute.assert_called_once_with(
            "test_task", "navigate", url="http://example.com"
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_snapshot(self, mock_execute):
        """Test browser_snapshot tool."""
        mock_execute.return_value = "Page snapshot content"
        
        result = await _browser_snapshot(
            {"full": True}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Page snapshot content")
        mock_execute.assert_called_once_with(
            "test_task", "snapshot", full=True
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_click(self, mock_execute):
        """Test browser_click tool."""
        mock_execute.return_value = "Clicked on @e5"
        
        result = await _browser_click(
            {"ref": "@e5"}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Clicked on @e5")
        mock_execute.assert_called_once_with(
            "test_task", "click", ref="@e5"
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_type(self, mock_execute):
        """Test browser_type tool."""
        mock_execute.return_value = "Typed 'test' into @e3"
        
        result = await _browser_type(
            {"ref": "@e3", "text": "test"}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Typed 'test' into @e3")
        mock_execute.assert_called_once_with(
            "test_task", "type", ref="@e3", text="test"
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_scroll(self, mock_execute):
        """Test browser_scroll tool."""
        mock_execute.return_value = "Scrolled down"
        
        result = await _browser_scroll(
            {"direction": "down"}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Scrolled down")
        mock_execute.assert_called_once_with(
            "test_task", "scroll", direction="down"
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_back(self, mock_execute):
        """Test browser_back tool."""
        mock_execute.return_value = "Navigated back"
        
        result = await _browser_back(
            {}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Navigated back")
        mock_execute.assert_called_once_with(
            "test_task", "back"
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_press(self, mock_execute):
        """Test browser_press tool."""
        mock_execute.return_value = "Pressed Enter"
        
        result = await _browser_press(
            {"key": "Enter"}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Pressed Enter")
        mock_execute.assert_called_once_with(
            "test_task", "press", key="Enter"
        )

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_get_images(self, mock_execute):
        """Test browser_get_images tool."""
        mock_execute.return_value = "Image list"
        
        result = await _browser_get_images(
            {}, 
            {"task_id": "test_task"}
        )
        
        self.assertEqual(result, "Image list")
        mock_execute.assert_called_once_with(
            "test_task", "get_images"
        )

    @patch('feinn_agent.tools.browser._get_browser_provider')
    async def test_cleanup_browser(self, mock_get_provider):
        """Test browser cleanup."""
        # Create mock provider
        mock_provider = Mock()
        mock_provider.close_session.return_value = True
        mock_get_provider.return_value = mock_provider
        
        # Add test session
        from feinn_agent.tools.browser import _active_sessions
        _active_sessions["test_task"] = {
            "session_id": "test_session_id"
        }
        
        # Test cleanup
        success = await cleanup_browser("test_task")
        self.assertTrue(success)
        mock_provider.close_session.assert_called_once_with("test_session_id")
        self.assertNotIn("test_task", _active_sessions)

    @patch('feinn_agent.tools.browser.cleanup_browser')
    async def test_cleanup_all_browsers(self, mock_cleanup):
        """Test cleanup of all browsers."""
        mock_cleanup.return_value = True
        
        # Add test sessions
        from feinn_agent.tools.browser import _active_sessions
        _active_sessions["task1"] = {"session_id": "session1"}
        _active_sessions["task2"] = {"session_id": "session2"}
        
        # Test cleanup
        await cleanup_all_browsers()
        self.assertEqual(mock_cleanup.call_count, 2)

    def test_browser_navigate_missing_url(self):
        """Test browser_navigate with missing URL."""
        async def test_missing_url():
            result = await _browser_navigate({}, {"task_id": "test_task"})
            self.assertEqual(result, "Error: url is required")
        
        asyncio.run(test_missing_url())

    def test_browser_click_missing_ref(self):
        """Test browser_click with missing ref."""
        async def test_missing_ref():
            result = await _browser_click({}, {"task_id": "test_task"})
            self.assertEqual(result, "Error: ref is required")
        
        asyncio.run(test_missing_ref())

    def test_browser_type_missing_ref(self):
        """Test browser_type with missing ref."""
        async def test_missing_ref():
            result = await _browser_type({"text": "test"}, {"task_id": "test_task"})
            self.assertEqual(result, "Error: ref is required")
        
        asyncio.run(test_missing_ref())

    def test_browser_press_missing_key(self):
        """Test browser_press with missing key."""
        async def test_missing_key():
            result = await _browser_press({}, {"task_id": "test_task"})
            self.assertEqual(result, "Error: key is required")
        
        asyncio.run(test_missing_key())

    def test_browser_scroll_invalid_direction(self):
        """Test browser_scroll with invalid direction."""
        async def test_invalid_direction():
            result = await _browser_scroll({"direction": "left"}, {"task_id": "test_task"})
            self.assertEqual(result, "Error: direction must be 'up' or 'down'")
        
        asyncio.run(test_invalid_direction())

    @patch('feinn_agent.tools.browser._execute_browser_command')
    async def test_browser_workflow_integration(self):
        """Test complete browser workflow integration."""
        # Mock execute command to return different results for different commands
        def mock_execute(task_id, command, **kwargs):
            if command == "navigate":
                return f"Navigated to {kwargs.get('url')}"
            elif command == "snapshot":
                return "Page snapshot with elements: @e1, @e2, @e3"
            elif command == "click":
                return f"Clicked on {kwargs.get('ref')}"
            elif command == "type":
                return f"Typed '{kwargs.get('text')}' into {kwargs.get('ref')}"
            elif command == "submit":
                return "Form submitted successfully"
            return "Command executed"
        
        with patch('feinn_agent.tools.browser._execute_browser_command', side_effect=mock_execute):
            # Test complete workflow
            result1 = await _browser_navigate({"url": "https://example.com"}, {"task_id": "test_task"})
            self.assertEqual(result1, "Navigated to https://example.com")
            
            result2 = await _browser_snapshot({"full": False}, {"task_id": "test_task"})
            self.assertEqual(result2, "Page snapshot with elements: @e1, @e2, @e3")
            
            result3 = await _browser_click({"ref": "@e1"}, {"task_id": "test_task"})
            self.assertEqual(result3, "Clicked on @e1")
            
            result4 = await _browser_type({"ref": "@e2", "text": "test"}, {"task_id": "test_task"})
            self.assertEqual(result4, "Typed 'test' into @e2")

    async def test_concurrent_sessions(self):
        """Test multiple concurrent browser sessions."""
        # Create mock provider
        mock_provider = Mock()
        mock_provider.create_session.side_effect = [
            {"session_id": "session1"},
            {"session_id": "session2"}
        ]
        mock_provider.execute_command.return_value = "Command executed"
        
        with patch('feinn_agent.tools.browser._get_browser_provider', return_value=mock_provider):
            # Create two sessions
            session1 = await _get_or_create_session("task1")
            session2 = await _get_or_create_session("task2")
            
            self.assertEqual(session1["session_id"], "session1")
            self.assertEqual(session2["session_id"], "session2")
            
            # Verify both sessions exist
            from feinn_agent.tools.browser import _active_sessions
            self.assertIn("task1", _active_sessions)
            self.assertIn("task2", _active_sessions)

    def test_malicious_urls(self):
        """Test handling of malicious URLs."""
        # Test localhost URL with allow_private_urls=False
        with patch('feinn_agent.tools.browser._allow_private_urls', return_value=False):
            with self.assertRaises(ValueError):
                _validate_url("http://localhost:8080")
        
        # Test internal IP URL
        with patch('feinn_agent.tools.browser._allow_private_urls', return_value=False):
            with self.assertRaises(ValueError):
                _validate_url("http://192.168.1.1")
        
        # Test loopback IP URL
        with patch('feinn_agent.tools.browser._allow_private_urls', return_value=False):
            with self.assertRaises(ValueError):
                _validate_url("http://127.0.0.1")

    def test_configuration_options(self):
        """Test different configuration options."""
        # Test browser provider selection with different environment variables
        
        # Test no environment variables (should use local)
        with patch.dict(os.environ, {}, clear=True):
            import feinn_agent.tools.browser
            feinn_agent.tools.browser._cached_provider = None
            feinn_agent.tools.browser._provider_resolved = False
            provider = _get_browser_provider()
            self.assertIsInstance(provider, LocalBrowserProvider)
        
        # Test Browserbase provider
        with patch.dict(os.environ, {
            "BROWSERBASE_API_KEY": "test_key",
            "BROWSERBASE_PROJECT_ID": "test_project"
        }):
            import feinn_agent.tools.browser
            feinn_agent.tools.browser._cached_provider = None
            feinn_agent.tools.browser._provider_resolved = False
            provider = _get_browser_provider()
            self.assertIsInstance(provider, BrowserbaseProvider)
        
        # Test Browser Use provider
        with patch.dict(os.environ, {
            "BROWSER_USE_API_KEY": "test_key"
        }):
            import feinn_agent.tools.browser
            feinn_agent.tools.browser._cached_provider = None
            feinn_agent.tools.browser._provider_resolved = False
            provider = _get_browser_provider()
            self.assertIsInstance(provider, BrowserUseProvider)
        
        # Test Firecrawl provider
        with patch.dict(os.environ, {
            "FIRECRAWL_API_KEY": "test_key"
        }):
            import feinn_agent.tools.browser
            feinn_agent.tools.browser._cached_provider = None
            feinn_agent.tools.browser._provider_resolved = False
            provider = _get_browser_provider()
            self.assertIsInstance(provider, FirecrawlProvider)

    @patch('feinn_agent.tools.browser._get_browser_provider')
    async def test_session_timeout_handling(self, mock_get_provider):
        """Test session timeout handling."""
        # Create mock provider
        mock_provider = Mock()
        mock_provider.create_session.return_value = {"session_id": "test_session"}
        mock_provider.execute_command.return_value = "Command executed"
        mock_provider.close_session.return_value = True
        mock_get_provider.return_value = mock_provider
        
        # Create session
        session = await _get_or_create_session("test_task")
        self.assertEqual(session["session_id"], "test_session")
        
        # Simulate session inactivity by setting last activity to long ago
        from feinn_agent.tools.browser import _session_last_activity
        import time
        _session_last_activity["test_task"] = time.time() - 3600  # 1 hour ago
        
        # Get or create session again (should create new session)
        mock_provider.create_session.return_value = {"session_id": "new_session"}
        new_session = await _get_or_create_session("test_task")
        self.assertEqual(new_session["session_id"], "new_session")


if __name__ == '__main__':
    unittest.main()
