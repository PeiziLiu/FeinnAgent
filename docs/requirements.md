# FeinnAgent Requirements Design Document

## 1. Project Overview

### 1.1 Project Background

With the rapid development of Large Language Model (LLM) capabilities, AI Agents are becoming the core technology for automating complex tasks. Enterprise scenarios impose higher requirements on Agents: multi-concurrency processing capabilities, stable long-running operations, flexible task orchestration, and comprehensive security controls.

FeinnAgent aims to build an **enterprise-grade, multi-concurrency, scalable** AI Agent framework that meets the high performance and reliability requirements of production environments.

### 1.2 Design Goals

| Goal | Description | Priority | Status |
|------|-------------|----------|--------|
| Enterprise Concurrency | Support parallel session processing with resource isolation | P0 | Done |
| Long Conversation Stability | Intelligent context compression to avoid window overflow | P0 | Done |
| Task Orchestration | DAG task management supporting complex workflows | P1 | Done |
| Sub-agent Collaboration | Concurrent sub-agents for parallel task decomposition | P1 | Done |
| Multi-Model Support | Unified interface supporting any LLM provider | P0 | Done |
| Security & Control | Fine-grained permissions, audit logs | P1 | Done |
| Easy Extension | Modular design, plugin-based tools | P2 | Done |
| Skill System | Reusable prompt templates with activators and parameter substitution | P1 | Done |
| Execution Engine Enhancement | Process tree management, Tmux, diagnostics, harness engineering | P1 | In Progress |
| MCP Protocol Integration | Native Model Context Protocol support for extended tool ecosystem | P1 | Done |
| Dual-Scope Memory | Workspace-level and Agent-level memory isolation | P1 | Done |

### 1.3 Supported LLM Providers

| Provider | Type | Implementation |
|----------|------|----------------|
| OpenAI | Cloud | `providers.py` - OpenAIProvider |
| Anthropic | Cloud | `providers.py` - AnthropicProvider |
| Google Gemini | Cloud | `providers.py` - GeminiProvider |
| DeepSeek | Cloud | `providers.py` - DeepSeekProvider |
| SiliconFlow | Cloud | `providers.py` - SiliconFlowProvider |
| Moonshot | Cloud | `providers.py` - MoonshotProvider |
| Azure OpenAI | Cloud | `providers.py` - AzureOpenAIProvider |
| vLLM | Local | `providers.py` - vLLMProvider |
| Ollama | Local | `providers.py` - OllamaProvider |
| LM Studio | Local | `providers.py` - LMStudioProvider |

### 1.4 Reference Projects

- **CheetahClaws**: Python Agent architecture, Plan mode design, execution engine (process tree, Tmux, diagnostics)
- **Claude Code**: Tool system, interaction design, MCP integration
- **Hermes Agent**: Enterprise features, multi-platform gateway, RL training, exit code semantics

---

## 2. Functional Requirements

### 2.1 Core Features

#### 2.1.1 Conversation Management

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-001 | Multi-turn Conversation | Support continuous user interaction | Maintain context, support 50+ turns | `agent.py` - FeinnAgent.run() |
| F-002 | Tool Invocation | LLM can call external tools | Support 20+ built-in tools | `tools/registry.py` - ToolRegistry |
| F-003 | Streaming Response | Real-time content generation | AsyncIterator stream, token-level events | `agent.py` - AgentStream |
| F-004 | Extended Thinking | Support reasoning/thinking blocks | ThinkingChunk event type | `types.py` - ThinkingChunk |
| F-005 | Permission Integration | Permission check for destructive tools | PermissionRequest events | `permission/__init__.py` |
| F-006 | Token Usage Tracking | Track input/output token consumption | Per-turn and total token counts | `types.py` - TurnDone, AgentDone |

#### 2.1.2 Tool System

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-011 | File Operations | Read/write/edit files | Support large files (>1MB) with chunking, unified diff output | `tools/builtins.py` - Read, Write, Edit |
| F-012 | Code Search | Glob/Grep search | Regex support, configurable results, glob filtering | `tools/builtins.py` - Glob, Grep |
| F-013 | Web Access | Fetch web content | Support HTML/Markdown fetch | `tools/builtins.py` - WebFetch |
| F-014 | Command Execution | Bash command execution | Timeout control, output truncation, process tree cleanup | `tools/builtins.py` - Bash; `tools/process.py` |
| F-015 | Tool Registration | Dynamically register new tools | Decorator pattern, auto-discovery | `tools/registry.py` - register() |
| F-016 | MCP Support | Connect to MCP services | Support stdio/sse/http transport | `mcp/client.py` |
| F-017 | Tmux Integration | Persistent session management | Session CRUD, send keys, capture output | `tools/tmux.py` |
| F-018 | Code Diagnostics | Built-in linter/checker | Support pyright/eslint/shellcheck | `tools/diagnostics.py` |

