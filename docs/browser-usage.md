# FeinnAgent Browser Automation Usage Guide

## 1. Overview

FeinnAgent's browser automation tools provide powerful web browsing capabilities that enable agents to navigate websites, interact with page elements, and extract information. This guide explains how to install, configure, and use the browser tools effectively.

## 2. Installation

### 2.1 Required Dependencies

To use browser automation, you need to install the following dependencies:

#### For Local Browser Mode
```bash
# Install agent-browser (Node.js package)
npm install -g agent-browser

# Install Chromium (required for headless browsing)
agent-browser install --with-deps
```

#### For FeinnAgent
```bash
# Install FeinnAgent with browser support
pip install feinn-agent[browser]

# Or install from source
pip install -e .
```

### 2.2 Optional Dependencies

For cloud browser providers, you'll need additional configuration:

| Provider | Required Environment Variables |
|----------|-------------------------------|
| Browserbase | `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` |
| Browser Use | `BROWSER_USE_API_KEY` |
| Firecrawl | `FIRECRAWL_API_KEY` |

## 3. Configuration

### 3.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BROWSER_INACTIVITY_TIMEOUT` | Session inactivity timeout (seconds) | 300 |
| `BROWSER_COMMAND_TIMEOUT` | Command execution timeout (seconds) | 30 |
| `BROWSERBASE_API_KEY` | Browserbase API key | - |
| `BROWSERBASE_PROJECT_ID` | Browserbase project ID | - |
| `BROWSER_USE_API_KEY` | Browser Use API key | - |
| `FIRECRAWL_API_KEY` | Firecrawl API key | - |
| `FIRECRAWL_API_URL` | Firecrawl API URL | https://api.firecrawl.dev |
| `BROWSER_CDP_URL` | Custom CDP endpoint URL | - |
| `CAMOFOX_URL` | Camofox server URL | - |

### 3.2 Config File

You can also configure browser settings in the FeinnAgent config file:

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

## 4. Available Browser Tools

### 4.1 `browser_navigate`

**Purpose**: Navigate to a URL and initialize a browser session

**Parameters**:
- `url`: The URL to navigate to (e.g., "https://example.com")

**Returns**: Page snapshot with interactive elements and ref IDs

**Example**:
```python
{
  "name": "browser_navigate",
  "input": {
    "url": "https://example.com"
  }
}
```

### 4.2 `browser_snapshot`

**Purpose**: Get a text-based snapshot of the current page

**Parameters**:
- `full`: If true, returns complete page content (default: false)

**Returns**: Text snapshot with interactive elements and ref IDs

**Example**:
```python
{
  "name": "browser_snapshot",
  "input": {
    "full": true
  }
}
```

### 4.3 `browser_click`

**Purpose**: Click on an element identified by ref ID

**Parameters**:
- `ref`: Element reference from snapshot (e.g., "@e5")

**Returns**: Success message

**Example**:
```python
{
  "name": "browser_click",
  "input": {
    "ref": "@e5"
  }
}
```

### 4.4 `browser_type`

**Purpose**: Type text into an input field

**Parameters**:
- `ref`: Element reference from snapshot
- `text`: Text to type

**Returns**: Success message

**Example**:
```python
{
  "name": "browser_type",
  "input": {
    "ref": "@e3",
    "text": "Hello, world!"
  }
}
```

### 4.5 `browser_scroll`

**Purpose**: Scroll the page in a direction

**Parameters**:
- `direction`: "up" or "down"

**Returns**: Success message

**Example**:
```python
{
  "name": "browser_scroll",
  "input": {
    "direction": "down"
  }
}
```

### 4.6 `browser_back`

**Purpose**: Navigate back to previous page

**Parameters**: None

**Returns**: Success message

**Example**:
```python
{
  "name": "browser_back",
  "input": {}
}
```

### 4.7 `browser_press`

**Purpose**: Press a keyboard key

**Parameters**:
- `key`: Key to press (e.g., "Enter", "Tab", "Escape")

**Returns**: Success message

**Example**:
```python
{
  "name": "browser_press",
  "input": {
    "key": "Enter"
  }
}
```

### 4.8 `browser_get_images`

**Purpose**: Get list of images on current page

**Parameters**: None

**Returns**: List of image URLs and alt text

**Example**:
```python
{
  "name": "browser_get_images",
  "input": {}
}
```

## 5. Usage Examples

### 5.1 Basic Navigation and Snapshot

```python
# Navigate to a website
result = await agent.run([
    {
        "role": "user",
        "content": "Navigate to example.com and get the page content"
    }
])

# The agent will use browser_navigate and browser_snapshot tools
```

### 5.2 Form Filling and Submission

