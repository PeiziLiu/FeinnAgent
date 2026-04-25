# FeinnAgent Browser Automation Technical Implementation

## 1. Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            FeinnAgent                              │
├─────────────────────────────────────────────────────────────────────┤
│          ┌─────────────────┐     ┌─────────────────┐              │
│          │  Tool Registry  │◄────┤  Browser Tools  │              │
│          └─────────────────┘     └─────────────────┘              │
│                     ▲                      ▲                       │
│                     │                      │                       │
│          ┌─────────────────┐     ┌─────────────────┐              │
│          │  Agent Engine   │     │  Browser Core   │              │
│          └─────────────────┘     └─────────────────┘              │
│                                         ▲                       │
│                                         │                       │
│                    ┌─────────────────────────────────┐            │
│                    │          Providers             │            │
│                    ├─────────────┬──────────────────┤            │
│                    │  Local      │  Cloud          │            │
│                    ├─────────────┼─────────┬────────┤            │
│                    │ agent-     │Browser- │Browser-│            │
│                    │ browser    │base     │Use     │Firecrawl   │
│                    └─────────────┴─────────┴────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Module Structure

```
feinn_agent/
├── tools/
│   ├── __init__.py
│   ├── browser.py          # Main browser tool definitions
│   └── browser_providers/
│       ├── __init__.py
│       ├── base.py         # Abstract base class
│       ├── local.py        # Local agent-browser
│       ├── browserbase.py  # Browserbase provider
│       ├── browseruse.py   # Browser Use provider
│       └── firecrawl.py    # Firecrawl provider
└── types.py                # ToolDef and other types
```

## 2. Core Components

### 2.1 Browser Tool Definitions

The browser tools will be defined using FeinnAgent's `ToolDef` structure and registered with the tool registry. Each tool will have a clear description, input schema, and handler function.

### 2.2 Browser Core

The browser core module will handle session management, command execution, and provider selection. It will maintain a registry of active sessions and manage their lifecycle.

### 2.3 Provider Interface

An abstract base class `BrowserProvider` will define the interface that all browser providers must implement. This allows for seamless switching between different browser backends.

### 2.4 Session Management

Session management will track active browser sessions per task ID, handle session cleanup, and provide session persistence across tool calls.

## 3. Implementation Details

### 3.1 Browser Tools

#### 3.1.1 browser_navigate

**Purpose**: Navigate to a URL and initialize a browser session

**Implementation**:
- Validate the URL for security (SSRF protection)
- Select appropriate browser provider
- Create new session if not exists
- Execute navigation command
- Return page snapshot with interactive elements

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "The URL to navigate to"
    }
  },
  "required": ["url"]
}
```

#### 3.1.2 browser_snapshot

**Purpose**: Get text-based snapshot of current page

**Implementation**:
- Check if session exists
- Execute snapshot command
- Process and truncate large content
- Return structured snapshot with element references

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "full": {
      "type": "boolean",
      "description": "If true, returns complete page content",
      "default": false
    }
  }
}
```

#### 3.1.3 browser_click

**Purpose**: Click on element identified by reference ID

**Implementation**:
- Validate element reference
- Execute click command
- Return success status

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "ref": {
      "type": "string",
      "description": "Element reference (e.g., @e5)"
    }
  },
  "required": ["ref"]
}
```

#### 3.1.4 browser_type

**Purpose**: Type text into input field

**Implementation**:
- Validate element reference
- Execute type command
- Return success status

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "ref": {
      "type": "string",
      "description": "Element reference"
    },
    "text": {
      "type": "string",
      "description": "Text to type"
    }
  },
  "required": ["ref", "text"]
}
```

### 3.2 Browser Core Implementation

#### 3.2.1 Session Management

```python
# Session storage
_active_sessions: Dict[str, Dict[str, str]] = {}  # task_id -> session info
_session_last_activity: Dict[str, float] = {}     # task_id -> timestamp

# Session cleanup thread
_cleanup_thread = None
_cleanup_running = False
_cleanup_lock = threading.Lock()

# Cleanup functions
def _cleanup_inactive_sessions():
    """Clean up sessions inactive for more than timeout"""
    # Implementation details

def _browser_cleanup_thread_worker():
    """Background thread for session cleanup"""
    # Implementation details
```

#### 3.2.2 Provider Selection

```python
def _get_browser_provider() -> BrowserProvider:
    """Select appropriate browser provider based on configuration"""
    # Check for CDP override
    # Check for cloud providers (Browserbase, BrowserUse, Firecrawl)
    # Fall back to local agent-browser
    # Return selected provider
```

#### 3.2.3 Command Execution