#### 2.1.3 Skill System

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-101 | Skill Loading | Load skills from filesystem (.md files) | Support global (~/.feinn/skills/) and project (.feinn/skills/) scopes | `skill/loader.py` - SkillLoader |
| F-102 | Skill Activation | Trigger skills via activator keywords | Match `/command` style activators, with parameter passing | `skill/loader.py` - detect_skill_activator() |
| F-103 | Template Substitution | Support parameter placeholders | $PARAMS, $ARGUMENTS, named $NAME substitution | `skill/loader.py` - SkillTemplate |
| F-104 | Built-in Skills | Provide common workflow skills | commit, review, explain, test, doc | `skill/builtin.py` - register_builtin_skills() |
| F-105 | Skill Isolation | Support isolated execution mode | Separate tool permissions per skill | SkillTemplate.allowed_tools, exec_mode |
| F-106 | Frontmatter Config | YAML frontmatter for skill metadata | id, summary, activators, tools, param-guide, param-names | `skill/loader.py` - SkillTemplate |
| F-107 | Execution Engine | Skill execution with conversation context | Direct or isolated mode execution | `skill/executor.py` - SkillExecutor |

#### 2.1.4 Context Management

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-021 | Length Detection | Monitor context length | Real-time token counting via provider | `context.py` - get_token_count() |
| F-022 | Smart Compression | Auto-compress history messages | Preserve key information when threshold exceeded | `compaction.py` - CompactionEngine |
| F-023 | Hierarchical Strategy | Multi-level compression strategy | Summary → Selective Drop → Truncation | `compaction.py` - CompactionStrategy |
| F-024 | User Control | Configurable compression parameters | Adjustable threshold, strategy | AgentConfig.compact_threshold |
| F-025 | System Prompt Building | Dynamic system prompt assembly | Memory context, workspace info, tool schemas | `context.py` - build_system_prompt() |

### 2.2 Enterprise Features

#### 2.2.1 Concurrency Processing

| ID | Requirement | Description | Acceptance Criteria |
|----|-------------|-------------|---------------------|
| F-031 | Multi-Session Concurrency | Process multiple sessions simultaneously | 100+ concurrent connections |
| F-032 | Resource Isolation | Resource isolation between sessions | Memory, CPU limits |
| F-033 | Flow Control | Request rate limiting | Token bucket algorithm |
| F-034 | Load Balancing | Multi-instance load distribution | Support horizontal scaling |

#### 2.2.2 Task System

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-041 | Task Creation | Create trackable tasks | Auto-increment ID, subject, description, active_form | `task/store.py` - TaskCreate |
| F-042 | Dependency Management | Inter-task dependency relationships | blocks/blocked_by DAG edges, reverse edge maintenance | `task/store.py` - task_create, task_update |
| F-043 | State Tracking | Task state machine | pending → in_progress → completed/cancelled | `task/store.py` - TaskStatus enum |
| F-044 | Owner Assignment | Task ownership tracking | Owner field for agent/user assignment | `task/store.py` - Task.owner |
| F-045 | Persistence | Task state persistence | JSON file storage (.feinn/tasks.json) | `task/store.py` - _save_tasks, _load_tasks |

#### 2.2.3 Sub-agent System

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-051 | Sub-agent Creation | Dynamically create sub-agents | Specify type, prompt, model override | `subagent/manager.py` - spawn() |
| F-052 | Parallel Execution | Multiple sub-agents run concurrently | asyncio.Semaphore concurrency control | `subagent/manager.py` - _run_agent() |
| F-053 | Result Collection | Aggregate sub-agent results | Wait/polling modes, error propagation | `subagent/manager.py` - check_result() |
| F-054 | Type System | Predefined agent types | general-purpose, coder, reviewer, researcher, tester | `subagent/manager.py` - _BUILTIN_AGENTS |
| F-055 | Tool Restrictions | Per-agent-type tool whitelisting | Restricted tools deregistered during execution | `subagent/manager.py` - _execute() |
| F-056 | Depth Control | Prevent infinite agent recursion | Max depth limit with error handling | `subagent/manager.py` - max_depth |
| F-057 | Lifecycle Management | Task tracking and cleanup | SubAgentTask dataclass with status tracking | `subagent/manager.py` - SubAgentTask |