```python
# Fill out a form
result = await agent.run([
    {
        "role": "user",
        "content": "Go to https://example.com/login, enter username 'test' and password 'password', then click login"
    }
])

# Expected tool usage:
# 1. browser_navigate to login page
# 2. browser_snapshot to get element refs
# 3. browser_type to fill username
# 4. browser_type to fill password
# 5. browser_click to submit form
```

### 5.3 Web Scraping

```python
# Scrape product information
result = await agent.run([
    {
        "role": "user",
        "content": "Go to https://example.com/products, find the first product, and get its name and price"
    }
])

# Expected tool usage:
# 1. browser_navigate to products page
# 2. browser_snapshot to see products
# 3. browser_click on first product
# 4. browser_snapshot to get product details
```

## 6. Browser Backends

FeinnAgent supports multiple browser backends:

### 6.1 Local Browser

- Uses `agent-browser` CLI with headless Chromium
- Best for local development and testing
- No cloud dependencies

### 6.2 Browserbase

- Cloud-based browser with residential proxies
- Supports anti-bot protection and stealth mode
- Requires Browserbase account and API key

### 6.3 Browser Use

- Alternative cloud browser provider
- Simpler API integration
- Requires Browser Use API key

### 6.4 Firecrawl

- Specialized for web scraping
- Built-in content extraction
- Requires Firecrawl API key

## 7. Security Considerations

### 7.1 SSRF Protection

By default, FeinnAgent blocks access to private/internal URLs to prevent SSRF attacks. To allow private URLs:

```bash
# Set environment variable
export BROWSER_ALLOW_PRIVATE_URLS=true

# Or in config file
{
  "browser": {
    "allow_private_urls": true
  }
}
```

### 7.2 Content Safety

Browser content is sanitized before being passed to LLMs to prevent injection attacks and reduce token usage.

### 7.3 Session Isolation

Each task gets its own isolated browser session to prevent cross-task interference.

## 8. Troubleshooting

### 8.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `agent-browser not found` | agent-browser not installed | Run `npm install -g agent-browser` |
| `Chromium not found` | Chromium not installed | Run `agent-browser install` |
| `Session timeout` | Browser command took too long | Increase `BROWSER_COMMAND_TIMEOUT` |
| `Cloud provider error` | Missing API credentials | Set required environment variables |
| `Private URL blocked` | SSRF protection active | Set `allow_private_urls=true` if needed |

### 8.2 Debugging

To enable debug logging:

```bash
export FEINN_LOG_LEVEL=debug
```

### 8.3 Resource Management

- Monitor memory usage for multiple concurrent sessions
- Set appropriate timeout values based on your network speed
- Use cloud providers for complex browsing tasks to avoid local resource constraints

## 9. Advanced Usage

### 9.1 Custom CDP Endpoint

Connect to an existing Chrome instance:

```bash
export BROWSER_CDP_URL=ws://localhost:9222/devtools/browser/...
```

### 9.2 Camofox Integration

Use Camofox for anti-detection browsing:

```bash
# Install and run Camofox
git clone https://github.com/jo-inc/camofox-browser && cd camofox-browser
npm install && npm start

# Set Camofox URL
export CAMOFOX_URL=http://localhost:9377
```

### 9.3 Browserbase Advanced Features

Enable residential proxies and advanced stealth:

```bash
export BROWSERBASE_PROXIES=true
export BROWSERBASE_ADVANCED_STEALTH=true
```

## 10. Performance Optimization

### 10.1 Best Practices

- Use `browser_navigate` only when necessary
- For simple information retrieval, use `WebFetch` tool instead
- Limit concurrent browser sessions
- Use `full=false` for snapshots when only interactive elements are needed
- Close sessions explicitly when done

### 10.2 Scaling

- **Horizontal Scaling**: Deploy multiple FeinnAgent instances
- **Session Management**: Monitor and limit active sessions
- **Resource Allocation**: Adjust timeout values based on hardware

## 11. Examples

### 11.1 Complete Workflow Example

```python
from feinn_agent import FeinnAgent
from feinn_agent.config import load_config

# Create agent
config = load_config()
agent = FeinnAgent(config)

# Run browser workflow
result = await agent.run([
    {
        "role": "user",
        "content": "Search for 'Python programming' on Google and get the first result"
    }
])

print(result)
```

### 11.2 CLI Usage

```bash
# Interactive mode with browser tools
feinn -i

# Example CLI conversation
feinn> Navigate to google.com
feinn> Search for 'FeinnAgent'
feinn> Click on the first result
feinn> Get the page title
```

## 12. Conclusion

FeinnAgent's browser automation tools provide powerful capabilities for web interaction and data extraction. By following this guide, you can effectively leverage these tools to build sophisticated agents that can browse the web, interact with pages, and extract valuable information.

For more information, refer to the [technical documentation](./browser-feature-technical.md) and [requirements documentation](./browser-feature-requirements.md).