```python
async def _execute_browser_command(task_id: str, command: str, **kwargs) -> str:
    """Execute browser command using selected provider"""
    # Get or create session
    # Execute command via provider
    # Handle errors and timeouts
    # Return result
```

### 3.3 Provider Implementations

#### 3.3.1 Local Provider (agent-browser)

**Implementation**:
- Uses `agent-browser` CLI
- Handles local headless Chromium
- Manages process lifecycle
- Provides accessibility tree snapshots

**Key Methods**:
- `create_session()`: Start local browser process
- `execute_command()`: Run agent-browser commands
- `close_session()`: Terminate browser process

#### 3.3.2 Cloud Providers

**Browserbase**:
- Uses Browserbase API
- Supports residential proxies and stealth mode
- Provides session management via API

**Browser Use**:
- Uses Browser Use REST API
- Alternative cloud browser provider
- Simpler API integration

**Firecrawl**:
- Specialized for web scraping
- Built-in content extraction
- Cloud-based execution

## 4. Security Implementation

### 4.1 SSRF Protection

```python
def _is_private_url(url: str) -> bool:
    """Check if URL points to private/internal network"""
    # Parse URL
    # Check against private IP ranges
    # Check localhost and loopback addresses
    # Return True if private

def _validate_url(url: str) -> bool:
    """Validate URL for security"""
    if not _allow_private_urls() and _is_private_url(url):
        raise ValueError(f"Access to private URL not allowed: {url}")
    return True
```

### 4.2 Content Sanitization

```python
def _sanitize_content(content: str) -> str:
    """Sanitize page content before passing to LLM"""
    # Remove sensitive information
    # Truncate excessively long content
    # Return sanitized content
```

### 4.3 Error Handling

```python
except TimeoutError:
    return f"Error: Browser command timed out after {timeout} seconds"
except Exception as e:
    logger.error(f"Browser command failed: {e}")
    return f"Error: {str(e)}"
```

## 5. Integration with FeinnAgent

### 5.1 Tool Registration

```python
# Register browser tools
register(
    ToolDef(
        name="browser_navigate",
        description="Navigate to a URL in the browser",
        input_schema=NAVIGATE_SCHEMA,
        handler=_browser_navigate,
        read_only=False,
        concurrent_safe=True,
    )
)

# Register other browser tools...
```

### 5.2 Configuration Integration

**Environment Variables**:
- `BROWSER_INACTIVITY_TIMEOUT`
- `BROWSER_COMMAND_TIMEOUT`
- `BROWSERBASE_API_KEY`
- `BROWSER_USE_API_KEY`
- `FIRECRAWL_API_KEY`
- `BROWSER_CDP_URL`
- `CAMOFOX_URL`

**Config File Support**:
```json
{
  "browser": {
    "command_timeout": 30,
    "inactivity_timeout": 300,
    "cloud_provider": "local",
    "allow_private_urls": false
  }
}
```

### 5.3 Logging Integration

```python
logger = logging.getLogger(__name__)

# Example usage
logger.info(f"Created browser session for task {task_id}")
logger.warning(f"Browser command failed: {e}")
```

## 6. Performance Optimization

### 6.1 Async Execution

```python
async def _browser_navigate(params: dict[str, Any], config: dict[str, Any]) -> str:
    """Async handler for browser_navigate tool"""
    url = params.get("url", "")
    if not url:
        return "Error: url is required"
    
    # Get task ID from context or generate new one
    task_id = config.get("task_id", new_id("task"))
    
    try:
        result = await _execute_browser_command(
            task_id, "navigate", url=url
        )
        return result
    except Exception as e:
        return f"Error: {str(e)}"
```

### 6.2 Session Reuse

```python
def _get_or_create_session(task_id: str) -> Dict[str, str]:
    """Get existing session or create new one"""
    if task_id in _active_sessions:
        _update_session_activity(task_id)
        return _active_sessions[task_id]
    
    # Create new session
    session = _create_session(task_id)
    _active_sessions[task_id] = session
    _update_session_activity(task_id)
    
    # Start cleanup thread if not running
    _start_browser_cleanup_thread()
    
    return session
```

### 6.3 Command Batching

```python
def _batch_commands(commands: list) -> list:
    """Batch multiple browser commands for efficiency"""
    # Group similar commands
    # Optimize execution order
    # Return batched commands
```

## 7. Testing Strategy

### 7.1 Unit Tests

- Test session management
- Test provider selection
- Test URL validation
- Test error handling

### 7.2 Integration Tests

- Test local browser functionality
- Test cloud provider integration
- Test session cleanup
- Test security features

