# Contributing to FeinnAgent

Thank you for your interest in contributing to FeinnAgent! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Harness Engineering](#harness-engineering)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Git Workflow](#git-workflow)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Code Review Guidelines](#code-review-guidelines)

---

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- (Optional) pyenv for Python version management

### Initial Setup

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/FeinnAgent.git
cd FeinnAgent

# 3. Add upstream remote
git remote add upstream https://github.com/PeiziLiu/FeinnAgent.git

# 4. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# 5. Install in development mode
pip install -e ".[dev]"

# 6. Copy environment file
cp .env.example .env
# Edit .env with your API keys

# 7. Verify installation
feinn --help
```

### Using Git Worktree (Recommended for Feature Development)

```bash
# Create a worktree for feature development
git worktree add ../feinn-agent-feature-name dev

# Navigate to worktree
cd ../feinn-agent-feature-name

# Create feature branch
git checkout -b feature/your-feature-name
```

### Daily Development Commands

```bash
# Run tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agent.py -v

# Run with coverage
pytest tests/ --cov=src/feinn_agent --cov-report=term-missing

# Format code
ruff format src/

# Lint code
ruff check src/

# Fix auto-fixable issues
ruff check src/ --fix
```

---

## Harness Engineering

FeinnAgent embraces **Harness Engineering** — a methodology for building AI systems that guide agent behavior through **constraints, tools, documentation, and feedback loops**.

### Core Philosophy

> A harness is a set of constraints, tools, docs, and feedback loops that keep agents on track.

When developing features, consider how your changes fit into the three harness dimensions:

### 1. Guides (Proactive Guidance)

Guide agent behavior **before** execution to improve first-time success.

| Mechanism | Implementation | Purpose |
|-----------|-----------------|---------|
| **Safe Command Whitelist** | `permission/__init__.py` | Allow verified safe commands without confirmation |
| **Tool Descriptions** | `ToolDef.description` | Clear usage guidance for LLM understanding |
| **Timeout Defaults** | Tool schemas | Prevent runaway processes |
| **Plan Mode** | `PermissionMode.PLAN` | Require planning before execution |
| **Skill Templates** | `skill/*.py` | Reusable workflows with built-in guardrails |

**Development Checklist:**
- [ ] Does the tool description explain when/how to use it?
- [ ] Are there timeout recommendations in the schema?
- [ ] Is the safe command whitelist extended for new operations?
- [ ] Does the tool handle edge cases with clear error messages?

### 2. Sensors (Post-Execution Detection)

Detect output quality issues **after** execution to catch problems early.

| Mechanism | Implementation | Purpose |
|-----------|-----------------|---------|
| **Exit Code Semantics** | `process.py` | Explain non-zero exits (grep "no match" is normal) |
| **Diff Feedback** | `output.py` | Show file changes for verification |
| **GetDiagnostics** | `diagnostics.py` | Auto-detect code issues |
| **Output Truncation** | `output.py` | Preserve critical info (errors at end) |
| **ANSI Cleanup** | `process.py` | Remove escape sequences from output |

**Development Checklist:**
- [ ] Does the tool return meaningful diff for file changes?
- [ ] Are common exit codes documented (grep exit 1 = no match)?
- [ ] Is output truncation strategy optimal (head 50% + tail 25%)?
- [ ] Are ANSI escape codes stripped before LLM consumption?

### 3. Guardrails (Safety Boundaries)

Maintain security boundaries **throughout** the execution lifecycle.

| Mechanism | Implementation | Purpose |
|-----------|-----------------|---------|
| **Process Tree Cleanup** | `process.py` | Prevent zombie processes |
| **Dangerous Command Detection** | `permission/__init__.py` | Block harmful operations |
| **Tmux Isolation** | `tmux.py` | Long-running processes don't block main loop |
| **Tool Safety Flags** | `ToolDef` | Classify tools as read-only/concurrent-safe/destructive |
| **Permission Modes** | `permission/__init__.py` | User control over operations |

**Development Checklist:**
- [ ] Does the tool properly clean up on timeout/exception?
- [ ] Are subprocess calls using process groups (Unix) or taskkill (Windows)?
- [ ] Is input validated against injection attacks?
- [ ] Are shell commands escaped with `shlex.quote()`?
- [ ] Does the tool have appropriate safety flags set?

### Harness Design Patterns

#### Pattern 1: Graceful Degradation

```python
# Check for optional dependencies, don't fail if unavailable
def register_tmux_tools() -> int:
    _TMUX_BIN = shutil.which("tmux")
    if not _TMUX_BIN:
        return 0  # 0 tools registered, no error
    # ... register tools
```

#### Pattern 2: Layered Safety

```python
# Multiple safety layers for Bash execution
1. Permission check (accept-all/auto/manual/plan modes)
2. Safe command whitelist (auto-approve known safe)
3. Dangerous command detection (block known harmful)
4. Process group isolation (prevent fork bombs)
5. Timeout enforcement (prevent hangs)
6. Process tree cleanup (prevent zombies)
```

#### Pattern 3: Meaningful Feedback

```python
# Don't just return exit code - explain meaning
_EXIT_CODE_MEANINGS = {
    "grep": {1: "No matches found (not an error)"},
    "diff": {1: "Files differ (not an error)"},
    "test": {1: "Condition is false (not an error)"},
}
```

### Adding New Tools: Harness Checklist

When adding a new tool, verify all three dimensions:

```
## Tool: MyNewTool

### Guides
- [ ] Description explains purpose, inputs, and limitations
- [ ] Examples in description help LLM understand usage
- [ ] Timeout recommendation included
- [ ] Related tools mentioned for context switching

### Sensors
- [ ] Error messages are actionable
- [ ] Output format is LLM-parseable
- [ ] Diff feedback provided for file changes
- [ ] Exit codes documented if relevant

### Guardrails
- [ ] Safety flags set (read_only/concurrent_safe/destructive)
- [ ] Input validation prevents injection
- [ ] Timeout enforced with cleanup
- [ ] Safe command whitelist extended if needed
- [ ] Permission mode respected
```

### Continuous Improvement

When agent execution fails, iterate on the harness:

1. **Guides fail?** → Improve tool descriptions, add safe command patterns
2. **Sensors miss issues?** → Add diagnostic checks, improve exit code semantics
3. **Guardrails block too much?** → Extend safe command whitelist
4. **Guardrails allow too much?** → Add dangerous command patterns

---

## Code Standards

### Python Version and Type Annotations

- **Minimum Python version**: 3.11
- All modules must include `from __future__ import annotations` at the top
- All public functions and methods must have complete type annotations
- Internal functions should have type annotations (recommended)

```python
# Correct
from __future__ import annotations

async def read_file(path: str, limit: int = 100) -> str:
    ...

# Incorrect - Missing return type
async def read_file(path, limit=100):
    ...
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Modules | snake_case | `context.py`, `tool_registry.py` |
| Classes | PascalCase | `FeinnAgent`, `ToolRegistry` |
| Functions/Methods | snake_case | `add_message()`, `get_token_count()` |
| Constants | UPPER_SNAKE_CASE | `_MAX_RETRIES`, `DEFAULT_MODEL` |
| Private Members | Prefix `_` | `_tools`, `_parse_chunk()` |
| Type Aliases | PascalCase | `AgentEvent`, `AgentStream` |
| Dataclass Fields | snake_case | `tool_call_id`, `input_tokens` |

### Async Programming Guidelines

1. **Async-First**: All IO operations (network, file, database) must be `async def`
2. **No Blocking in Async**: Use `asyncio.to_thread()` for synchronous blocking calls
3. **Timeout Control**: All external calls must have timeouts using `asyncio.wait_for()`
4. **Concurrency Control**: Use `asyncio.Semaphore` to limit concurrency

```python
# Correct - Async IO with timeout
async def fetch_url(url: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        return response.text

# Correct - Sync blocking via to_thread
async def run_command(cmd: str) -> str:
    return await asyncio.to_thread(subprocess.run, cmd, capture_output=True)

# Incorrect - Blocking call in async function
async def bad_example():
    result = subprocess.run(cmd)  # Blocks the event loop!
```

### Data Model Conventions

1. **Core Types**: Use `dataclass` (see `types.py`)
2. **API Layer**: FastAPI request/response models can use Pydantic
3. **Immutability Preferred**: Design core data structures as immutable (`frozen=True`)
4. **Enums**: Use `StrEnum` instead of `str + Enum`

```python
from dataclasses import dataclass
from enum import StrEnum

@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]

class PermissionMode(StrEnum):
    AUTO = "auto"
    ACCEPT_ALL = "accept-all"
```

### Module Organization

- **Maximum module size**: ~500 lines (split if larger)
- **Import order**: stdlib > third-party > local (ruff's `I` rule handles this)
- **Circular imports**: Use `TYPE_CHECKING` guard or restructure
- **Public API**: Export via `__all__` in `__init__.py`

### Code Quality Tools

Ruff is configured in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

**Required checks before committing:**

```bash
ruff check src/
ruff format src/ --check
pytest tests/ -v
```

---

## Testing Requirements

### Test Framework

- **Framework**: pytest + pytest-asyncio
- **Async mode**: `asyncio_mode = "auto"` (configured in pyproject.toml)
- **Coverage target**: > 80%

### Test File Naming

| Module Under Test | Test File |
|-------------------|----------|
| `agent.py` | `tests/test_agent.py` |
| `tools/builtins.py` | `tests/test_tools.py` |
| `compaction.py` | `tests/test_compaction.py` |
| `memory/store.py` | `tests/test_memory.py` |
| `skill/` | `tests/test_skill.py` |

### Test Writing Guidelines

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_agent_handles_tool_call():
    """Test Agent correctly processes tool calls."""
    # Arrange - Prepare test data and mocks
    mock_provider = AsyncMock()
    ...
    
    # Act - Execute the operation under test
    result = await agent.run("test input")
    
    # Assert - Verify the result
    assert result is not None
```

**Rules:**
- Test function naming: `test_<feature>_<scenario>`
- Each test should verify one behavior
- Use `AsyncMock` for async dependencies
- Don't depend on external APIs (mock LLM calls)
- Mark integration tests with `@pytest.mark.integration`

### Running Tests

```bash
# Run all tests
pytest tests/ -v --tb=short

# Run specific module
pytest tests/test_tools.py -v

# With coverage
pytest tests/ --cov=src/feinn_agent --cov-report=term-missing

# Exclude integration tests
pytest tests/ -m "not integration"
```

---

## Git Workflow

### Branch Strategy

```
main (production)
  ↑
dev (development) ←── feature/xxx ── bugfix/yyy
  ↑
hotfix/zzz (urgent fixes)
```

### Branch Naming

- `feature/<description>` - New features
- `bugfix/<description>` - Bug fixes
- `hotfix/<description>` - Urgent fixes
- `docs/<description>` - Documentation updates
- `refactor/<description>` - Refactoring

### Workflow

```bash
# 1. Sync with upstream
git checkout dev
git pull upstream dev

# 2. Create feature branch
git checkout -b feature/your-feature

# 3. Make changes and commit
git add .
git commit -m "feat: add new feature"

# 4. Keep branch updated
git fetch upstream
git rebase upstream/dev

# 5. Push and create PR
git push origin feature/your-feature
```

---

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Code style changes (formatting, etc.) |
| `refactor` | Code refactoring |
| `test` | Adding or modifying tests |
| `chore` | Build process or auxiliary tool changes |
| `perf` | Performance improvements |
| `ci` | CI/CD changes |

### Examples

```bash
# Feature
git commit -m "feat(tools): add WebFetch tool for URL content retrieval"

# Bug fix
git commit -m "fix(compaction): prevent index out of bounds in truncation"

# Documentation
git commit -m "docs(readme): add deployment guide section"

# Refactoring
git commit -m "refactor(memory): extract storage backend interface"
```

---

## Pull Request Process

### Before Submitting

1. **Run all tests**: `pytest tests/ -v`
2. **Run linter**: `ruff check src/`
3. **Format code**: `ruff format src/`
4. **Update documentation** if needed
5. **Add tests** for new functionality

### PR Description Template

```markdown
## Summary
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Test addition

## Testing
Describe how the changes were tested.

## Checklist
- [ ] Code follows the style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass
```

### Review Process

1. Maintainers will review within 48 hours
2. Address feedback through additional commits
3. Once approved, maintainers will merge

---

## Code Review Guidelines

### For Authors

- **Keep PRs small**: One feature or fix per PR
- **Write clear descriptions**: Explain *why*, not just *what*
- **Respond promptly**: Address comments within 48 hours
- **Don't take feedback personally**: Reviews are about code, not you

### For Reviewers

- **Be constructive**: Suggest improvements, don't just criticize
- **Be timely**: Review within 48 hours
- **Be specific**: Reference line numbers, explain concerns clearly
- **Acknowledge good work**: Praise well-written code

### Review Checklist

- [ ] Code follows naming conventions
- [ ] Type annotations are complete
- [ ] Async/await used correctly
- [ ] Error handling is appropriate
- [ ] Tests cover the changes
- [ ] Documentation updated if needed
- [ ] No security issues introduced
- [ ] No performance regressions

---

## Architecture Constraints

### Layer Dependencies

```
Presentation Layer (CLI / API Server)
    ↓ only calls
Core Layer (Agent / Context / Compaction)
    ↓ only calls
Subsystem Layer (Tools / Memory / Task / Subagent / Permission / Skill)
    ↓ only calls
Infrastructure Layer (Providers / MCP / Storage)
```

**Rules:**
- No reverse dependencies
- No cross-layer jumps (must go through core)
- Low coupling between subsystems

### Tool System Constraints

- All tools must be registered via `registry.py`
- Tool handler signature: `async def handler(params: dict, config: dict) -> str`
- `input_schema` must be valid JSON Schema
- Tools must specify security level: `read_only`, `concurrent_safe`, or `destructive`

### Error Handling

- Tool errors should return strings (prefix `Error:`), not exceptions
- Provider network errors use retry mechanism
- Non-recoverable errors (auth failures) report directly to user

---

## Questions?

- **Issues**: [GitHub Issues](https://github.com/PeiziLiu/FeinnAgent/issues)
- **Email**: hanfazy@126.com
- **Discussions**: [GitHub Discussions](https://github.com/PeiziLiu/FeinnAgent/discussions)

---

Thank you for contributing to FeinnAgent!
