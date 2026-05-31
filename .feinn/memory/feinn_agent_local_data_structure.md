---
name: feinn_agent_local_data_structure
description: .feinn/ directory structure for local project data and memory
type: project
confidence: 0.9
source: user
last_used_at: 2026-06-01
conflict_group: feinn_agent_local_data_structure
---
The feinn-agent project uses a `.feinn/` directory in the project root for local project-scoped data. Contents observed:
- .feinn/tasks.json — Task tracking/state
- .feinn/memory/*.md — Project-scoped memory files (feinn_agent_current_branch_state.md, feinn_agent_project_overview.md, feinn_agent_tech_stack.md)

This is part of the framework's dual-scope memory system (user scope + project scope). The framework dogfoods its own memory system by storing project context in `.feinn/memory/`.