### 7.3 End-to-End Tests

- Test complete browser workflows
- Test multi-step interactions
- Test performance under load
- Test error recovery scenarios

## 8. Deployment Considerations

### 8.1 Dependencies

**Required**:
- `agent-browser` (Node.js package)
- `httpx` (existing dependency)

**Optional**:
- Browserbase SDK (for cloud mode)
- Firecrawl SDK (for cloud mode)

### 8.2 Installation

```bash
# Install agent-browser
npm install -g agent-browser
agent-browser install --with-deps

# Install FeinnAgent with browser support
pip install feinn-agent[browser]
```

### 8.3 Scaling

- **Horizontal Scaling**: Multiple FeinnAgent instances can run independently
- **Session Management**: Each instance manages its own browser sessions
- **Resource Allocation**: Monitor memory and CPU usage for browser processes

## 9. Monitoring and Maintenance

### 9.1 Logging

- Browser session creation and cleanup
- Command execution and errors
- Performance metrics
- Security events

### 9.2 Health Checks

- Browser process status
- Session count and age
- Provider connectivity
- Resource usage

### 9.3 Troubleshooting

**Common Issues**:
- `agent-browser` not installed
- Cloud provider credentials missing
- Timeout errors
- Memory issues with multiple sessions

**Resolution Steps**:
- Verify dependencies are installed
- Check environment variables
- Increase timeout settings
- Monitor and limit concurrent sessions

## 10. Future Enhancements

### 10.1 Advanced Features

- **Visual Testing**: Compare page screenshots
- **Browser Profiles**: Support for different browser profiles
- **Network Control**: Mock responses and network throttling
- **Mobile Emulation**: Test mobile websites

### 10.2 Integration Opportunities

- **CI/CD Integration**: Automated browser testing
- **Web Scraping Framework**: Structured data extraction
- **Accessibility Testing**: Evaluate website accessibility
- **Performance Testing**: Measure page load times

## 11. References

- [hermes-agent browser_tool implementation](https://github.com/hermes-agent/hermes-agent/blob/main/tools/browser_tool.py)
- [agent-browser documentation](https://github.com/agent-browser/agent-browser)
- [Browserbase API documentation](https://browserbase.com/docs)
- [Firecrawl API documentation](https://firecrawl.dev/docs)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)

## 12. Appendices

### 12.1 API Reference

#### Browser Tools

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| browser_navigate | Navigate to URL | url: string | Page snapshot |
| browser_snapshot | Get page snapshot | full: boolean | Text snapshot |
| browser_click | Click element | ref: string | Success message |
| browser_type | Type text | ref: string, text: string | Success message |
| browser_scroll | Scroll page | direction: string | Success message |
| browser_back | Navigate back | - | Success message |
| browser_press | Press key | key: string | Success message |
| browser_get_images | Get images | - | Image list |
| browser_vision | Visual analysis | question: string | AI analysis |

### 12.2 Configuration Reference

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| BROWSER_INACTIVITY_TIMEOUT | Session inactivity timeout (seconds) | 300 |
| BROWSER_COMMAND_TIMEOUT | Command timeout (seconds) | 30 |
| BROWSERBASE_API_KEY | Browserbase API key | - |
| BROWSERBASE_PROJECT_ID | Browserbase project ID | - |
| BROWSER_USE_API_KEY | Browser Use API key | - |
| FIRECRAWL_API_KEY | Firecrawl API key | - |
| FIRECRAWL_API_URL | Firecrawl API URL | https://api.firecrawl.dev |
| BROWSER_CDP_URL | Custom CDP endpoint | - |
| CAMOFOX_URL | Camofox server URL | - |
| AUXILIARY_VISION_MODEL | Vision model for browser_vision | - |

#### Config File

```json
{
  "browser": {
    "command_timeout": 30,
    "inactivity_timeout": 300,
    "cloud_provider": "local",
    "allow_private_urls": false,
    "providers": {
      "browserbase": {
        "api_key": "YOUR_KEY",
        "project_id": "YOUR_PROJECT"
      }
    }
  }
}
```

### 12.3 Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| E_BROWSER_NOT_INSTALLED | agent-browser not found | Install agent-browser |
| E_CLOUD_CREDENTIALS_MISSING | Missing API keys | Set environment variables |
| E_URL_VALIDATION_FAILED | Invalid or private URL | Use valid public URL |
| E_SESSION_TIMEOUT | Session timed out | Increase timeout settings |
| E_COMMAND_FAILED | Browser command failed | Check browser logs |
| E_MEMORY_ERROR | Insufficient memory | Reduce concurrent sessions |