#### 2.2.4 Memory System

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-061 | Dual-Scope Storage | User (global) and Project (repo-local) scopes | Cross-session sharing for user scope | `memory/store.py` |
| F-062 | Markdown Storage | YAML frontmatter + content body | Metadata: name, description, type, confidence, source | `memory/store.py` - MemoryEntry |
| F-063 | Keyword Search | Search by keyword with ranking | Confidence × recency decay scoring | `memory/store.py` - search_memory() |
| F-064 | Memory CRUD | Create, read, list, delete operations | Complete lifecycle management | `memory/store.py` - save_memory, search_memory, list_memories, delete_memory |
| F-065 | System Prompt Integration | Inject memory context into system prompt | Build memory index for LLM context | `memory/store.py` - get_memory_context() |

#### 2.2.5 Permission Control

| ID | Requirement | Description | Acceptance Criteria | Implementation |
|----|-------------|-------------|---------------------|----------------|
| F-071 | Permission Mode | Four approval modes | accept-all/auto/manual/plan | `types.py` - PermissionMode |
| F-072 | Tool Classification | Tool risk grading | read_only/concurrent_safe/destructive flags | `types.py` - ToolDef |
| F-073 | Approval Process | Manual confirmation mechanism | PermissionRequest event for interactive confirmation | `permission/__init__.py` |
| F-074 | Plan Mode | Read-only + plan file writes only | Special handling for plan files | `permission/__init__.py` |
| F-075 | Auto Mode Logic | Smart judgment for destructive operations | read_only/concurrent_safe tools auto-approved | `permission/__init__.py` |

### 2.3 Interface Requirements

#### 2.3.1 REST API

| ID | Requirement | Description | Acceptance Criteria |
|----|-------------|-------------|---------------------|
| F-081 | Session Management | Create/delete/list | Full CRUD |
| F-082 | Message Sending | Send user messages | Async processing |
| F-083 | SSE Push | Server push | Real-time event stream |
| F-084 | Task Management | Task CRUD | Complete lifecycle |
| F-085 | Memory Operations | Memory CRUD | Dual-scope support |

#### 2.3.2 CLI

| ID | Requirement | Description | Acceptance Criteria |
|----|-------------|-------------|---------------------|
| F-091 | Interactive Mode | Continuous conversation | Similar to ChatGPT CLI |
| F-092 | Single Execution | One-time tasks | Suitable for script calls |
| F-093 | Service Start | Start API service | Production deployment |
| F-094 | Configuration Management | View/modify configuration | Persistent storage |

---

## 3. Non-Functional Requirements

### 3.1 Performance Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NF-001 | Response Latency | P95 < 2s (first token) |
| NF-002 | Throughput | 100+ TPS |
| NF-003 | Concurrent Connections | 1000+ WebSocket |
| NF-004 | Memory Usage | < 2GB (single instance) |
| NF-005 | Startup Time | < 5s |

### 3.2 Reliability Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NF-011 | Availability | 99.9% |
| NF-012 | Fault Recovery | Auto-restart, state recovery |
| NF-013 | Data Persistence | Zero data loss |
| NF-014 | Graceful Shutdown | Complete current requests |

### 3.3 Security Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| NF-021 | Input Validation | All input parameter validation |
| NF-022 | Command Whitelist | Bash command restrictions |
| NF-023 | Path Restrictions | File access sandbox |
| NF-024 | Key Management | Secure API Key storage |
| NF-025 | Audit Logging | Complete operation records |

### 3.4 Maintainability Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| NF-031 | Code Coverage | > 80% test coverage |
| NF-032 | Complete Documentation | API/architecture/development docs |
| NF-033 | Log Levels | DEBUG/INFO/WARNING/ERROR |
| NF-034 | Monitoring Metrics | Prometheus metrics |

---

## 4. User Scenarios

### 4.1 Scenario 1: Code Review Assistant

**Role**: Development Team
**Scenario**: Automatically review PRs, check code quality, security vulnerabilities

