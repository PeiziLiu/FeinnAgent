"""Tests for FeinnAgent browser providers functionality."""

import unittest
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.tools.browser_providers.base import BrowserProvider
from feinn_agent.tools.browser_providers.local import LocalBrowserProvider
from feinn_agent.tools.browser_providers.browserbase import BrowserbaseProvider
from feinn_agent.tools.browser_providers.browseruse import BrowserUseProvider
from feinn_agent.tools.browser_providers.firecrawl import FirecrawlProvider


class TestBrowserProviders(unittest.TestCase):
    """Test browser providers functionality."""

    def test_base_browser_provider(self):
        """Test Base BrowserProvider class."""
        # Test that Base class is abstract
        with self.assertRaises(TypeError):
            BrowserProvider()

    def test_local_browser_provider(self):
        """Test LocalBrowserProvider."""
        provider = LocalBrowserProvider()
        self.assertEqual(provider.provider_name(), "local")
        
        # Test is_configured method
        # This will return False if no browser is available, which is expected in test environment
        configured = provider.is_configured()
        self.assertIsInstance(configured, bool)

    def test_browserbase_provider(self):
        """Test BrowserbaseProvider."""
        provider = BrowserbaseProvider()
        self.assertEqual(provider.provider_name(), "Browserbase")
        
        # Test is_configured method
        configured = provider.is_configured()
        self.assertIsInstance(configured, bool)

    def test_browseruse_provider(self):
        """Test BrowserUseProvider."""
        provider = BrowserUseProvider()
        self.assertEqual(provider.provider_name(), "Browser Use")
        
        # Test is_configured method
        configured = provider.is_configured()
        self.assertIsInstance(configured, bool)

    def test_firecrawl_provider(self):
        """Test FirecrawlProvider."""
        provider = FirecrawlProvider()
        self.assertEqual(provider.provider_name(), "Firecrawl")
        
        # Test is_configured method
        configured = provider.is_configured()
        self.assertIsInstance(configured, bool)


if __name__ == "__main__":
    unittest.main()