```
1. Developer submits PR
2. FeinnAgent triggers code review sub-agent
3. Execute in parallel:
   - Code style check
   - Security vulnerability scan
   - Performance analysis
   - Test coverage check
4. Aggregate results, generate review report
5. Auto-comment on PR
```

### 4.2 Scenario 2: Intelligent Customer Service

**Role**: Customer Service Team
**Scenario**: 7x24 automatic response to customer inquiries

```
1. Customer sends question
2. FeinnAgent searches knowledge base
3. Analyze question intent
4. Call appropriate tools to query information
5. Generate and send response
6. Escalate complex issues to human
```

### 4.3 Scenario 3: Data Analysis Assistant

**Role**: Data Analyst
**Scenario**: Automated data processing workflow

```
1. User uploads data file
2. FeinnAgent analyzes data structure
3. Create data processing task chain:
   - Data cleaning
   - Feature engineering
   - Model training
   - Result visualization
4. Execute independent tasks in parallel
5. Summarize analysis results
```

### 4.4 Scenario 4: DevOps Assistant

**Role**: Operations Engineer
**Scenario**: Automated deployment and monitoring

```
1. Receive deployment command
2. Check environment status
3. Execute deployment tasks:
   - Code pull
   - Dependency installation
   - Service restart
   - Health check
4. Monitor deployment status
5. Report results
```

---

## 5. Constraints

### 5.1 Technical Constraints

- **Language**: Python 3.11+
- **Async**: Must use asyncio for all IO operations
- **Types**: Complete type annotations (using `from __future__ import annotations`)
- **Dependencies**: Core dependencies are minimal; development tools in optional dependencies
- **Data Models**: Use dataclasses for core types (not Pydantic for core, Pydantic for API layer)
- **Core Dependencies**: anthropic, openai, httpx, fastapi, uvicorn, pydantic, rich, prompt-toolkit, click, pyyaml, watchdog, aiofiles, python-dotenv
- **Development Dependencies**: pytest, pytest-asyncio, pytest-cov, ruff

### 5.2 Deployment Constraints

- **Container**: Support Docker deployment
- **Orchestration**: Support Kubernetes
- **Configuration**: Environment variables + config files
- **Logging**: stdout/stderr output

### 5.3 Compliance Constraints

- **License**: Apache 2.0 open source license
- **Privacy**: No user data collection
- **Security**: Follow OWASP security guidelines

---

## 6. Glossary

| Term | Definition |
|------|------------|
| Agent | Intelligent agent, AI entity that executes tasks via LLM and tools |
| LLM | Large Language Model |
| MCP | Model Context Protocol for extending tool ecosystem |
| DAG | Directed Acyclic Graph, used for task dependency management |
| SSE | Server-Sent Events for streaming responses |
| Context Window | Maximum tokens LLM can process in a single request |
| Tool | External function that Agent can call to interact with the world |
| Subagent | Auxiliary agent spawned by main agent for parallel task execution |
| Workspace | Project-level resource isolation unit |
| Skill | Reusable prompt template with activators and parameter substitution |
| Harness Engineering | Engineering methodology: constraints, tools, docs and feedback loops |
| Compaction | Context compression to fit within LLM token limits |
| AgentStream | AsyncIterator of AgentEvent objects for streaming responses |
| ToolDef | Tool definition with name, description, schema, and handler |
| PermissionMode | Four modes: accept-all, auto, manual, plan |
| Dual-Scope Memory | Memory split into user (global) and project (repo-local) scopes |

---

## 7. Appendix

### 7.1 Related Documents

- [Architecture Design](architecture.md)
- [Technical Design](technical.md)
- [Execution Engine Upgrade Requirements](execution-engine-requirements.md)
- [Execution Engine Technical Design](execution-engine-technical.md)
- [Development Roadmap](roadmap.md)

### 7.2 Reference Documentation

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### 7.3 Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-11 | Feinn Team | Initial version |
| 1.1 | 2026-04-16 | Feinn Team | Added Skill system requirements (F-101~F-107), Tmux/diagnostics tool requirements (F-017~F-018), updated permission modes, fixed Python version constraint to 3.11+, added glossary entries, linked execution engine docs |
| 1.2 | 2026-04-16 | Feinn Team | Added implementation file references for all requirements, updated LLM provider list, enhanced context management and conversation management sections, added MCP support details |
